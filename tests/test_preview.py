import unittest

from fastapi.testclient import TestClient

from main import app, db


class PreviewTest(unittest.TestCase):
    def test_preview_content_types_limits_and_fallback(self):
        with TestClient(app) as client:
            samples = [
                ("photo.png", b"\x89PNG\r\n\x1a\n", "image", "image/png"),
                ("movie.mp4", b"video", "video", "video/mp4"),
                ("sound.mp3", b"audio", "audio", "audio/mpeg"),
                ("page.html", b"<script>alert(1)</script>", "text", "text/plain"),
                ("large.txt", b"x" * 100_001, "text", "text/plain"),
                ("archive.zip", b"zip", None, None),
            ]
            uploaded = []
            try:
                for name, content, kind, mime in samples:
                    client.post(
                        "/upload/", files={"files": (name, content)}
                    ).raise_for_status()
                    file = client.get("/files/").json()[-1]
                    uploaded.append(file["id"])
                    self.assertEqual(file["preview"], kind)
                    response = client.get("/preview/" + file["id"])
                    if kind is None:
                        self.assertEqual(response.status_code, 415)
                    else:
                        self.assertEqual(response.status_code, 200)
                        self.assertTrue(
                            response.headers["content-type"].startswith(mime)
                        )
                        self.assertEqual(
                            response.headers["x-content-type-options"], "nosniff"
                        )
                        self.assertIn(
                            "sandbox", response.headers["content-security-policy"]
                        )
                        self.assertEqual(
                            response.content,
                            content[:100_000] if kind == "text" else content,
                        )
                        if name == "large.txt":
                            self.assertEqual(
                                response.headers["x-preview-truncated"], "true"
                            )
                    self.assertEqual(
                        client.get("/download/" + file["id"]).content, content
                    )
                self.assertEqual(client.get("/preview/nonexistent").status_code, 404)
            finally:
                for file_id in uploaded:
                    db.pop(file_id, None)
