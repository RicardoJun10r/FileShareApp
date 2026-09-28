import asyncio
import multiprocessing
import os
import pickle
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from preview_jobs import PreviewJobs, run_process
from preview_cache import PreviewCache, memory_size


def sleeping_worker(kind, source, result, options):
    time.sleep(30)


def crashing_worker(kind, source, result, options):
    os._exit(1)


def pid_worker(kind, source, result, options):
    Path(result).write_bytes(pickle.dumps((200, os.getpid())))


class PreviewJobsTest(unittest.IsolatedAsyncioTestCase):
    async def test_process_isolation_timeout_cleanup_and_recovery(self):
        before = {child.pid for child in multiprocessing.active_children()}
        pid = await run_process('test', b'', (), worker=pid_worker)
        self.assertNotEqual(pid, os.getpid())
        with self.assertRaises(HTTPException) as error:
            await run_process('test', b'', (), timeout=0.1, worker=sleeping_worker)
        self.assertEqual(error.exception.status_code, 504)
        self.assertEqual({child.pid for child in multiprocessing.active_children()}, before)
        with self.assertRaises(HTTPException) as error:
            await run_process('test', b'', (), worker=crashing_worker)
        self.assertEqual(error.exception.status_code, 422)
        self.assertNotEqual(await run_process('test', b'', (), worker=pid_worker), os.getpid())

    async def test_duplicate_requests_share_job_and_one_cancel_does_not_cancel_others(self):
        jobs = PreviewJobs(capacity=1)
        started, release = asyncio.Event(), asyncio.Event()
        async def work(*args):
            started.set()
            await release.wait()
            return b'png', 2
        with patch('preview_jobs.run_process', side_effect=work) as run:
            first = asyncio.create_task(jobs.run(('id', 1), 'pdf', b'pdf', (1,)))
            await started.wait()
            second = asyncio.create_task(jobs.run(('id', 1), 'pdf', b'pdf', (1,)))
            await asyncio.sleep(0)
            first.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await first
            with self.assertRaises(HTTPException) as error:
                await jobs.run(('id', 2), 'pdf', b'pdf', (2,))
            self.assertEqual(error.exception.status_code, 503)
            release.set()
            self.assertEqual(await second, (b'png', 2))
            run.assert_awaited_once()
        await jobs.close()

    async def test_shutdown_cancels_pending_jobs(self):
        jobs = PreviewJobs()
        started = asyncio.Event()
        async def work(*args):
            started.set()
            await asyncio.Event().wait()
        with patch('preview_jobs.run_process', side_effect=work):
            task = asyncio.create_task(jobs.run(('id', 1), 'pdf', b''))
            await started.wait()
            await jobs.close()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertEqual(jobs.pending, {})


class PreviewCacheTest(unittest.TestCase):
    def test_lru_memory_limit_and_expiration(self):
        value = b'x' * 500
        key = ('a', 1)
        size = memory_size(value) + memory_size(key)
        cache = PreviewCache(size * 2)
        cache.put(key, value)
        cache.put(('b', 1), value)
        self.assertEqual(cache.get(key), value)
        cache.put(('c', 1), value)
        self.assertIsNone(cache.get(('b', 1)))
        self.assertLessEqual(cache.used, cache.limit)
        cache.put(('large', 1), b'x' * (size * 3))
        self.assertIsNone(cache.get(('large', 1)))
        cache.discard_file('a')
        self.assertIsNone(cache.get(key))
