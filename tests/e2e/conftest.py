"""Servidor real isolado por teste; nunca usa a instância pessoal da porta 8000."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(params=[320, 375, 390, 768, 1280], ids=lambda width: f'{width}px')
def screen_width(request):
    return request.param


@pytest.fixture
def browser_context_args(browser_context_args, screen_width):
    return {**browser_context_args, 'viewport': {'width': screen_width, 'height': 800},
            'is_mobile': screen_width < 500, 'has_touch': screen_width < 500}


@pytest.fixture
def app_url(tmp_path):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    url = f'http://127.0.0.1:{port}'
    env = {**os.environ, 'FILESHARE_PUBLIC_URL': url}
    with (tmp_path / 'server.log').open('w+') as log:
        process = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', str(port)],
            cwd=ROOT, env=env, stdout=log, stderr=log,
        )
        try:
            with httpx.Client(trust_env=False, timeout=1) as client:
                for _ in range(100):
                    if process.poll() is not None:
                        log.seek(0)
                        pytest.fail(log.read())
                    try:
                        if client.get(url + '/').status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(.05)
                else:
                    pytest.fail('Servidor E2E não iniciou em 5 segundos')
            yield url
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


@pytest.fixture(autouse=True)
def browser_errors(page):
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    yield
    assert not errors, f'Erros JavaScript: {errors}'
