"""Teste de integração com conexões HTTP reais e dois clientes de eventos."""

import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path
from urllib.request import urlopen

import httpx


class RealtimeTest(unittest.TestCase):
    def test_upload_notifies_all_clients_and_reconnect_syncs(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            with httpx.Client(base_url=base, timeout=5, trust_env=False) as client:
                for _ in range(100):
                    try:
                        client.get("/").raise_for_status()
                        break
                    except httpx.TransportError:
                        if process.poll() is not None:
                            self.fail("Servidor encerrou antes de iniciar")
                        time.sleep(0.05)
                else:
                    self.fail("Servidor não iniciou")

                self.assertEqual(client.get("/files/").json(), [])
                with (
                    urlopen(base + "/events/", timeout=5) as first,
                    urlopen(base + "/events/", timeout=5) as second,
                ):
                    for stream in (first, second):
                        self.assertIn(
                            "text/event-stream", stream.headers["Content-Type"]
                        )
                        self.assertEqual(stream.readline(), b"data: files_changed\n")
                        self.assertEqual(stream.readline(), b"\n")
                    response = client.post(
                        "/upload/",
                        files=[
                            ("files", ("ação.txt", b"first")),
                            ("files", ("ação.txt", b"second")),
                        ],
                    )
                    self.assertEqual(response.status_code, 200)
                    for stream in (first, second):
                        self.assertEqual(stream.readline(), b"data: files_changed\n")
                        self.assertEqual(stream.readline(), b"\n")
                    shared = client.post(
                        "/links/",
                        json={
                            "url": "https://example.com",
                            "title": "Link em tempo real",
                        },
                    )
                    self.assertEqual(shared.status_code, 201)
                    for stream in (first, second):
                        self.assertEqual(stream.readline(), b"data: files_changed\n")
                        self.assertEqual(stream.readline(), b"\n")
                    self.assertIn(shared.json(), client.get("/links/").json())
                    files = client.get("/files/").json()
                    self.assertEqual(len(files), 2)
                    self.assertNotEqual(files[0]["id"], files[1]["id"])
                    for file, expected in zip(files, [b"first", b"second"]):
                        self.assertEqual(
                            client.get("/download/" + file["id"]).content, expected
                        )

                client.post(
                    "/upload/", files={"files": ("offline.txt", b"offline")}
                ).raise_for_status()
                with urlopen(base + "/events/", timeout=5) as reconnected:
                    self.assertEqual(reconnected.readline(), b"data: files_changed\n")
                    self.assertEqual(len(client.get("/files/").json()), 3)
                self.assertEqual(client.get("/download/missing").status_code, 404)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    unittest.main()
