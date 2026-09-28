import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import main
from catalog_sync import CatalogChanges


class CatalogSyncTest(unittest.TestCase):
    def test_delta_upload_links_expiration_and_no_changes(self):
        before, links_before = set(main.db), set(main.links)
        try:
            with patch('main.monotonic', return_value=100) as clock:
                with TestClient(main.app) as client:
                    initial = client.get('/sync/').json()
                    self.assertTrue(initial['reset'])
                    params = {'since': initial['revision'], 'epoch': initial['epoch']}
                    client.post('/upload/', files={'files': ('new.txt', b'abc')}).raise_for_status()
                    delta = client.get('/sync/', params=params).json()
                    self.assertFalse(delta['reset'])
                    self.assertEqual([file['filename'] for file in delta['files']], ['new.txt'])
                    file_id = delta['files'][0]['id']
                    params['since'] = delta['revision']
                    empty = client.get('/sync/', params=params).json()
                    self.assertEqual(empty['files'], [])
                    client.post('/links/', json={'url': 'https://example.com', 'title': 'New'}).raise_for_status()
                    change = client.get('/sync/', params=params).json()
                    self.assertEqual(len(change['links']), 1)
                    self.assertEqual(change['files'], [])
                    params['since'] = change['revision']
                    clock.return_value = 220
                    expired = client.get('/sync/', params=params).json()
                    self.assertIn(file_id, expired['deleted'])
                    self.assertEqual(expired['files'], [])
        finally:
            for key in set(main.db) - before:
                main.db.pop(key)
            for key in set(main.links) - links_before:
                main.links.pop(key)

    def test_history_eviction_and_server_restart_force_snapshot(self):
        history = CatalogChanges(capacity=1)
        history.record(files=[{'id': 'a'}])
        history.record(deleted=['a'])
        self.assertTrue(history.read(0, history.epoch, [], [])['reset'])
        self.assertFalse(history.read(1, history.epoch, [], [])['reset'])
        self.assertTrue(history.read(2, 'other-server', [], [])['reset'])
        tiny = CatalogChanges(max_bytes=1)
        tiny.record(files=[{'id': 'a'}])
        self.assertEqual(tiny.used, 0)
        self.assertTrue(tiny.read(0, tiny.epoch, [{'id': 'a'}], [])['reset'])
