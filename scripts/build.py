"""Build nativo: execute com uv run --group build python scripts/build.py."""
import importlib.metadata
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
subprocess.run([
    sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
    '--name', 'FileShare', '--console', '--noupx',
    '--add-data', 'static:static', '--add-data', 'pyproject.toml:.',
    '--collect-all', 'pypdfium2', '--collect-all', 'pypdfium2_raw',
    '--collect-submodules', 'uvicorn', 'launcher.py',
], cwd=ROOT, check=True)
package = ROOT / 'dist' / 'FileShare'
shutil.copy2(ROOT / 'packaging/LEIA-ME.txt', package / 'LEIA-ME.txt')
# Preserva avisos de licença das dependências distribuídas.
licenses = package / 'THIRD_PARTY_LICENSES'
licenses.mkdir(exist_ok=True)
for distribution in importlib.metadata.distributions():
    name = distribution.metadata['Name']
    for file in distribution.files or []:
        if any(word in str(file).lower() for word in ('license', 'copying', 'notice')):
            source = Path(distribution.locate_file(file))
            if source.is_file():
                target = licenses / name / str(file).replace('..', '_')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
if sys.platform == 'darwin':
    start = package / 'Iniciar FileShare.command'
    start.write_text('#!/bin/sh\ncd "$(dirname "$0")"\nexec ./FileShare\n')
    start.chmod(0o755)
system = {'win32':'windows','darwin':'macos'}.get(sys.platform, 'linux')
arch = {'amd64':'x86_64','aarch64':'arm64'}.get(platform.machine().lower(), platform.machine().lower())
name = f'FileShare-{version}-{system}-{arch}'
if system == 'windows':
    archive = ROOT / 'dist' / f'{name}.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for path in package.rglob('*'):
            if path.is_file():
                z.write(path, path.relative_to(package.parent))
else:
    archive = ROOT / 'dist' / f'{name}.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        tar.add(package, arcname='FileShare')
print(f'Pacote criado: {archive}', flush=True)
