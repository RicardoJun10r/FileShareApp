import asyncio
import base64
import ipaddress
import os
import re
import socket
import subprocess
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated
from urllib.parse import quote
from uuid import uuid4

import qrcode
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl
from pypdf import PdfReader

from tabular_preview import read_table

# Conteúdo em memória: os arquivos são perdidos ao reiniciar o servidor.
db = {}
links = {}
pdf_slots = asyncio.Semaphore(2)
subscribers: set[asyncio.Queue] = set()
app = FastAPI()
INDEX_PATH = Path(__file__).resolve().parent / "static" / "index.html"
app.mount("/static", StaticFiles(directory=INDEX_PATH.parent), name="static")
table_slots = asyncio.Semaphore(2)


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


def read_pdf_outline(content: bytes):
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError("encrypted")
        count = len(reader.pages)
        items = []

        def walk(entries, level=0):
            for entry in entries:
                if isinstance(entry, list):
                    walk(entry, level + 1)
                else:
                    page = reader.get_destination_page_number(entry)
                    if page is not None and 0 <= page < count:
                        items.append(
                            {
                                "title": str(entry.title),
                                "page": page + 1,
                                "level": level,
                            }
                        )

        walk(reader.outline)
        source = "bookmarks" if items else "pages"
        if not items:
            items = [
                {"title": f"Página {page + 1}", "page": page + 1, "level": 0}
                for page in range(count)
            ]
        return {"pages": count, "source": source, "items": items}
    except Exception as error:
        raise HTTPException(
            status_code=422, detail="Não foi possível ler o sumário deste PDF"
        ) from error


@app.get("/preview/{file_id}/outline")
async def pdf_outline(file_id: str):
    file = db.get(file_id)
    if file is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    if preview_type(file["filename"])[0] != "pdf":
        raise HTTPException(status_code=415, detail="Este arquivo não é um PDF")
    if "outline" not in file:
        async with pdf_slots:
            file["outline"] = await asyncio.to_thread(read_pdf_outline, file["content"])
    return file["outline"]


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
    notify_clients()
    return item


@app.get("/links/")
async def list_links():
    return list(links.values())


@app.post("/upload/")
async def upload_files(
    files: Annotated[
        list[UploadFile], File(description="Multiple files as UploadFile")
    ],
):
    for file in files:
        db[uuid4().hex] = {
            "filename": file.filename or "arquivo",
            "content": await file.read(),
        }
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


def render_pdf(content: bytes, page: int):
    # Arquivo temporário isolado; cada chamada renderiza apenas uma página.
    try:
        with TemporaryDirectory(prefix="fileshare-pdf-") as directory:
            source = Path(directory) / "source.pdf"
            source.write_bytes(content)
            info = subprocess.run(
                ["pdfinfo", str(source)],
                capture_output=True,
                timeout=15,
                check=True,
            )
            match = re.search(rb"(?m)^Pages:\s+(\d+)", info.stdout)
            if not match:
                raise HTTPException(
                    status_code=422, detail="Não foi possível ler as páginas do PDF"
                )
            pages = int(match.group(1))
            if page > pages:
                raise HTTPException(status_code=404, detail="Página não encontrada")
            output = Path(directory) / "page"
            subprocess.run(
                [
                    "pdftoppm",
                    "-f",
                    str(page),
                    "-l",
                    str(page),
                    "-singlefile",
                    "-scale-to",
                    "1500",
                    "-png",
                    str(source),
                    str(output),
                ],
                capture_output=True,
                timeout=30,
                check=True,
            )
            return output.with_suffix(".png").read_bytes(), pages
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Instale poppler-utils no servidor para visualizar PDFs",
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=422,
            detail="Este PDF demorou demais para renderizar. Baixe para abri-lo",
        )
    except subprocess.CalledProcessError:
        raise HTTPException(
            status_code=422,
            detail="PDF inválido ou protegido por senha. Baixe para abri-lo",
        )


@app.get("/preview/{file_id}/pdf")
async def preview_pdf(file_id: str, page: Annotated[int, Query(ge=1)] = 1):
    file = db.get(file_id)
    if file is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    if preview_type(file["filename"])[0] != "pdf":
        raise HTTPException(status_code=415, detail="Este arquivo não é um PDF")
    async with pdf_slots:
        content, pages = await asyncio.to_thread(render_pdf, file["content"], page)
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
    async with table_slots:
        return await asyncio.to_thread(
            read_table,
            file["content"],
            file["filename"],
            sheet,
            offset,
            delimiter,
            header,
        )


@app.get("/preview/{file_id}")
async def preview_file(file_id: str):
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


@app.get("/files/")
async def list_files():
    return [
        {
            "id": file_id,
            "filename": file["filename"],
            "size": len(file["content"]),
            "preview": preview_type(file["filename"])[0],
        }
        for file_id, file in db.items()
    ]


@app.get("/download/{file_id}")
async def download_file(file_id: str):
    file = db.get(file_id)
    if file is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return Response(
        content=file["content"],
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file['filename'], safe='')}"
        },
    )


@app.get("/")
async def main():
    return FileResponse(INDEX_PATH)
