#!/usr/bin/env bash
# Instala os .deb offline do pacote na ordem de dependencias do Python 3.12.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEB_DIR="${1:-$APP_DIR/debs}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Execute como root: sudo $APP_DIR/instalar_debs.sh" >&2
  exit 1
fi

if ! compgen -G "$DEB_DIR/*.deb" >/dev/null; then
  echo "Nenhum .deb encontrado em $DEB_DIR" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
export TZ="${TZ:-Etc/UTC}"

install_glob() {
  local pattern="$1"
  local files=( "$DEB_DIR"/$pattern )
  if [[ -e "${files[0]}" ]]; then
    dpkg -i "${files[@]}"
  fi
}

install_glob 'libexpat1_*.deb'
install_glob 'media-types_*.deb'
install_glob 'netbase_*.deb'
install_glob 'tzdata_*.deb'
install_glob 'readline-common_*.deb'
install_glob 'libreadline8t64_*.deb'
install_glob 'libsqlite3-0_*.deb'
install_glob 'libpython3.12-minimal_*.deb'
install_glob 'python3.12-minimal_*.deb'
install_glob 'libpython3.12-stdlib_*.deb'
install_glob 'libpython3-stdlib_*.deb'
install_glob 'python3.12_*.deb'
install_glob 'python3-minimal_*.deb'
install_glob 'python3_*.deb'
install_glob 'python3-pkg-resources_*.deb'
install_glob 'python3-setuptools_*.deb'
install_glob 'python3-wheel_*.deb'
install_glob 'openssl_*.deb'
install_glob 'ca-certificates_*.deb'
install_glob 'python3-pip-whl_*.deb'
install_glob 'python3-setuptools-whl_*.deb'
install_glob 'python3-pip_*.deb'
install_glob 'python3.12-venv_*.deb'

dpkg --configure -a
echo "Pacotes Python 3.12/venv instalados a partir de $DEB_DIR"
