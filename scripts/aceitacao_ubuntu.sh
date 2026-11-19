#!/usr/bin/env bash
# Aceitação em ubuntu:24.04 limpo e sem rede.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCHIVE="${1:-$(ls -1t "$APP_DIR"/dist/triscore-portatil-*.tar.gz 2>/dev/null | head -n 1)}"

if [[ -z "${ARCHIVE:-}" || ! -f "$ARCHIVE" ]]; then
  echo "Uso: $0 [caminho/para/triscore-portatil-*.tar.gz]" >&2
  exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "ERRO: Docker nao encontrado." >&2
  exit 1
fi

ARCHIVE="$(cd "$(dirname "$ARCHIVE")" && pwd)/$(basename "$ARCHIVE")"

docker run --rm --network none \
  -e DEBIAN_FRONTEND=noninteractive -e TZ=Etc/UTC \
  -v "$ARCHIVE:/pkg.tar.gz:ro" \
  ubuntu:24.04 bash -euo pipefail -c '
    mkdir -p /tmp/triscore
    tar -xzf /pkg.tar.gz -C /tmp/triscore --strip-components=1
    cd /tmp/triscore
    ./instalar_debs.sh
    ./verificar.sh
    .venv/bin/python scripts/smoke_launcher.py --timeout 90
  '
