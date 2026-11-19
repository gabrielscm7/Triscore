from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _request(url: str, *, data: dict | None = None, timeout: float = 5.0):
    payload = None
    headers = {}
    if data is not None:
        payload = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=payload, headers=headers)
    return urllib.request.urlopen(request, timeout=timeout)


def _wait_port(port_file: Path, process: subprocess.Popen, timeout: float) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Launcher encerrou antes de subir (código {process.returncode}).")
        if port_file.exists():
            text = port_file.read_text(encoding="utf-8").strip()
            if text:
                return int(text)
        time.sleep(0.2)
    raise TimeoutError("Arquivo de porta não apareceu.")


def _wait_health(port: int, process: subprocess.Popen, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/health"
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Launcher encerrou antes do health check (código {process.returncode}).")
        try:
            with _request(url, timeout=2) as response:
                if response.status == 200:
                    return json.loads(response.read().decode("utf-8"))
        except Exception as error:
            last_error = error
        time.sleep(0.25)
    raise TimeoutError(f"Health check não respondeu: {last_error}")


def _event_id(db_path: Path) -> int:
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute("SELECT MAX(id) AS id FROM events").fetchone()
    finally:
        connection.close()
    if row is None or row[0] is None:
        raise RuntimeError("Nenhuma prova foi criada.")
    return int(row[0])


def _tail(path: Path, lines: int = 40) -> str:
    if not path.exists():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def run_smoke(*, keep: bool = False, timeout: float = 60.0) -> list[str]:
    base = Path(tempfile.mkdtemp(prefix="triscore-launcher-"))
    data_dir = base / "dados"
    port_file = base / "porta"
    log_file = base / "launcher.out"
    env = os.environ.copy()
    env["TRISCORE_DATA_DIR"] = str(data_dir)
    env["TRISCORE_PORT_FILE"] = str(port_file)
    env["TRISCORE_NO_BROWSER"] = "1"
    env.pop("TRISCORE_DB", None)
    env.pop("TRISCORE_ENV", None)

    launcher = PROJECT_ROOT / "TriScore.sh"
    checks: list[str] = []
    with log_file.open("wb") as log_handle:
        process = subprocess.Popen(
            [str(launcher), "--modo", "teste", "--no-browser"],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            port = _wait_port(port_file, process, timeout)
            checks.append(f"Launcher escolheu a porta {port}")

            health = _wait_health(port, process, timeout)
            assert health.get("status") == "ok", health
            assert health.get("environment") == "teste", health
            checks.append("Health check respondeu status ok")

            base_url = f"http://127.0.0.1:{port}"
            with _request(
                f"{base_url}/eventos",
                data={
                    "name": "Smoke Launcher 2026",
                    "event_date": "2026-12-12",
                    "location": "Arena Offline",
                },
                timeout=10,
            ) as response:
                assert response.status in (200, 303), response.status
            db_path = data_dir / "teste" / "banco" / "triscore-teste.db"
            event_id = _event_id(db_path)
            checks.append(f"Prova fictícia criada (id {event_id})")

            with _request(f"{base_url}/eventos/{event_id}/pdfs/cronograma", timeout=30) as response:
                content = response.read()
            assert content.startswith(b"%PDF"), content[:20]
            checks.append(f"PDF de cronograma gerado ({len(content)} bytes)")

            with _request(f"{base_url}/encerrar", data={}, timeout=10) as response:
                assert response.status == 200, response.status
            checks.append("POST /encerrar respondeu 200")

            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired as error:
                raise RuntimeError("Launcher não encerrou após /encerrar.") from error
            assert code == 0, f"Launcher encerrou com código {code}."
            checks.append("Processo do launcher encerrou com código 0")

            backups = sorted((data_dir / "teste" / "backups").glob("*encerramento*.db"))
            assert backups, "Backup de encerramento não foi criado."
            checks.append(f"Backup de encerramento criado: {backups[-1].name}")
        except Exception:
            print("\n--- log do launcher ---", file=sys.stderr)
            print(_tail(log_file), file=sys.stderr)
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
            raise
        finally:
            if keep:
                print(f"Arquivos do smoke mantidos em: {base}")
            else:
                subprocess.run(["rm", "-rf", str(base)], check=False)

    return checks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sobe o Triscore pelo TriScore.sh, testa health, PDF e encerramento."
    )
    parser.add_argument("--keep", action="store_true", help="Mantém a pasta temporária.")
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()
    checks = run_smoke(keep=args.keep, timeout=args.timeout)
    print("Smoke do launcher concluído com sucesso:")
    for item in checks:
        print(f"  [ok] {item}")


if __name__ == "__main__":
    main()
