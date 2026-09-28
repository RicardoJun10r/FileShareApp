"""Renderizador distribuído com o aplicativo, sem executáveis no PATH."""

from io import BytesIO
from threading import Lock

import pypdfium2 as pdfium
from fastapi import HTTPException

# PDFium não permite chamadas concorrentes, mesmo em documentos diferentes.
_pdfium_lock = Lock()


def render_pdf(content: bytes, page: int):
    with _pdfium_lock:
        try:
            with pdfium.PdfDocument(content) as document:
                pages = len(document)
                if not 1 <= page <= pages:
                    raise HTTPException(status_code=404, detail="Página não encontrada")
                pdf_page = document[page - 1]
                bitmap = None
                try:
                    width, height = pdf_page.get_size()
                    if max(width, height) <= 0:
                        raise ValueError("Página sem dimensões")
                    bitmap = pdf_page.render(scale=1500 / max(width, height))
                    image = bitmap.to_pil()
                    try:
                        output = BytesIO()
                        image.save(output, format="PNG")
                        return output.getvalue(), pages
                    finally:
                        image.close()
                finally:
                    if bitmap is not None:
                        bitmap.close()
                    pdf_page.close()
        except HTTPException:
            raise
        except (pdfium.PdfiumError, ValueError, RuntimeError) as error:
            raise HTTPException(
                status_code=422,
                detail="PDF inválido ou protegido por senha. Baixe para abri-lo",
            ) from error


def read_pdf_outline(content: bytes):
    with _pdfium_lock:
        try:
            with pdfium.PdfDocument(content) as document:
                count = len(document)
                if count > 10_000:
                    raise HTTPException(413, "PDF excede 10.000 páginas para o sumário. Baixe o original.")
                items = []
                for bookmark in document.get_toc():
                    if len(items) >= 10_000:
                        break
                    dest = bookmark.get_dest()
                    page = dest.get_index() if dest else None
                    if page is not None and 0 <= page < count:
                        items.append(
                            {
                                "title": bookmark.get_title()[:1000],
                                "page": page + 1,
                                "level": bookmark.level,
                            }
                        )
                source = "bookmarks" if items else "pages"
                if not items:
                    items = [
                        {"title": f"Página {page + 1}", "page": page + 1, "level": 0}
                        for page in range(count)
                    ]
                return {"pages": count, "source": source, "items": items}
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(
                status_code=422, detail="Não foi possível ler o sumário deste PDF"
            ) from error
