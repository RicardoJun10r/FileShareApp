import asyncio
import base64
import ipaddress
import os
import socket
import logging
from time import monotonic
from contextlib import asynccontextmanager, suppress
from collections import OrderedDict
from io import BytesIO
from pathlib import Path
from typing import Annotated
from urllib.parse import quote
from uuid import uuid4

import qrcode
import psutil
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl

from tabular_preview import table_page, MAX_INPUT_BYTES
from preview_jobs import PreviewJobs
from preview_cache import PreviewCache, memory_size
from catalog_sync import CatalogChanges

# Conteúdo em memória: os arquivos são perdidos ao reiniciar o servidor.
db = {}
links = {}
catalog = CatalogChanges()
subscribers: set[asyncio.Queue] = set()
FILE_TTL_SECONDS = 120
MEMORY_RESERVE_BYTES = 256 * 1024 * 1024


def memory_budget(available):
    # Margem para cópias, prévias, multipart e outros programas.
    return max(0, min(512 * 1024 * 1024, available // 4,
                      (available - MEMORY_RESERVE_BYTES) // 2))


def expire_files():
    now = monotonic()
    expired = {key for key, file in db.items()
               if file.get("expires_at", float("inf")) <= now}
    for key in expired:
        del db[key]
    for key in list(pdf_render_cache):
        if key[0] in expired:
            del pdf_render_cache[key]
    if hasattr(app.state, "preview_cache"):
        for key in expired:
            app.state.preview_cache.discard_file(key)
    if expired:
        catalog.record(deleted=expired)
        notify_clients()


async def expiration_loop():
    while True:
        await asyncio.sleep(1)
        expire_files()


@asynccontextmanager
async def lifespan(app):
    app.state.storage_limit = memory_budget(psutil.virtual_memory().available)
    app.state.upload_lock = asyncio.Lock()
    app.state.preview_jobs = PreviewJobs()
    app.state.preview_cache = PreviewCache(min(32 * 1024 * 1024, app.state.storage_limit // 8))
    pdf_render_cache.clear()
    logging.getLogger("uvicorn.error").info(
        "Limite de arquivos em RAM: %.1f MiB; expiração: 120 segundos",
        app.state.storage_limit / (1024 * 1024),
    )
    task = asyncio.create_task(expiration_loop())
    try:
        yield
    finally:
        await app.state.preview_jobs.close()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def expire_before_request(request, call_next):
    expire_files()
    return await call_next(request)


@app.get("/storage/")
async def storage_info():
    return {"limit": app.state.storage_limit,
            "used": sum(len(file["content"]) for file in db.values()),
            "ttl_seconds": FILE_TTL_SECONDS}

INDEX_PATH = Path(__file__).resolve().parent / "static" / "index.html"
app.mount("/static", StaticFiles(directory=INDEX_PATH.parent), name="static")
MAX_UPLOAD_BYTES = int(os.environ.get("FILESHARE_MAX_UPLOAD_MB", "1024")) * 1024 * 1024
PDF_RENDER_CACHE_SIZE = 24
pdf_render_cache: "OrderedDict[tuple[str, int], tuple[bytes, int]]" = OrderedDict()


def connection_url(request: Request):
    configured = os.environ.get("FILESHARE_PUBLIC_URL")
    if configured:
        return str(HttpUrl(configured))
    host = request.url.hostname or "localhost"
    try:
        local = (
            ipaddress.ip_address(host).is_loopback
            or ipaddress.ip_address(host).is_unspecified
        )
    except ValueError:
        local = host.lower() == "localhost"
    if local:
        try:
            # UDP connect escolhe a interface da rota padrão, sem enviar dados.
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("192.0.2.1", 9))
                host = sock.getsockname()[0]
        except OSError:
            raise HTTPException(
                status_code=503,
                detail="Abra o FileShare pelo IP da rede ou configure FILESHARE_PUBLIC_URL",
            )
    authority = f"[{host}]" if ":" in host else host
    if request.url.port:
        authority += f":{request.url.port}"
    return f"{request.url.scheme}://{authority}/"


@app.get("/connection/")
def connection_info(request: Request):
    url = connection_url(request)
    output = BytesIO()
    qrcode.make(url).save(output, format="PNG")
    return {
        "url": url,
        "qr": "data:image/png;base64,"
        + base64.b64encode(output.getvalue()).decode("ascii"),
    }


@app.get("/preview/{file_id}/outline")
async def pdf_outline(file_id: str):
    file = db.get(file_id)
    if file is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    if preview_type(file["filename"])[0] != "pdf":
        raise HTTPException(status_code=415, detail="Este arquivo não é um PDF")
    return await indexed_preview(file_id, file, "outline")


async def indexed_preview(file_id, file, kind, options=()):
    if len(file["content"]) > MAX_INPUT_BYTES:
        raise HTTPException(413, "Prévia limitada a arquivos de até 32 MiB. Baixe o original.")
    key = (file_id, kind, *options)
    cache = app.state.preview_cache
    value = cache.get(key)
    if value is None:
        value = await app.state.preview_jobs.run(key, kind, file["content"], options)
        expire_files()
        if file_id not in db:
            raise HTTPException(404, "Arquivo expirado")
        cache.put(key, value)
    return value


def notify_clients():
    for queue in tuple(subscribers):
        if not queue.full():
            queue.put_nowait(None)


class SharedLink(BaseModel):
    url: HttpUrl = Field(max_length=4096)
    title: str = Field(default="", max_length=200)


@app.post("/links/", status_code=201)
async def share_link(link: SharedLink):
    if link.url.username or link.url.password:
        raise HTTPException(
            status_code=422, detail="Use um link sem usuário ou senha no endereço"
        )
    item = {
        "id": uuid4().hex,
        "url": str(link.url),
        "title": link.title.strip() or str(link.url),
    }
    links[item["id"]] = item
    catalog.record(links=[item])
    notify_clients()
    return item


@app.get("/links/")
async def list_links():
    return list(links.values())


async def read_upload(file: UploadFile) -> bytes:
    # O tamanho foi calculado pelo parser multipart antes de entrar na rota.
    content = await file.read(file.size + 1)
    if len(content) != file.size:
        raise HTTPException(status_code=400, detail="Tamanho do arquivo inconsistente")
    return content


@app.post("/upload/")
async def upload_files(
    files: Annotated[list[UploadFile], File(description="Multiple files as UploadFile")],
):
    # Serializa admissão e leitura para lotes concorrentes não excederem a quota.
    async with app.state.upload_lock:
        expire_files()
        for file in files:
            if file.size is None or file.size > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Arquivo excede o limite permitido")
        size = sum(file.size for file in files)
        used = sum(len(file["content"]) for file in db.values())
        if used + size > app.state.storage_limit:
            raise HTTPException(status_code=413, detail="Limite de memória para arquivos atingido. Aguarde a expiração dos arquivos e tente novamente.")
        if psutil.virtual_memory().available < MEMORY_RESERVE_BYTES + 2 * size:
            raise HTTPException(status_code=503, detail="Pouca memória disponível no computador. Tente novamente mais tarde.")
        pending = {}
        for file in files:
            pending[uuid4().hex] = {
                "filename": file.filename or "arquivo",
                "content": await read_upload(file),
            }
        # Os dois minutos começam quando o lote inteiro está disponível.
        deadline = monotonic() + FILE_TTL_SECONDS
        for file in pending.values():
            file["expires_at"] = deadline
        db.update(pending)
        catalog.record(files=[file_metadata(key, file) for key, file in pending.items()])
        notify_clients()
    return {"filenames": [file.filename for file in files]}


@app.get("/events/")
async def file_events():
    async def events():
        queue = asyncio.Queue(maxsize=1)
        subscribers.add(queue)
        try:
            # Uma nova conexão também sincroniza arquivos enviados enquanto estava offline.
            yield "data: files_changed\n\n"
            while True:
                try:
                    await asyncio.wait_for(queue.get(), timeout=15)
                    yield "data: files_changed\n\n"
                except TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            subscribers.discard(queue)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


PREVIEW_TYPES = {
    ".xlsx": (
        "spreadsheet",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    ".xlsm": ("spreadsheet", "application/vnd.ms-excel.sheet.macroEnabled.12"),
    ".xls": ("spreadsheet", "application/vnd.ms-excel"),
    ".csv": ("spreadsheet", "text/csv"),
    ".tsv": ("spreadsheet", "text/tab-separated-values"),
    ".pdf": ("pdf", "application/pdf"),
    ".png": ("image", "image/png"),
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".gif": ("image", "image/gif"),
    ".webp": ("image", "image/webp"),
    ".avif": ("image", "image/avif"),
    ".mp4": ("video", "video/mp4"),
    ".webm": ("video", "video/webm"),
    ".mp3": ("audio", "audio/mpeg"),
    ".wav": ("audio", "audio/wav"),
    ".ogg": ("audio", "audio/ogg"),
    ".m4a": ("audio", "audio/mp4"),
}
for extension in (
    ".txt",
    ".md",
    ".json",
    ".log",
    ".py",
    ".js",
    ".css",
    ".html",
    ".xml",
    ".svg",
    ".yml",
    ".yaml",
):
    PREVIEW_TYPES[extension] = ("text", "text/plain")


def preview_type(filename):
    return PREVIEW_TYPES.get(Path(filename).suffix.lower(), (None, None))


def ranged_response(request: Request, content: bytes, media_type: str, headers: dict):
    total = len(content)
    headers = {**headers, "Accept-Ranges": "bytes"}
    range_header = request.headers.get("range")
    if range_header is None:
        headers["Content-Length"] = str(total)
        return Response(content=content, media_type=media_type, headers=headers)
    try:
        units, _, range_spec = range_header.partition("=")
        start_text, _, end_text = range_spec.partition("-")
        if units != "bytes" or (start_text == "" and end_text == ""):
            raise ValueError
        if start_text == "":
            start = max(total - int(end_text), 0)
            end = total - 1
        else:
            start = int(start_text)
            end = min(int(end_text), total - 1) if end_text else total - 1
        if start > end or start >= total:
            raise ValueError
    except ValueError:
        raise HTTPException(
            status_code=416,
            detail="Intervalo inválido",
            headers={"Content-Range": f"bytes */{total}"},
        )
    headers["Content-Range"] = f"bytes {start}-{end}/{total}"
    headers["Content-Length"] = str(end - start + 1)
    return Response(
        content=content[start : end + 1],
        media_type=media_type,
        headers=headers,
        status_code=206,
    )


@app.get("/preview/{file_id}/pdf")
async def preview_pdf(file_id: str, page: Annotated[int, Query(ge=1)] = 1):
    file = db.get(file_id)
    if file is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    if preview_type(file["filename"])[0] != "pdf":
        raise HTTPException(status_code=415, detail="Este arquivo não é um PDF")
    cache_key = (file_id, page)
    cached = pdf_render_cache.get(cache_key)
    if cached is None:
        if len(file["content"]) > MAX_INPUT_BYTES:
            raise HTTPException(413, "Prévia limitada a arquivos de até 32 MiB. Baixe o original.")
        cached = await app.state.preview_jobs.run((file_id, "pdf", page), "pdf", file["content"], (page,))
        expire_files()
        if file_id not in db:
            raise HTTPException(404, "Arquivo expirado")
        pdf_render_cache[cache_key] = cached
        cache_limit = min(64 * 1024 * 1024, app.state.storage_limit // 8)
        while pdf_render_cache and (
            len(pdf_render_cache) > PDF_RENDER_CACHE_SIZE
            or sum(memory_size(key) + memory_size(value) for key, value in pdf_render_cache.items()) > cache_limit
        ):
            pdf_render_cache.popitem(last=False)
    else:
        pdf_render_cache.move_to_end(cache_key)
    content, pages = cached
    return Response(
        content,
        media_type="image/png",
        headers={
            "X-PDF-Pages": str(pages),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/preview/{file_id}/table")
async def preview_table(
    file_id: str,
    sheet: Annotated[int, Query(ge=0)] = 0,
    offset: Annotated[int, Query(ge=0)] = 0,
    delimiter: str = "auto",
    header: bool = False,
):
    file = db.get(file_id)
    if file is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    if preview_type(file["filename"])[0] != "spreadsheet":
        raise HTTPException(status_code=415, detail="Este arquivo não é uma planilha")
    if delimiter not in ("auto", ",", ";", "\t", "|"):
        raise HTTPException(status_code=422, detail="Separador inválido")
    index = await indexed_preview(file_id, file, "table", (file["filename"], delimiter))
    return table_page(index, sheet, offset, header)


@app.get("/preview/{file_id}")
async def preview_file(file_id: str, request: Request):
    file = db.get(file_id)
    if file is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    kind, media_type = preview_type(file["filename"])
    if kind is None:
        raise HTTPException(
            status_code=415, detail="Prévia indisponível para este formato"
        )
    content = file["content"]
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "sandbox; default-src 'none'",
        "Cache-Control": "no-store",
    }
    if kind == "text":
        # Limita a prévia, mantendo o download original completo.
        headers["X-Preview-Truncated"] = str(len(content) > 100_000).lower()
        content = content[:100_000].decode("utf-8-sig", errors="replace")
        return Response(content=content, media_type=media_type, headers=headers)
    # Vídeo e áudio precisam de intervalos parciais para permitir busca (seek).
    return ranged_response(request, content, media_type, headers)


def file_metadata(file_id, file):
    return {"id": file_id, "filename": file["filename"],
            "size": len(file["content"]), "preview": preview_type(file["filename"])[0]}


@app.get("/files/")
async def list_files():
    return [file_metadata(key, file) for key, file in db.items()]


@app.get("/sync/")
async def synchronize(since: Annotated[int | None, Query(ge=0)] = None, epoch: str = ""):
    return catalog.read(since, epoch,
                        (file_metadata(key, file) for key, file in db.items()), links.values())


@app.get("/download/{file_id}")
async def download_file(file_id: str, request: Request):
    file = db.get(file_id)
    if file is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file['filename'], safe='')}"
    }
    return ranged_response(request, file["content"], "application/octet-stream", headers)


@app.get("/")
async def main():
    return FileResponse(INDEX_PATH)
