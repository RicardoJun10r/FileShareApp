"""Inicializador de desktop e ponto de entrada do pacote PyInstaller."""

import multiprocessing

# Necessário antes dos imports do app também no executável PyInstaller.
if __name__ == "__main__":
    multiprocessing.freeze_support()

import argparse
import ipaddress
import os
import socket
import sys
import threading
import time
import tomllib
import webbrowser
from pathlib import Path

import uvicorn

from main import app


def network_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))  # escolhe a rota sem transmitir dados
            address = probe.getsockname()[0]
            if not ipaddress.ip_address(address).is_loopback:
                return address
    except OSError:
        pass
    return "127.0.0.1"


def bind_server(host, port):
    candidates = range(8000, 8011) if port is None else [port]
    for candidate in candidates:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Evita que outro processo compartilhe a porta no Windows.
            if os.name == "nt":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind((host, candidate))
            return sock
        except OSError:
            sock.close()
            if port is not None or candidate == 8010:
                raise


def open_when_ready(server, address, open_browser):
    while not server.started and not server.should_exit:
        time.sleep(0.05)
    if not server.started:
        return
    print(
        f"\nFileShare pronto!\nEndereço: {address}\n"
        "Conecte os dispositivos à mesma rede.\n"
        "Mantenha esta janela aberta. Para encerrar: Ctrl+C.\n",
        flush=True,
    )
    if open_browser:
        try:
            if not webbrowser.open(address):
                print(
                    "Não foi possível abrir o navegador. Abra o endereço acima manualmente.",
                    flush=True,
                )
        except Exception as error:
            print(
                f"Abra o endereço manualmente (navegador indisponível: {error}).",
                flush=True,
            )


def main():
    parser = argparse.ArgumentParser(
        description="FileShare: compartilhe arquivos na rede local."
    )
    version = tomllib.loads((Path(__file__).parent / "pyproject.toml").read_text())[
        "project"
    ]["version"]
    parser.add_argument("--version", action="version", version=f"FileShare {version}")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Interface IPv4 de escuta (padrão: todas)"
    )
    parser.add_argument(
        "--port", type=int, help="Porta fixa; sem esta opção procura entre 8000 e 8010"
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Não abrir o navegador automaticamente",
    )
    args = parser.parse_args()
    if args.port is not None and not 0 <= args.port <= 65535:
        parser.error("A porta deve estar entre 0 e 65535")
    try:
        with bind_server(args.host, args.port) as sock:
            port = sock.getsockname()[1]
            host = network_ip() if args.host == "0.0.0.0" else args.host
            address = os.environ.get("FILESHARE_PUBLIC_URL") or f"http://{host}:{port}/"
            os.environ["FILESHARE_PUBLIC_URL"] = address
            if host == "127.0.0.1" and args.host == "0.0.0.0":
                print(
                    "Rede local não identificada. Conecte o computador à rede para compartilhar com outros dispositivos."
                )
            server = uvicorn.Server(
                uvicorn.Config(
                    app,
                    host=args.host,
                    port=port,
                    loop="asyncio",
                    http="h11",
                    ws="none",
                    timeout_graceful_shutdown=2,
                )
            )
            threading.Thread(
                target=open_when_ready,
                args=(server, address, not args.no_browser),
                daemon=True,
            ).start()
            try:
                server.run(sockets=[sock])
            finally:
                server.should_exit = True
    except OSError as error:
        print(f"Não foi possível iniciar o FileShare: {error}", file=sys.stderr)
        if getattr(sys, "frozen", False) and not args.no_browser and sys.stdin.isatty():
            input("Pressione Enter para sair…")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
