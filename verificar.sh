#!/usr/bin/env bash
# Triscore - verificacao de ambiente offline
# Alvo: Ubuntu 24.04 LTS x86_64, Python 3.12
set -u

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR" || exit 1

DATA_DIR="${TRISCORE_DATA_DIR:-$APP_DIR/dados}"
case "$DATA_DIR" in
  /*) ;;
  *) DATA_DIR="$APP_DIR/${DATA_DIR#./}" ;;
esac

FAILS=0
ok()   { printf '  [OK]    %s\n' "$1"; }
fail() { printf '  [FALHA] %s\n' "$1" >&2; FAILS=$((FAILS + 1)); }
info() { printf '  [INFO]  %s\n' "$1"; }

echo "Triscore - verificacao de ambiente"
echo "App:   $APP_DIR"
echo "Dados: $DATA_DIR"
echo

if [[ -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  OS_PRETTY="${PRETTY_NAME:-desconhecido}"
  if [[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "24.04" ]]; then
    ok "Ubuntu 24.04: $OS_PRETTY"
  else
    fail "SO fora do alvo: $OS_PRETTY (esperado Ubuntu 24.04)"
  fi
else
  fail "/etc/os-release nao encontrado"
fi

ARCH="$(uname -m)"
if [[ "$ARCH" == "x86_64" ]]; then
  ok "Arquitetura x86_64"
else
  fail "Arquitetura $ARCH (esperado x86_64)"
fi

PYTHON=""
if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
  PYTHON="$APP_DIR/.venv/bin/python"
  ok "venv do pacote encontrado: .venv/bin/python"
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON="$(command -v python3.12)"
  info "venv .venv ausente; usando python3.12 do sistema"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
  info "venv .venv ausente; usando python3 do sistema"
else
  fail "Python 3.12 nao encontrado. Instale com: sudo ./instalar_debs.sh"
fi

if [[ -n "$PYTHON" ]]; then
  if "$PYTHON" - <<'PY'
import sys

version = sys.version.split()[0]
if sys.version_info[:2] != (3, 12):
    print(f"Python {version} (esperado 3.12.x)")
    raise SystemExit(1)
print(f"Python {version}")
PY
  then
    ok "Python 3.12.x"
  else
    fail "Python diferente de 3.12"
  fi
fi

if [[ -n "$PYTHON" ]]; then
  if "$PYTHON" -c 'import venv' >/dev/null 2>&1; then
    ok "Modulo venv disponivel"
  else
    fail "Modulo venv ausente. Use: sudo ./instalar_debs.sh"
  fi
fi

if [[ -n "$PYTHON" ]]; then
  if "$PYTHON" - <<'PY'
import importlib

required = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "jinja2": "jinja2",
    "multipart": "python-multipart",
    "reportlab": "reportlab",
    "PIL": "pillow",
    "pydantic": "pydantic",
    "starlette": "starlette",
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

import reportlab
print(f"reportlab {getattr(reportlab, 'Version', 'desconhecida')}")
PY
  then
    ok "Dependencias de execucao importaveis"
  else
    fail "Dependencias ausentes. Rode ./TriScore.sh para instalar do wheelhouse."
  fi
fi

if [[ -d "$APP_DIR/wheels" ]]; then
  WHEEL_COUNT="$(find "$APP_DIR/wheels" -maxdepth 1 -name '*.whl' | wc -l | tr -d ' ')"
  SDIST_COUNT="$(find "$APP_DIR/wheels" -maxdepth 1 \( -name '*.tar.gz' -o -name '*.zip' \) | wc -l | tr -d ' ')"
  CP314_COUNT="$(find "$APP_DIR/wheels" -maxdepth 1 -name '*cp314*' | wc -l | tr -d ' ')"
  if [[ "$WHEEL_COUNT" -eq 0 ]]; then
    fail "wheelhouse vazio"
  elif [[ "$SDIST_COUNT" -ne 0 ]]; then
    fail "wheelhouse contem fontes ($SDIST_COUNT); o alvo exige --only-binary"
  elif [[ "$CP314_COUNT" -ne 0 ]]; then
    fail "wheelhouse contem wheels cp314; o alvo e cp312"
  else
    ok "$WHEEL_COUNT wheels, sem fontes e sem cp314"
  fi
else
  info "Pasta wheels ausente (ok se o .venv ja esta instalado)"
fi

if mkdir -p "$DATA_DIR/banco" "$DATA_DIR/backups" "$DATA_DIR/exports" \
  "$DATA_DIR/uploads" "$DATA_DIR/logs" 2>/dev/null; then
  PROBE="$DATA_DIR/.verificar-$$"
  if ( : > "$PROBE" ) 2>/dev/null && [[ -w "$PROBE" ]]; then
    ok "Pasta de dados gravavel: $DATA_DIR"
  else
    fail "Sem permissao de escrita em $DATA_DIR"
  fi
  rm -f "$PROBE" 2>/dev/null || true
else
  fail "Nao foi possivel criar a pasta de dados: $DATA_DIR"
fi

if [[ -n "$PYTHON" ]]; then
  PDF_DIR="$DATA_DIR/.verificar-pdf-$$"
  if mkdir -p "$PDF_DIR" 2>/dev/null; then
    PDF="$PDF_DIR/teste.pdf"
    if "$PYTHON" - "$PDF" "$APP_DIR" <<'PY'
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

target = Path(sys.argv[1])
app_dir = Path(sys.argv[2])
font = app_dir / "app" / "static" / "fonts" / "FiraSans-Regular.ttf"

if not font.is_file():
    raise SystemExit(f"Fonte local nao encontrada: {font}")

pdfmetrics.registerFont(TTFont("FiraVerificacao", str(font)))
doc = canvas.Canvas(str(target), pagesize=A4)
doc.setFont("FiraVerificacao", 14)
doc.drawString(72, 760, "Triscore - verificacao de geracao de PDF")
doc.save()

if target.read_bytes()[:4] != b"%PDF":
    raise SystemExit("O arquivo gerado nao e um PDF valido")

print(f"PDF de teste gerado: {target.stat().st_size} bytes")
PY
    then
      ok "Geracao de PDF com ReportLab e fonte local"
    else
      fail "Falha ao gerar PDF (ReportLab/Pillow/fonte local)"
    fi
    rm -rf "$PDF_DIR" 2>/dev/null || true
  else
    fail "Nao foi possivel criar pasta para o teste de PDF"
  fi
fi

if [[ -n "$PYTHON" ]]; then
  if PORT="$("$PYTHON" - <<'PY'
import socket

for port in range(8000, 8100):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            continue
        print(port)
        break
else:
    raise SystemExit(1)
PY
  )"; then
    ok "Porta local livre para o servidor: $PORT"
  else
    fail "Nenhuma porta livre entre 8000 e 8099 em 127.0.0.1"
  fi
fi

if [[ -n "$PYTHON" ]]; then
  NET="$("$PYTHON" - <<'PY'
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(2)
try:
    sock.connect(("1.1.1.1", 443))
    print("disponivel")
except OSError:
    print("indisponivel")
finally:
    sock.close()
PY
)"
  info "Internet: $NET (informativo; a aplicacao nao usa rede externa)"
fi

if [[ -x "$APP_DIR/TriScore.sh" ]]; then
  ok "TriScore.sh executavel"
else
  fail "TriScore.sh ausente ou sem permissao de execucao"
fi

if [[ -f "$APP_DIR/TriScore.desktop" ]]; then
  ok "TriScore.desktop presente"
else
  fail "TriScore.desktop ausente"
fi

echo
if (( FAILS > 0 )); then
  echo "RESULTADO: FALHA ($FAILS item(ns) com problema)" >&2
  exit 1
fi
echo "RESULTADO: OK (0 falhas)"
