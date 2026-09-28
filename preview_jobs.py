"""Prévia isolada: fila limitada, deduplicação e encerramento real no timeout."""
import asyncio
import multiprocessing
import pickle
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import HTTPException

MAX_RESULT_BYTES = 32 * 1024 * 1024


def preview_worker(kind, source, result, options):
    try:
        content = Path(source).read_bytes()
        if kind == "pdf":
            from pdf_preview import render_pdf
            value = render_pdf(content, *options)
        elif kind == "outline":
            from pdf_preview import read_pdf_outline
            value = read_pdf_outline(content)
        elif kind == "table":
            from tabular_preview import build_table_index
            value = build_table_index(content, *options)
        else:
            raise ValueError("Operação desconhecida")
        payload = (200, value)
    except HTTPException as error:
        payload = (error.status_code, error.detail)
    except Exception:
        payload = (422, "Não foi possível processar esta prévia. Baixe o original.")
    # Arquivo privado local, produzido exclusivamente pelo processo filho.
    Path(result).write_bytes(pickle.dumps(payload, protocol=5))


async def run_process(kind, content, options, timeout=10, worker=preview_worker):
    with TemporaryDirectory(prefix="fileshare-preview-") as folder:
        source = Path(folder) / "source"
        result = Path(folder) / "result"
        await asyncio.to_thread(source.write_bytes, content)
        process = multiprocessing.get_context("spawn").Process(
            target=worker, args=(kind, str(source), str(result), options), daemon=True,
        )
        started = False
        try:
            process.start()
            started = True
            async with asyncio.timeout(timeout):
                while process.is_alive():
                    await asyncio.sleep(0.025)
            if process.exitcode != 0 or not result.exists():
                raise HTTPException(422, "O processo de prévia falhou. Baixe o original.")
            if result.stat().st_size > MAX_RESULT_BYTES:
                raise HTTPException(413, "Prévia excedeu o limite de memória. Baixe o original.")
            status, value = pickle.loads(await asyncio.to_thread(result.read_bytes))
            if status != 200:
                raise HTTPException(status, value)
            return value
        except TimeoutError:
            raise HTTPException(504, "A prévia excedeu 10 segundos. Baixe o arquivo original.")
        finally:
            if started:
                if process.is_alive():
                    process.terminate()
                await asyncio.to_thread(process.join, 1)
                if process.is_alive():
                    process.kill()
                    await asyncio.to_thread(process.join)
                process.close()


class PreviewJobs:
    def __init__(self, workers=2, capacity=8, timeout=10):
        self.slots = asyncio.Semaphore(workers)
        self.capacity = capacity
        self.timeout = timeout
        self.pending = {}

    async def run(self, key, kind, content, options=()):
        task = self.pending.get(key)
        if task is None:
            if len(self.pending) >= self.capacity:
                raise HTTPException(503, "Fila de prévias cheia. Tente novamente em instantes.")
            task = asyncio.create_task(self._run(kind, content, options))
            self.pending[key] = task
            def finished(done):
                self.pending.pop(key, None)
                if not done.cancelled():
                    done.exception()  # recupera exceções mesmo sem clientes conectados
            task.add_done_callback(finished)
        return await asyncio.shield(task)

    async def _run(self, kind, content, options):
        try:
            await asyncio.wait_for(self.slots.acquire(), self.timeout)
        except TimeoutError:
            raise HTTPException(503, "Tempo de espera da prévia excedido. Tente novamente.")
        try:
            return await run_process(kind, content, options, self.timeout)
        finally:
            self.slots.release()

    async def close(self):
        tasks = list(self.pending.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.pending.clear()
