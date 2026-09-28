import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

import main


class StorageLimitsTest(unittest.TestCase):
    def setUp(self):
        self.before = dict(main.db)
        main.db.clear()
        main.pdf_render_cache.clear()

    def tearDown(self):
        main.db.clear()
        main.db.update(self.before)
        main.pdf_render_cache.clear()

    def test_budget_is_fixed_at_startup(self):
        mib = 1024 * 1024
        self.assertEqual(main.memory_budget(128 * mib), 0)
        self.assertEqual(main.memory_budget(1024 * mib), 256 * mib)
        self.assertEqual(main.memory_budget(8192 * mib), 512 * mib)
        with patch('main.psutil.virtual_memory', return_value=SimpleNamespace(available=1024*mib)) as memory:
            with TestClient(main.app) as client:
                self.assertEqual(client.get('/storage/').json()['limit'], 256*mib)
                memory.return_value = SimpleNamespace(available=8192*mib)
                self.assertEqual(client.get('/storage/').json()['limit'], 256*mib)

    def test_concurrent_batches_cannot_overbook(self):
        with TestClient(main.app) as client:
            main.app.state.storage_limit = 10
            def upload(_):
                return client.post('/upload/', files={'files': ('file.txt', b'123456')}).status_code
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(sorted(pool.map(upload, range(2))), [200, 413])
            self.assertEqual(client.get('/storage/').json()['used'], 6)

    def test_oversized_batch_and_low_memory_leave_storage_unchanged(self):
        with TestClient(main.app) as client:
            main.app.state.storage_limit = 10
            response = client.post('/upload/', files=[
                ('files', ('one.txt', b'123456')), ('files', ('two.txt', b'123456'))])
            self.assertEqual(response.status_code, 413)
            self.assertEqual(main.db, {})
            with patch('main.psutil.virtual_memory', return_value=SimpleNamespace(available=1)):
                self.assertEqual(client.post('/upload/', files={'files': ('a', b'a')}).status_code, 503)
            self.assertEqual(main.db, {})

    def test_expiration_blocks_all_file_routes_and_reclaims_quota(self):
        with patch('main.monotonic', return_value=100) as clock:
            with TestClient(main.app) as client:
                main.app.state.storage_limit = 3
                client.post('/upload/', files={'files': ('file.pdf', b'abc')}).raise_for_status()
                file_id = next(iter(main.db))
                main.pdf_render_cache[(file_id, 1)] = (b'image', 1)
                clock.return_value = 219.99
                self.assertEqual(client.get('/download/' + file_id).status_code, 200)
                clock.return_value = 220
                for path in (f'/download/{file_id}', f'/preview/{file_id}',
                             f'/preview/{file_id}/pdf', f'/preview/{file_id}/outline',
                             f'/preview/{file_id}/table'):
                    self.assertEqual(client.get(path).status_code, 404)
                self.assertEqual(client.get('/files/').json(), [])
                self.assertEqual(main.pdf_render_cache, {})
                self.assertEqual(client.post('/upload/', files={'files': ('new', b'abc')}).status_code, 200)

    def test_background_expiration_notifies_without_requests(self):
        with patch('main.monotonic', return_value=100) as clock:
            with TestClient(main.app) as client:
                client.post('/upload/', files={'files': ('file.txt', b'abc')}).raise_for_status()
                notified = Event()
                with patch('main.notify_clients', side_effect=notified.set):
                    clock.return_value = 220
                    self.assertTrue(notified.wait(3), 'Limpeza não notificou os clientes')
                    self.assertEqual(main.db, {})
