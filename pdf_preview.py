"""Renderizador distribuído com o aplicativo, sem executáveis no PATH."""
from io import BytesIO
from threading import Lock

from fastapi import HTTPException
import pypdfium2 as pdfium

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
            raise HTTPException(status_code=422, detail="PDF inválido ou protegido por senha. Baixe para abri-lo") from error
