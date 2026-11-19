#!/usr/bin/env bash
# Gera o .tar.gz portátil para Ubuntu 24.04 x86_64 / Python 3.12.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERRO: python3 não encontrado na máquina de build." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "AVISO: Docker não encontrado; o wheelhouse/venv do alvo não pode ser gerado." >&2
  echo "Use uma máquina Ubuntu 24.04 ou instale Docker. Para desenvolvimento, use --skip-wheels." >&2
fi

exec python3 scripts/build_portable.py "$@"
