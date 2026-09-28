"""Extrai o pacote e testa o executável fora do projeto, sem Python/Poppler no PATH."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from test_pdf_links import sample_pdf
from test_tabular_preview import xlsx_fixture

parser = argparse.ArgumentParser()
parser.add_argument('archive', nargs='?')
args = parser.parse_args()
archives = list((ROOT / 'dist').glob('FileShare-*.zip')) + list((ROOT / 'dist').glob('FileShare-*.tar.gz'))
archive = Path(args.archive).resolve() if args.archive else archives[0]
http = build_opener(ProxyHandler({}))
with tempfile.TemporaryDirectory(prefix='fileshare-package-') as directory:
    root = Path(directory)
    shutil.unpack_archive(str(archive), str(root))
    executable = root / 'FileShare' / ('FileShare.exe' if os.name == 'nt' else 'FileShare')
    work = root / 'empty-working-directory'
    work.mkdir()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    url = f'http://127.0.0.1:{port}'
    env = dict(os.environ)
    for name in ('PYTHONPATH', 'PYTHONHOME', 'FILESHARE_PUBLIC_URL'):
        env.pop(name, None)
    env['PATH'] = str(work)
    with (root / 'run.log').open('w+') as log:
        process = subprocess.Popen([str(executable), '--host', '127.0.0.1', '--port', str(port), '--no-browser'], cwd=work, env=env, stdout=log, stderr=log)
        try:
            for _ in range(200):
                if process.poll() is not None:
                    log.seek(0)
                    raise RuntimeError(log.read())
                try:
                    with http.open(url, timeout=1) as response:
                        assert response.status == 200
                        break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError('Executável não iniciou em 20 segundos')
            for path in ('/static/styles.css', '/static/app.js', '/static/favicon.svg', '/static/vendor/bootstrap/bootstrap.min.css'):
                with http.open(url + path) as response:
                    assert response.status == 200, path
            with http.open(url + '/connection/') as response:
                info = json.load(response)
                assert info['url'] == url + '/'
                assert info['qr'].startswith('data:image/png;base64,')
            def upload(name, data):
                boundary = 'fileshare-smoke-boundary'
                body = (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode() + data + f'\r\n--{boundary}--\r\n'.encode()
                with http.open(Request(url + '/upload/', data=body, headers={'Content-Type':f'multipart/form-data; boundary={boundary}'})) as response:
                    assert response.status == 200
                with http.open(url + '/files/') as response:
                    return json.load(response)[-1]['id']
            pdf = sample_pdf()
            pdf_id = upload('sample.pdf', pdf)
            with http.open(url + f'/preview/{pdf_id}/pdf?page=2') as response:
                assert response.read().startswith(b'\x89PNG')
                assert response.headers['X-PDF-Pages'] == '2'
            with http.open(url + f'/preview/{pdf_id}/outline') as response:
                assert json.load(response)['pages'] == 2
            with http.open(url + f'/download/{pdf_id}') as response:
                assert response.read() == pdf
            sheet = upload('sample.xlsx', xlsx_fixture())
            with http.open(url + f'/preview/{sheet}/table') as response:
                assert json.load(response)['rows'][0][0] == '00123'
            csv = upload('sample.csv', b'Name;Value\nTest;123')
            with http.open(url + f'/preview/{csv}/table?header=true') as response:
                assert json.load(response)['rows'] == [['Test', '123']]
            with http.open(Request(url + '/links/', data=b'{"url":"https://example.com","title":"Smoke"}', headers={'Content-Type':'application/json'})) as response:
                assert response.status == 201
            log.flush()
            print(f'PASS {archive.name}: inicialização, recursos locais, QR, PDF, sumário, download, XLSX, CSV e links; PATH sem ferramentas externas.')
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
