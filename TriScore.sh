#!/usr/bin/env bash
# Triscore - launcher local para Ubuntu/Linux (offline)
set -u

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR" || exit 1

VENV_DIR="$APP_DIR/.venv"
VENV_TMP="$APP_DIR/.venv.tmp"
VENV_LOCAL_MARKER=".triscore-local"

DATA_DIR="${TRISCORE_DATA_DIR:-$APP_DIR/dados}"
case "$DATA_DIR" in
  /*) ;;
  *) DATA_DIR="$APP_DIR/${DATA_DIR#./}" ;;
esac
export TRISCORE_DATA_DIR="$DATA_DIR"

mkdir -p "$DATA_DIR/banco" "$DATA_DIR/backups" "$DATA_DIR/exports" \
  "$DATA_DIR/uploads" "$DATA_DIR/logs" "$DATA_DIR/teste/banco" \
  "$DATA_DIR/teste/backups" "$DATA_DIR/teste/exports" \
  "$DATA_DIR/teste/uploads" "$DATA_DIR/teste/logs" || {
    echo "ERRO: nao foi possivel criar a pasta de dados: $DATA_DIR" >&2
    exit 1
  }

STAMP="$(date +%Y%m%d-%H%M%S)"
export TRISCORE_LOG_FILE="$DATA_DIR/logs/triscore-$STAMP.log"
LAUNCHER_LOG="$DATA_DIR/logs/launcher-$STAMP.log"
exec > >(tee -a "$LAUNCHER_LOG") 2>&1

echo "Triscore"
echo "App:   $APP_DIR"
echo "Dados: $DATA_DIR"
echo "Log:   $TRISCORE_LOG_FILE"
echo

die() {
  echo >&2
  echo "ERRO: $1" >&2
  echo "Consulte o log: $LAUNCHER_LOG" >&2
  exit 1
}

find_python() {
  if command -v python3.12 >/dev/null 2>&1; then
    command -v python3.12
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  return 1
}

PYTHON_VERSION_OK='import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'

VENV_IMPORT_CHECK='
import importlib

required = {
    "uvicorn": "uvicorn",
    "fastapi": "fastapi",
    "jinja2": "jinja2",
    "multipart": "python-multipart",
    "reportlab": "reportlab",
    "PIL": "pillow",
}
missing = []
for module, package in required.items():
    try:
        importlib.import_module(module)
    except Exception as error:
        missing.append(f"{package}: {error}")

if missing:
    print("Dependencias ausentes: " + "; ".join(missing))
    raise SystemExit(1)
'

VENV_VALIDATION_ERROR=""
SERVER_PID=""
PORT_FILE=""

remove_venv_tmp() {
  if [[ -e "$VENV_TMP" || -L "$VENV_TMP" ]]; then
    rm -rf -- "$VENV_TMP" 2>/dev/null || true
  fi
}

validate_venv() {
  local venv="$1"
  local output=""
  VENV_VALIDATION_ERROR=""

  if [[ ! -x "$venv/bin/python" ]]; then
    VENV_VALIDATION_ERROR="Python executavel ausente em $venv/bin/python"
    return 1
  fi
  if ! output="$("$venv/bin/python" -c "$PYTHON_VERSION_OK" 2>&1)"; then
    VENV_VALIDATION_ERROR="Python anterior a 3.11${output:+: $output}"
    return 1
  fi
  if ! output="$("$venv/bin/python" -c "$VENV_IMPORT_CHECK" 2>&1)"; then
    VENV_VALIDATION_ERROR="${output:-Falha ao importar as dependencias}"
    return 1
  fi
  return 0
}

prepare_system_python() {
  SYSTEM_PYTHON="$(find_python || true)"
  if [[ -z "$SYSTEM_PYTHON" ]]; then
    die "Python 3.11 ou superior nao encontrado. No git clone, instale python3.12 e python3.12-venv; no pacote offline, use: sudo ./instalar_debs.sh"
  fi
  if ! "$SYSTEM_PYTHON" -c "$PYTHON_VERSION_OK"; then
    die "Python encontrado ($SYSTEM_PYTHON) e anterior ao 3.11. Instale o Python 3.12 (python3.12-venv) ou use sudo ./instalar_debs.sh."
  fi
  if ! "$SYSTEM_PYTHON" -m venv --help >/dev/null 2>&1; then
    die "O modulo venv nao esta disponivel. No git clone, instale python3.12-venv; no pacote offline, use: sudo ./instalar_debs.sh"
  fi
}

has_wheelhouse() {
  [[ -d "$APP_DIR/wheels" ]] && \
    compgen -G "$APP_DIR/wheels/*.whl" >/dev/null 2>&1
}

create_local_venv() {
  local system_python="$1"
  local validation_output=""

  remove_venv_tmp
  echo "Criando ambiente virtual temporario em $VENV_TMP ..."
  if ! "$system_python" -m venv --copies "$VENV_TMP"; then
    remove_venv_tmp
    die "Falha ao criar o ambiente virtual temporario. No git clone, instale python3.12-venv; no pacote offline, use: sudo ./instalar_debs.sh"
  fi

  if has_wheelhouse; then
    echo "Instalando dependencias offline de $APP_DIR/wheels ..."
    if ! "$VENV_TMP/bin/python" -m pip install --no-index \
      --find-links "$APP_DIR/wheels" -r "$APP_DIR/requirements.txt"; then
      remove_venv_tmp
      die "Falha ao instalar as dependencias offline da pasta wheels/. Use o pacote portatil completo ou refaca o download. O ambiente temporario foi removido."
    fi
  else
    echo "Pasta wheels/ ausente; instalando dependencias pelo indice do pip (requer internet) ..."
    if ! "$VENV_TMP/bin/python" -m pip install -r "$APP_DIR/requirements.txt"; then
      remove_venv_tmp
      die "Nao foi possivel instalar as dependencias sem wheels/, provavelmente por falta de internet. Conecte-se a internet e execute ./TriScore.sh novamente. Para uso offline, use o pacote portatil com a pasta wheels/. O ambiente temporario foi removido."
    fi
  fi

  if ! validate_venv "$VENV_TMP"; then
    validation_output="$VENV_VALIDATION_ERROR"
    remove_venv_tmp
    if has_wheelhouse; then
      die "As dependencias instaladas de wheels/ nao puderam ser importadas: $validation_output. O ambiente temporario foi removido; refaca o download do pacote."
    fi
    die "As dependencias instaladas pelo pip nao puderam ser importadas: $validation_output. Verifique a conexao e execute ./TriScore.sh novamente. O ambiente temporario foi removido."
  fi

  if ! : > "$VENV_TMP/$VENV_LOCAL_MARKER"; then
    remove_venv_tmp
    die "Falha ao preparar o ambiente virtual temporario. O ambiente temporario foi removido."
  fi
  if ! rm -rf -- "$VENV_DIR"; then
    remove_venv_tmp
    die "Falha ao substituir o .venv existente. O ambiente temporario foi removido."
  fi
  if ! mv -- "$VENV_TMP" "$VENV_DIR"; then
    remove_venv_tmp
    die "Falha ao ativar o novo .venv. O ambiente temporario foi removido e nenhum .venv parcial foi mantido."
  fi
}

venv_runtime_label() {
  if [[ -f "$VENV_DIR/$VENV_LOCAL_MARKER" ]]; then
    printf 'criado localmente'
  elif [[ -f "$APP_DIR/BUILD-INFO.txt" ]] || has_wheelhouse; then
    printf 'do pacote'
  else
    printf 'criado localmente'
  fi
}

cleanup() {
  local rc=0
  trap - EXIT HUP INT TERM
  remove_venv_tmp
  if [[ -n "$SERVER_PID" ]]; then
    if kill -0 "$SERVER_PID" 2>/dev/null; then
      kill -INT "$SERVER_PID" 2>/dev/null || true
      wait "$SERVER_PID" 2>/dev/null || true
    fi
  else
    echo >&2
    echo "Interrompido antes da inicializacao do servidor." >&2
    rc=130
  fi
  if [[ -n "$PORT_FILE" ]]; then
    rm -f "$PORT_FILE"
  fi
  exit "$rc"
}

trap 'remove_venv_tmp' EXIT
trap cleanup HUP INT TERM

RUNTIME=()
HEALTH_PYTHON=""
NO_BROWSER=0
for arg in "$@"; do
  case "$arg" in
    --no-browser) NO_BROWSER=1 ;;
    --help|-h)
      if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
        exec "$APP_DIR/.venv/bin/python" "$APP_DIR/run.py" "$@"
      fi
      PY="$(find_python)" || die "Python 3 nao encontrado."
      exec "$PY" "$APP_DIR/run.py" "$@"
      ;;
  esac
done

if [[ -x "$APP_DIR/TriScore/TriScore" ]]; then
  RUNTIME=("$APP_DIR/TriScore/TriScore")
  HEALTH_PYTHON="$(find_python || true)"
  echo "Runtime: binario embutido ($APP_DIR/TriScore/TriScore)"
elif [[ -x "$APP_DIR/TriScore" && ! -d "$APP_DIR/app" ]]; then
  RUNTIME=("$APP_DIR/TriScore")
  HEALTH_PYTHON="$(find_python || true)"
  echo "Runtime: binario embutido ($APP_DIR/TriScore)"
elif [[ -e "$VENV_DIR" || -L "$VENV_DIR" ]]; then
  if validate_venv "$VENV_DIR"; then
    RUNTIME=("$VENV_DIR/bin/python" "$APP_DIR/run.py")
    HEALTH_PYTHON="$VENV_DIR/bin/python"
    echo "Runtime: .venv $(venv_runtime_label) ($("$HEALTH_PYTHON" -c 'import sys; print(sys.version.split()[0])'))"
  else
    echo >&2
    echo "AVISO: o .venv existente esta incompleto ou invalido e sera recriado." >&2
    echo "Motivo: $VENV_VALIDATION_ERROR" >&2
    if ! rm -rf -- "$VENV_DIR"; then
      die "Falha ao remover o .venv incompleto. Nenhum ambiente parcial novo foi criado."
    fi
    prepare_system_python
    create_local_venv "$SYSTEM_PYTHON"
    RUNTIME=("$VENV_DIR/bin/python" "$APP_DIR/run.py")
    HEALTH_PYTHON="$VENV_DIR/bin/python"
    echo "Runtime: .venv criado localmente ($("$HEALTH_PYTHON" -c 'import sys; print(sys.version.split()[0])'))"
  fi
else
  prepare_system_python
  create_local_venv "$SYSTEM_PYTHON"
  RUNTIME=("$VENV_DIR/bin/python" "$APP_DIR/run.py")
  HEALTH_PYTHON="$VENV_DIR/bin/python"
  echo "Runtime: .venv criado localmente ($("$HEALTH_PYTHON" -c 'import sys; print(sys.version.split()[0])'))"
fi

if [[ ${#RUNTIME[@]} -eq 0 ]]; then
  die "Nenhum runtime valido encontrado."
fi

PORT_FILE="${TRISCORE_PORT_FILE:-$DATA_DIR/logs/.triscore-port-$$}"
rm -f "$PORT_FILE"

"${RUNTIME[@]}" --no-browser --port-file "$PORT_FILE" "$@" &
SERVER_PID=$!

PORT=""
for _ in $(seq 1 120); do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    wait "$SERVER_PID" 2>/dev/null
    RC=$?
    echo >&2
    echo "ERRO: o servidor encerrou durante a inicializacao (codigo $RC)." >&2
    echo "Ultimas linhas do log $TRISCORE_LOG_FILE:" >&2
    tail -n 30 "$TRISCORE_LOG_FILE" 2>/dev/null >&2 || true
    exit 1
  fi
  if [[ -s "$PORT_FILE" ]]; then
    PORT="$(head -n 1 "$PORT_FILE")"
    break
  fi
  sleep 0.25
done

if [[ -z "$PORT" ]]; then
  echo >&2
  echo "ERRO: o servidor nao informou a porta em 30 segundos." >&2
  kill -INT "$SERVER_PID" 2>/dev/null || true
  wait "$SERVER_PID" 2>/dev/null || true
  tail -n 30 "$TRISCORE_LOG_FILE" 2>/dev/null >&2 || true
  exit 1
fi

URL="http://127.0.0.1:$PORT"
HEALTH_OK=0
for _ in $(seq 1 120); do
  if [[ -n "$HEALTH_PYTHON" ]] && "$HEALTH_PYTHON" - "$PORT" <<'PY'
import sys
import urllib.request

port = int(sys.argv[1])
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
        raise SystemExit(0 if response.status == 200 else 1)
except Exception:
    raise SystemExit(1)
PY
  then
    HEALTH_OK=1
    break
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    break
  fi
  sleep 0.25
done

if [[ "$HEALTH_OK" -ne 1 ]]; then
  echo >&2
  echo "ERRO: o health check nao respondeu em $URL/health." >&2
  echo "Ultimas linhas do log $TRISCORE_LOG_FILE:" >&2
  tail -n 40 "$TRISCORE_LOG_FILE" 2>/dev/null >&2 || true
  kill -INT "$SERVER_PID" 2>/dev/null || true
  wait "$SERVER_PID" 2>/dev/null || true
  rm -f "$PORT_FILE"
  exit 1
fi

echo
echo "Triscore disponivel em $URL"
echo "Pressione Ctrl+C para encerrar ou use o botao Encerrar na interface."

if [[ "$NO_BROWSER" -eq 0 && ( -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ) ]]; then
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 &
  fi
fi

wait "$SERVER_PID"
RC=$?
rm -f "$PORT_FILE"
if [[ "$RC" -ne 0 ]]; then
  echo "Servidor encerrou com codigo $RC. Consulte $TRISCORE_LOG_FILE" >&2
fi
exit "$RC"
