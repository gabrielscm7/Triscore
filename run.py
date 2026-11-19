from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

import uvicorn

from app.data_migration import migrate_legacy_data
from app.database import backup_database, resolve_db_path
from app.environment import (
    REAL_PORT,
    TEST_DB_PATH,
    TEST_PORT,
    Environment,
    create_environment,
)
from app.main import create_app
from app.paths import APP_DIR, DATA_DIR


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


def find_available_port(preferred: int, end: int) -> int:
    for port in range(preferred, end):
        if _port_available(port):
            return port
    raise RuntimeError(
        f"Nenhuma porta local disponível entre {preferred} e {end - 1}."
    )


def _fail(message: str) -> None:
    print(f"\n{message}\n", file=sys.stderr)
    raise SystemExit(2)


def _choose_database(args: argparse.Namespace):
    explicit_db = args.db if args.db is not None else os.environ.get("TRISCORE_DB")
    if explicit_db:
        return resolve_db_path(explicit_db)
    if args.modo == "teste":
        return resolve_db_path(TEST_DB_PATH)
    return resolve_db_path(None)


def _configure_logging(environment: Environment) -> Path:
    configured = os.environ.get("TRISCORE_LOG_FILE")
    if configured:
        log_path = Path(configured).expanduser()
        if not log_path.is_absolute():
            log_path = environment.logs_dir / log_path
    else:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_path = environment.logs_dir / f"triscore-{stamp}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.FileHandler(log_path, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    return log_path


def _health_ready(port: int, timeout: float = 30.0) -> bool:
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def _open_browser_when_ready(port: int, url: str, stop: threading.Event) -> None:
    deadline = time.monotonic() + 30
    while not stop.is_set() and time.monotonic() < deadline:
        if _health_ready(port, timeout=1):
            try:
                webbrowser.open(url)
            except Exception:
                logging.getLogger("triscore").warning(
                    "Nao foi possivel abrir o navegador automaticamente. Acesse %s",
                    url,
                )
            return
        stop.wait(0.25)


def _write_port_file(path: str | Path | None, port: int) -> Path | None:
    if not path:
        return None
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{port}\n", encoding="utf-8")
    return target


def _run_server(
    *,
    app,
    db_path: Path,
    environment: Environment,
    port: int,
    open_browser: bool,
    port_file: Path | None,
) -> None:
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        log_config=None,
        access_log=True,
    )
    server = uvicorn.Server(config)
    logger = logging.getLogger("triscore")

    backup_lock = threading.Lock()
    backup_done = False

    def make_shutdown_backup() -> None:
        nonlocal backup_done
        with backup_lock:
            if backup_done:
                return
            backup_done = True
        if not db_path.exists():
            return
        try:
            target = backup_database(
                db_path,
                prefix=f"{environment.backup_prefix}-encerramento",
                backup_dir=environment.backup_dir,
            )
            logger.info("Backup de encerramento criado em %s", target)
        except Exception:
            logger.exception("Falha ao criar o backup de encerramento")

    def request_shutdown() -> None:
        make_shutdown_backup()
        server.should_exit = True

    app.state.shutdown_handler = request_shutdown

    stop_browser = threading.Event()
    if open_browser:
        threading.Thread(
            target=_open_browser_when_ready,
            args=(port, f"http://127.0.0.1:{port}", stop_browser),
            daemon=True,
            name="triscore-browser",
        ).start()

    try:
        server.run()
    finally:
        stop_browser.set()
        make_shutdown_backup()
        if port_file is not None:
            port_file.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inicia o Triscore localmente, com ambientes real e de teste."
    )
    parser.add_argument(
        "--modo",
        choices=("real", "teste"),
        default=None,
        help="Ambiente explícito. Sem esta opção, o padrão é real.",
    )
    parser.add_argument(
        "--db",
        help="Caminho alternativo para o banco SQLite.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Porta local fixa. Sem esta opção, usa 8000 (real) ou 8100 (teste).",
    )
    parser.add_argument(
        "--port-file",
        default=None,
        help="Arquivo onde a porta efetivamente usada será gravada.",
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="Não abre o navegador."
    )
    parser.add_argument(
        "--confirmar-banco",
        action="store_true",
        help="Confirma a abertura de um banco de outro ambiente.",
    )
    args = parser.parse_args()

    db_path = _choose_database(args)
    environment = create_environment(db_path)

    if args.modo is None:
        if environment.is_test:
            _fail(
                "Banco de teste detectado. Use --modo teste para abri-lo. "
                "Para abrir mesmo assim no modo real, use --modo real --confirmar-banco."
            )
        mode = "real"
    else:
        mode = args.modo

    if mode == "teste" and not environment.is_test and not args.confirmar_banco:
        _fail(
            f"O banco {db_path} não está na pasta de teste. "
            "Use --modo teste --confirmar-banco para abri-lo como teste."
        )
    if mode == "real" and environment.is_test and not args.confirmar_banco:
        _fail(
            f"O banco {db_path} parece ser de teste. "
            "Use --modo teste para abri-lo ou --confirmar-banco para assumir o risco."
        )

    os.environ["TRISCORE_ENV"] = mode
    environment = create_environment(db_path)
    log_path = _configure_logging(environment)

    migration = migrate_legacy_data(APP_DIR, DATA_DIR)
    if migration.errors:
        for error in migration.errors:
            print(f"Aviso de migração de dados: {error}", file=sys.stderr)
    if migration.copied:
        print(
            f"Migração de dados: {len(migration.copied)} arquivo(s) copiados "
            f"para {DATA_DIR}."
        )

    if args.port is not None:
        port = args.port
        if not _port_available(port):
            _fail(f"A porta {port} já está em uso. Escolha outra porta.")
        other_port = TEST_PORT if environment.is_test else REAL_PORT
        if port == other_port:
            print(
                f"Aviso: a porta {port} é a padrão do outro ambiente. "
                "Confira o banco exibido abaixo."
            )
    else:
        try:
            port = find_available_port(*environment.port_range)
        except RuntimeError as error:
            _fail(str(error))

    port_file = _write_port_file(args.port_file, port)
    url = f"http://127.0.0.1:{port}"
    print(f"\nTriscore — ambiente {environment.label.upper()}")
    print(f"Banco:   {environment.db_path}")
    print(f"Backups: {environment.backup_dir}")
    print(f"PDFs:    {environment.exports_dir}")
    print(f"Uploads: {environment.awards_media_dir.parent.parent}")
    print(f"Logs:    {log_path}")
    if environment.is_test:
        print("MODO TESTE: use apenas dados fictícios.")
    print(f"\nTriscore disponível em {url}")
    print("Pressione Ctrl+C ou use o botão Encerrar na interface.\n")

    application = create_app(environment.db_path)
    application.state.log_file = str(log_path)
    _run_server(
        app=application,
        db_path=environment.db_path,
        environment=environment,
        port=port,
        open_browser=not args.no_browser,
        port_file=port_file,
    )


if __name__ == "__main__":
    main()
