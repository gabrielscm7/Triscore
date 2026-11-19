#!/usr/bin/env bash
# Build opcional do binario onedir com PyInstaller em Ubuntu 24.04 x86_64.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERRO: Docker e necessario para gerar o binario no alvo Ubuntu 24.04." >&2
  exit 1
fi

STAMP="$(date -u +%Y%m%d-%H%M%S)"
OUT_DIR="$APP_DIR/dist/triscore-binario-$STAMP"
mkdir -p "$OUT_DIR"

docker run --rm \
  -v "$APP_DIR:/src" \
  -v "$OUT_DIR:/out" \
  -w /src \
  ubuntu:24.04 bash -euo pipefail -c '
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends python3.12 python3.12-venv python3-pip libpython3.12t64 ca-certificates binutils
python3.12 -m venv /tmp/build-venv
/tmp/build-venv/bin/python -m pip install --no-cache-dir -r requirements-lock.txt -r requirements-build.txt
/tmp/build-venv/bin/pyinstaller \
  --noconfirm --clean --onedir --name TriScore \
  --distpath /out --workpath /tmp/pyinstaller-work --specpath /tmp/pyinstaller-spec \
  --add-data "/src/app/templates:app/templates" \
  --add-data "/src/app/static:app/static" \
  --add-data "/src/app/schema.sql:app" \
  --collect-all uvicorn \
  --collect-all reportlab \
  --collect-all PIL \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.lifespan.on \
  /src/run.py
{
  echo "target_os=Ubuntu 24.04 LTS"
  . /etc/os-release
  echo "build_os=$PRETTY_NAME"
  echo "build_arch=$(uname -m)"
  echo "build_python=$(python3.12 --version 2>&1)"
  echo "build_glibc=$(ldd --version | head -n 1)"
  echo "pyinstaller=$(/tmp/build-venv/bin/pyinstaller --version)"
  echo "built_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > /out/TriScore/BUILD-INFO.txt
chown -R '"$(id -u)"':'"$(id -g)"' /out
'

cp "$APP_DIR/TriScore.sh" "$OUT_DIR/TriScore.sh"
cp "$APP_DIR/verificar.sh" "$OUT_DIR/verificar.sh"
cp "$APP_DIR/TriScore.desktop" "$OUT_DIR/TriScore.desktop"
cp "$APP_DIR/instalar_atalho.sh" "$OUT_DIR/instalar_atalho.sh"
cp "$APP_DIR/README.md" "$OUT_DIR/README.md"
cp "$APP_DIR/docs/README-PORTATIL.md" "$OUT_DIR/README-PORTATIL.md"
chmod +x "$OUT_DIR/TriScore.sh" "$OUT_DIR/verificar.sh" "$OUT_DIR/instalar_atalho.sh"
mkdir -p "$OUT_DIR/dados"
touch "$OUT_DIR/dados/.gitkeep"

tar --sort=name --owner=0 --group=0 --numeric-owner \
  -czf "$OUT_DIR.tar.gz" -C "$APP_DIR/dist" "$(basename "$OUT_DIR")"
(cd "$APP_DIR/dist" && sha256sum "$(basename "$OUT_DIR").tar.gz" > "$(basename "$OUT_DIR").tar.gz.sha256")

echo "Binario criado em: $OUT_DIR"
echo "Pacote criado em:  $OUT_DIR.tar.gz"
