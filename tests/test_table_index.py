import unittest
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
import main
import tabular_preview as tables
from test_tabular_preview import xlsx_fixture


class TableIndexTest(unittest.TestCase):
    def test_csv_multiline_and_late_encoding_fallback(self):
        raw = ('Name;Value\n' + 'ascii;x\n' * 10000 + 'João;"line\nnext"').encode('cp1252')
        with patch.object(tables, 'MAX_ROWS', 20000):
            index = tables.build_table_index(raw, 'file.csv', ';')
        self.assertIn('cp1252', index['tables'][0]['notes'][0])
        self.assertEqual(tables.table_page(index, offset=10000, header=True)['rows'], [['João', 'line\nnext']])

    def test_input_expansion_row_and_memory_limits(self):
        with patch.object(tables, 'MAX_INPUT_BYTES', 2):
            with self.assertRaises(HTTPException) as error:
                tables.build_table_index(b'a,b', 'file.csv')
            self.assertEqual(error.exception.status_code, 413)
        with patch.object(tables, 'MAX_EXPANDED_BYTES', 1):
            with self.assertRaises(HTTPException) as error:
                tables.build_table_index(xlsx_fixture(), 'file.xlsx')
            self.assertEqual(error.exception.status_code, 413)
        with patch.object(tables, 'MAX_ROWS', 3):
            index = tables.build_table_index(b'a\nb\nc\nd', 'file.csv')
            self.assertEqual(len(index['tables'][0]['rows']), 3)
            self.assertIn('Prévia parcial', index['tables'][0]['notes'][-1])
        with patch.object(tables, 'MAX_INDEX_BYTES', 2000):
            index = tables.build_table_index(('x'*100 + '\n') .encode() * 100, 'file.csv')
            self.assertLess(len(index['tables'][0]['rows']), 100)

    def test_paging_and_header_changes_reuse_one_index(self):
        before = set(main.db)
        try:
            with TestClient(main.app) as client:
                client.post('/upload/', files={'files': ('data.csv', b'a;b\n' + b'1;2\n'*105)}).raise_for_status()
                file_id = next(iter(set(main.db) - before))
                url = f'/preview/{file_id}/table'
                with patch.object(main.app.state.preview_jobs, 'run', wraps=main.app.state.preview_jobs.run) as run:
                    first = client.get(url, params={'header': True}).json()
                    second = client.get(url, params={'header': True, 'offset': 100}).json()
                    raw = client.get(url).json()
                    self.assertEqual(first['headers'], ['a', 'b'])
                    self.assertEqual(len(second['rows']), 5)
                    self.assertEqual(raw['rows'][0], ['a', 'b'])
                    run.assert_awaited_once()
        finally:
            for key in set(main.db) - before:
                main.db.pop(key)

    def test_expiration_during_indexing_does_not_restore_cache(self):
        before = set(main.db)
        try:
            with patch('main.monotonic', return_value=100) as clock:
                with TestClient(main.app) as client:
                    client.post('/upload/', files={'files': ('data.csv', b'a,b')}).raise_for_status()
                    file_id = next(iter(set(main.db) - before))
                    async def finish_after_expiration(*args):
                        clock.return_value = 220
                        return {'sheets': ['data.csv'], 'tables': [{'rows': [['a', 'b']], 'notes': []}]}
                    with patch.object(main.app.state.preview_jobs, 'run', side_effect=finish_after_expiration):
                        self.assertEqual(client.get(f'/preview/{file_id}/table').status_code, 404)
                    self.assertEqual(main.app.state.preview_cache.used, 0)
                    self.assertNotIn(file_id, main.db)
        finally:
            for key in set(main.db) - before:
                main.db.pop(key)
