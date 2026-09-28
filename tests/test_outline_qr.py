import base64
import unittest
from io import BytesIO
from unittest.mock import patch

import qrcode
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfWriter

from main import app, db


class OutlineQrTest(unittest.TestCase):
    def test_nested_outline_and_page_fallback(self):
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=200)
        writer.add_blank_page(width=300, height=200)
        parent = writer.add_outline_item("Introdução", 0)
        writer.add_outline_item("Detalhes", 1, parent=parent)
        with TestClient(app) as client:
            for bookmarks in (True, False):
                output = BytesIO()
                if not bookmarks:
                    writer = PdfWriter()
                    writer.add_blank_page(width=300, height=200)
                writer.write(output)
                client.post(
                    "/upload/", files={"files": ("sumario.pdf", output.getvalue())}
                ).raise_for_status()
                file_id = client.get("/files/").json()[-1]["id"]
                try:
                    response = client.get(f"/preview/{file_id}/outline")
                    self.assertEqual(response.status_code, 200)
                    data = response.json()
                    if bookmarks:
                        self.assertEqual(data["source"], "bookmarks")
                        self.assertEqual(
                            data["items"],
                            [
                                {"title": "Introdução", "page": 1, "level": 0},
                                {"title": "Detalhes", "page": 2, "level": 1},
                            ],
                        )
                    else:
                        self.assertEqual(data["source"], "pages")
                        self.assertEqual(data["items"][0]["page"], 1)
                finally:
                    db.pop(file_id)
            self.assertEqual(client.get("/preview/missing/outline").status_code, 404)

    def test_qr_encodes_network_address(self):
        with patch.dict("os.environ", {}, clear=True):
            with TestClient(app, base_url="http://192.168.15.15:8000") as client:
                with patch("main.qrcode.make", wraps=qrcode.make) as make:
                    result = client.get("/connection/").json()
                    self.assertEqual(result["url"], "http://192.168.15.15:8000/")
                    make.assert_called_once_with(result["url"])
                    image = Image.open(
                        BytesIO(base64.b64decode(result["qr"].split(",")[1]))
                    )
                    self.assertEqual(image.format, "PNG")
                    self.assertEqual(image.width, image.height)
            with TestClient(app, base_url="http://localhost:8000") as client:
                with patch("main.socket") as socket_module:
                    socket_module.socket.return_value.__enter__.return_value.getsockname.return_value = (
                        "192.168.15.15",
                        40000,
                    )
                    self.assertEqual(
                        client.get("/connection/").json()["url"],
                        "http://192.168.15.15:8000/",
                    )
            with (
                patch.dict(
                    "os.environ", {"FILESHARE_PUBLIC_URL": "https://files.example.com/"}
                ),
                TestClient(app) as client,
            ):
                self.assertEqual(
                    client.get("/connection/").json()["url"],
                    "https://files.example.com/",
                )
