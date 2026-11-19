#!/usr/bin/env bash
# Triscore - launcher local para Ubuntu/Linux (offline)
set -u

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR" || exit 1

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
elif [[ -x "$APP_DIR/.venv/bin/python" ]]; then
  RUNTIME=("$APP_DIR/.venv/bin/python" "$APP_DIR/run.py")
  HEALTH_PYTHON="$APP_DIR/.venv/bin/python"
  if ! "$HEALTH_PYTHON" -c "$PYTHON_VERSION_OK"; then
    die "O .venv do pacote nao e Python 3.11+."
  fi
  echo "Runtime: .venv embutido ($("$HEALTH_PYTHON" -c 'import sys; print(sys.version.split()[0])'))"
else
  SYSTEM_PYTHON="$(find_python || true)"
  if [[ -z "$SYSTEM_PYTHON" ]]; then
    die "Python 3.12 nao encontrado. Instale os pacotes offline com: sudo ./instalar_debs.sh"
  fi
  if ! "$SYSTEM_PYTHON" -c "$PYTHON_VERSION_OK"; then
    die "Python encontrado ($SYSTEM_PYTHON) e anterior ao 3.11. Instale o Python 3.12: sudo ./instalar_debs.sh"
  fi
  if ! "$SYSTEM_PYTHON" -m venv --help >/dev/null 2>&1; then
    die "O modulo venv nao esta disponivel. Instale offline: sudo ./instalar_debs.sh"
  fi
  echo "Criando ambiente virtual em $APP_DIR/.venv ..."
  "$SYSTEM_PYTHON" -m venv --copies "$APP_DIR/.venv" || \
    die "Falha ao criar o .venv. Instale os .deb offline com: sudo ./instalar_debs.sh"
  if [[ -d "$APP_DIR/wheels" ]]; then
    "$APP_DIR/.venv/bin/python" -m pip install --no-index \
      --find-links "$APP_DIR/wheels" -r "$APP_DIR/requirements.txt" || \
      die "Falha ao instalar dependencias offline da pasta wheels."
  else
    die "Pasta wheels ausente e .venv nao foi encontrado no pacote."
  fi
  RUNTIME=("$APP_DIR/.venv/bin/python" "$APP_DIR/run.py")
  HEALTH_PYTHON="$APP_DIR/.venv/bin/python"
  echo "Runtime: .venv criado ($("$HEALTH_PYTHON" -c 'import sys; print(sys.version.split()[0])'))"
fi

if [[ ${#RUNTIME[@]} -eq 0 ]]; then
  die "Nenhum runtime valido encontrado."
fi

PORT_FILE="${TRISCORE_PORT_FILE:-$DATA_DIR/logs/.triscore-port-$$}"
rm -f "$PORT_FILE"

"${RUNTIME[@]}" --no-browser --port-file "$PORT_FILE" "$@" &
SERVER_PID=$!

cleanup() {
  trap - INT TERM EXIT
  if kill -0 "$SERVER_PID" 2>/dev/null; then
    kill -INT "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -f "$PORT_FILE"
  exit 0
}
trap cleanup INT TERM

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
