from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FAKE_PYTHON = r"""#!/usr/bin/env bash
set -u
if [[ "${1:-}" == "-m" && "${2:-}" == "venv" ]]; then
  if [[ "$*" == *"--help"* ]]; then
    exit 0
  fi
  target="${@: -1}"
  mkdir -p "$target/bin"
  cp "$0" "$target/bin/python"
  chmod +x "$target/bin/python"
  exit 0
fi
if [[ "${1:-}" == "-m" && "${2:-}" == "pip" ]]; then
  if [[ "${TRISCORE_TEST_FAIL_STAGE:-}" == "install" ]]; then
    echo "simulated pip failure: no network" >&2
    exit 1
  fi
  exit 0
fi
if [[ "${1:-}" == "-c" ]]; then
  if [[ "${2:-}" == *importlib* && "${TRISCORE_TEST_FAIL_STAGE:-}" == "validation" ]]; then
    echo "Dependencias ausentes: pillow: modulo ausente" >&2
    exit 1
  fi
  exit 0
fi
exit 1
"""


def _prepare_fake_launcher(tmp_path: Path) -> tuple[Path, Path]:
    app_dir = tmp_path / "app"
    fake_bin = tmp_path / "bin"
    app_dir.mkdir()
    fake_bin.mkdir()

    launcher = app_dir / "TriScore.sh"
    shutil.copy2(PROJECT_ROOT / "TriScore.sh", launcher)
    launcher.chmod(0o755)
    (app_dir / "requirements.txt").write_text("", encoding="utf-8")

    fake_python = fake_bin / "python3.12"
    fake_python.write_text(FAKE_PYTHON, encoding="utf-8")
    fake_python.chmod(0o755)
    return app_dir, fake_bin


@pytest.mark.parametrize(
    ("failure_stage", "expected_message"),
    [
        ("install", "Conecte-se a internet"),
        ("validation", "nao puderam ser importadas"),
    ],
)
def test_failed_venv_is_never_promoted_or_left_as_temporary(
    tmp_path, failure_stage, expected_message
):
    app_dir, fake_bin = _prepare_fake_launcher(tmp_path)
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["TRISCORE_DATA_DIR"] = str(tmp_path / "dados")
    env["TRISCORE_TEST_FAIL_STAGE"] = failure_stage
    env.pop("TRISCORE_DB", None)
    env.pop("TRISCORE_ENV", None)

    result = subprocess.run(
        [str(app_dir / "TriScore.sh"), "--no-browser"],
        cwd=app_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert expected_message in output
    assert not (app_dir / ".venv").exists()
    assert not (app_dir / ".venv.tmp").exists()


def test_existing_incomplete_venv_is_removed_when_recreation_fails(tmp_path):
    app_dir, fake_bin = _prepare_fake_launcher(tmp_path)
    (app_dir / ".venv").mkdir()
    (app_dir / ".venv" / "resto-incompleto").write_text("parcial", encoding="utf-8")
    (app_dir / "wheels").mkdir()

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["TRISCORE_DATA_DIR"] = str(tmp_path / "dados")
    env["TRISCORE_TEST_FAIL_STAGE"] = "install"
    env.pop("TRISCORE_DB", None)
    env.pop("TRISCORE_ENV", None)

    result = subprocess.run(
        [str(app_dir / "TriScore.sh"), "--no-browser"],
        cwd=app_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "esta incompleto ou invalido e sera recriado" in output
    assert "Conecte-se a internet" in output
    assert not (app_dir / ".venv").exists()
    assert not (app_dir / ".venv.tmp").exists()


def _wait_for_port(
    port_file: Path, process: subprocess.Popen, timeout: float
) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"Launcher encerrou antes de informar a porta (codigo {process.returncode})."
            )
        if port_file.exists():
            text = port_file.read_text(encoding="utf-8").strip()
            if text:
                return int(text)
        time.sleep(0.2)
    raise TimeoutError("Arquivo de porta nao apareceu.")


def _wait_for_health(
    port: int, process: subprocess.Popen, timeout: float
) -> dict:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/health"
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"Launcher encerrou antes do health check (codigo {process.returncode})."
            )
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return json.loads(response.read().decode("utf-8"))
        except Exception as error:  # noqa: BLE001
            last_error = error
        time.sleep(0.25)
    raise TimeoutError(f"Health check nao respondeu: {last_error}")


def _tail(path: Path, lines: int = 50) -> str:
    if not path.exists():
        return ""
    return "\n".join(
        path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    )


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="SIGHUP indisponivel")
def test_sighup_shuts_down_server_with_automatic_backup(tmp_path):
    launcher = PROJECT_ROOT / "TriScore.sh"
    if not (PROJECT_ROOT / ".venv" / "bin" / "python").exists():
        pytest.skip("Teste de integracao requer o .venv do projeto.")

    data_dir = tmp_path / "dados"
    port_file = tmp_path / "porta"
    log_file = tmp_path / "launcher.log"
    env = os.environ.copy()
    env["TRISCORE_DATA_DIR"] = str(data_dir)
    env["TRISCORE_PORT_FILE"] = str(port_file)
    env.pop("TRISCORE_DB", None)
    env.pop("TRISCORE_ENV", None)

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
            port = _wait_for_port(port_file, process, timeout=60)
            health = _wait_for_health(port, process, timeout=60)
            assert health.get("status") == "ok"
            assert health.get("environment") == "teste"

            os.kill(process.pid, signal.SIGHUP)
            code = process.wait(timeout=60)

            assert code == 0
            backups = sorted(
                (data_dir / "teste" / "backups").glob("*encerramento*.db")
            )
            assert backups
            assert backups[-1].stat().st_size > 0
        except Exception:
            print("\n--- log do launcher ---", file=sys.stderr)
            print(_tail(log_file), file=sys.stderr)
            raise
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
