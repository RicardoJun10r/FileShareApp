import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
import pdf_preview
from main import app, db, links, pdf_render_cache


def sample_pdf():
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 5 0 R >> >> /Contents 7 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for text in (b"Page one", b"Page two"):
        stream = b"BT /F1 24 Tf 30 100 Td (" + text + b") Tj ET"
        objects.append(
            b"<< /Length "
            + str(len(stream)).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
    result = b"%PDF-1.4\n"
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(result)
    result += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:
        result += f"{offset:010d} 00000 n \n".encode()
    result += f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return result


class PdfAndLinksTest(unittest.TestCase):
    def test_pdf_operations_share_lock_and_release_it_on_error(self):
        document_factory = pdf_preview.pdfium.PdfDocument

        def guarded_document(*args, **kwargs):
            self.assertTrue(pdf_preview._pdfium_lock.locked())
            return document_factory(*args, **kwargs)

        with patch.object(pdf_preview.pdfium, "PdfDocument", side_effect=guarded_document):
            for operation in (
                pdf_preview.read_pdf_outline,
                lambda content: pdf_preview.render_pdf(content, 1),
            ):
                with self.subTest(operation=operation):
                    operation(sample_pdf())
                    self.assertFalse(pdf_preview._pdfium_lock.locked())
                    with self.assertRaises(main.HTTPException) as error:
                        operation(b"invalid pdf")
                    self.assertEqual(error.exception.status_code, 422)
                    self.assertFalse(pdf_preview._pdfium_lock.locked())

    def test_upload_batch_is_atomic_and_notifies_only_after_success(self):
        before = dict(db)
        try:
            with (
                TestClient(app) as client,
                patch.object(main, "MAX_UPLOAD_BYTES", 10),
                patch.object(main, "notify_clients") as notify,
            ):
                response = client.post("/upload/", files=[
                    ("files", ("small.bin", b"a" * 5)),
                    ("files", ("big.bin", b"b" * 11)),
                ])
                self.assertEqual(response.status_code, 413)
                self.assertEqual(db, before)
                notify.assert_not_called()

                published = []
                notify.side_effect = lambda: published.append(set(db) - set(before))
                response = client.post("/upload/", files=[
                    ("files", ("small.bin", b"a" * 5)),
                    ("files", ("other.bin", b"b" * 10)),
                ])
                self.assertEqual(response.status_code, 200)
                added = set(db) - set(before)
                self.assertEqual(len(added), 2)
                self.assertEqual(published, [added])
                notify.assert_called_once()
                self.assertEqual(
                    {db[key]["filename"]: db[key]["content"] for key in added},
                    {"small.bin": b"a" * 5, "other.bin": b"b" * 10},
                )
        finally:
            for key in set(db) - set(before):
                db.pop(key)

    def test_pdf_pages_and_invalid_files(self):
        with TestClient(app) as client:
            original = sample_pdf()
            client.post(
                "/upload/", files={"files": ("sample.pdf", original)}
            ).raise_for_status()
            item = client.get("/files/").json()[-1]
            file_id = item["id"]
            try:
                self.assertEqual(item["preview"], "pdf")
                first = client.get(f"/preview/{file_id}/pdf?page=1")
                second = client.get(f"/preview/{file_id}/pdf?page=2")
                self.assertEqual(first.status_code, 200)
                self.assertEqual(second.status_code, 200)
                self.assertEqual(first.headers["x-pdf-pages"], "2")
                self.assertTrue(first.content.startswith(b"\x89PNG"))
                self.assertNotEqual(first.content, second.content)
                self.assertEqual(
                    client.get(f"/preview/{file_id}/pdf?page=3").status_code, 404
                )
                self.assertEqual(
                    client.get(f"/preview/{file_id}/pdf?page=0").status_code, 422
                )
                self.assertEqual(client.get(f"/download/{file_id}").content, original)
                db[file_id]["content"] = b"not a pdf"
                for key in [key for key in pdf_render_cache if key[0] == file_id]:
                    del pdf_render_cache[key]
                self.assertEqual(client.get(f"/preview/{file_id}/pdf").status_code, 422)
            finally:
                db.pop(file_id, None)

    def test_pdf_render_is_cached(self):
        with TestClient(app) as client:
            client.post(
                "/upload/", files={"files": ("cache.pdf", sample_pdf())}
            ).raise_for_status()
            file_id = client.get("/files/").json()[-1]["id"]
            try:
                with patch.object(app.state.preview_jobs, "run", wraps=app.state.preview_jobs.run) as render:
                    first = client.get(f"/preview/{file_id}/pdf?page=1")
                    second = client.get(f"/preview/{file_id}/pdf?page=1")
                    self.assertEqual(first.status_code, 200)
                    self.assertEqual(first.content, second.content)
                    render.assert_called_once()
            finally:
                db.pop(file_id, None)
                for key in [key for key in pdf_render_cache if key[0] == file_id]:
                    del pdf_render_cache[key]

    def test_upload_rejects_file_above_limit(self):
        with TestClient(app) as client:
            with patch.object(main, "MAX_UPLOAD_BYTES", 10):
                response = client.post(
                    "/upload/", files={"files": ("big.bin", b"x" * 11)}
                )
                self.assertEqual(response.status_code, 413)
                response = client.post(
                    "/upload/", files={"files": ("small.bin", b"x" * 10)}
                )
                self.assertEqual(response.status_code, 200)
                file_id = client.get("/files/").json()[-1]["id"]
                db.pop(file_id, None)

    def test_share_and_validate_links(self):
        with TestClient(app) as client:
            before = set(links)
            try:
                response = client.post(
                    "/links/",
                    json={"url": "https://example.com/test?q=1", "title": " Teste "},
                )
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()["title"], "Teste")
                self.assertIn(response.json(), client.get("/links/").json())
                response = client.post(
                    "/links/", json={"url": "http://192.168.15.15:8000"}
                )
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()["title"], response.json()["url"])
                for url in (
                    "javascript:alert(1)",
                    "data:text/html,test",
                    "file:///etc/passwd",
                    "not a url",
                    "https://user:pass@example.com",
                ):
                    self.assertEqual(
                        client.post("/links/", json={"url": url}).status_code, 422
                    )
            finally:
                for key in set(links) - before:
                    links.pop(key)
