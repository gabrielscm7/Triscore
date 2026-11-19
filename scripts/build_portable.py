from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COPY_ITEMS = (
    "app",
    "scripts",
    "tests",
    "examples",
    "docs",
    "run.py",
    "TriScore.sh",
    "iniciar.sh",
    "TriScore.desktop",
    "instalar_atalho.sh",
    "instalar_debs.sh",
    "verificar.sh",
    "build.sh",
    "pytest.ini",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-lock.txt",
    "requirements-build.txt",
    "README.md",
)
IGNORE = shutil.ignore_patterns(
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    ".ruff_cache",
    "*.db",
    "*.db-wal",
    "*.db-shm",
)

EXPECTED_WHEELS = 29


def _copy_item(item: str, target: Path) -> None:
    source = PROJECT_ROOT / item
    if not source.exists():
        raise FileNotFoundError(f"Item obrigatório não encontrado: {source}")
    if source.is_dir():
        shutil.copytree(source, target / item, ignore=IGNORE)
    else:
        shutil.copy2(source, target / item)


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def _docker_build(package: Path) -> None:
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError(
            "Docker não encontrado. O wheelhouse/venv do alvo Ubuntu 24.04 "
            "precisa ser gerado em contêiner. Use --skip-wheels apenas em desenvolvimento."
        )

    uid = os.getuid()
    gid = os.getgid()
    script = r"""
set -euo pipefail
cd /src
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends python3.12 python3.12-venv python3-pip ca-certificates

rm -rf /pkg/wheels /pkg/debs /pkg/.venv
mkdir -p /pkg/wheels /pkg/debs

download_wheel() {
  spec="$1"
  python3.12 -m pip download --no-cache-dir --no-deps --only-binary=:all: \
    --platform manylinux_2_28_x86_64 --python-version 3.12 \
    --implementation cp --abi cp312 -d /pkg/wheels "$spec" && return 0
  python3.12 -m pip download --no-cache-dir --no-deps --only-binary=:all: \
    --platform manylinux2014_x86_64 --python-version 3.12 \
    --implementation cp --abi cp312 -d /pkg/wheels "$spec"
}

while IFS= read -r spec; do
  spec="${spec%%#*}"
  spec="$(echo "$spec" | xargs)"
  [ -z "$spec" ] && continue
  download_wheel "$spec"
done < requirements-lock.txt

python3.12 - <<'PY'
from pathlib import Path
import sys

wheels = list(Path("/pkg/wheels").glob("*.whl"))
sdists = list(Path("/pkg/wheels").glob("*.tar.gz")) + list(Path("/pkg/wheels").glob("*.zip"))
bad_abi = [p.name for p in wheels if "cp314" in p.name]
bad_platform = [p.name for p in wheels if "linux_x86_64" in p.name and "manylinux" not in p.name]
if sdists:
    raise SystemExit(f"wheelhouse contem fontes: {[p.name for p in sdists]}")
if bad_abi:
    raise SystemExit(f"wheelhouse contem cp314: {bad_abi}")
if bad_platform:
    raise SystemExit(f"wheelhouse contem wheel fora de manylinux: {bad_platform}")
if len(wheels) < 29:
    raise SystemExit(f"wheelhouse incompleto: {len(wheels)} wheels")
print(f"wheelhouse ok: {len(wheels)} wheels")
PY

(cd /pkg/wheels && sha256sum *.whl | sort > MANIFEST.sha256)

python3.12 -m venv --copies /pkg/.venv
/pkg/.venv/bin/python -m pip install --no-index --find-links /pkg/wheels \
  -r /pkg/requirements-lock.txt

mkdir -p /tmp/debs && cd /tmp/debs
for pkg in \
  python3.12 python3.12-minimal python3.12-venv \
  libpython3.12-minimal libpython3.12-stdlib \
  python3-minimal python3 libpython3-stdlib \
  libexpat1 media-types netbase tzdata \
  readline-common libreadline8t64 libsqlite3-0 \
  openssl ca-certificates python3-pkg-resources \
  python3-pip python3-pip-whl python3-setuptools \
  python3-setuptools-whl python3-wheel; do
  apt-get download "$pkg" || true
done
cp /tmp/debs/*.deb /pkg/debs/ 2>/dev/null || true
ls -1 /pkg/debs/*.deb >/dev/null 2>&1 || { echo "Nenhum .deb baixado" >&2; exit 1; }
cd /src

{
  echo "target_os=Ubuntu 24.04 LTS"
  . /etc/os-release
  echo "build_os=$PRETTY_NAME"
  echo "build_arch=$(uname -m)"
  echo "build_python=$(python3.12 --version 2>&1)"
  echo "build_glibc=$(ldd --version | head -n 1)"
  echo "wheels=$(find /pkg/wheels -maxdepth 1 -name '*.whl' | wc -l | tr -d ' ')"
  echo "venv_python=$(/pkg/.venv/bin/python --version 2>&1)"
  echo "built_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > /pkg/BUILD-INFO.txt

chown -R "${HOST_UID}:${HOST_GID}" /pkg
"""
    _run(
        [
            docker,
            "run",
            "--rm",
            "-e",
            f"HOST_UID={uid}",
            "-e",
            f"HOST_GID={gid}",
            "-v",
            f"{PROJECT_ROOT}:/src:ro",
            "-v",
            f"{package}:/pkg",
            "-w",
            "/src",
            "ubuntu:24.04",
            "bash",
            "-c",
            script,
        ]
    )


def _write_checksums(package: Path) -> None:
    checksums = []
    for path in sorted(package.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        checksums.append(f"{digest}  {path.relative_to(package)}")
    (package / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8")


def _make_archive(package: Path, output: Path) -> Path:
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "0")) or int(datetime.now().timestamp())
    archive = output / f"{package.name}.tar.gz"
    _run(
        [
            "tar",
            "--sort=name",
            "--owner=0",
            "--group=0",
            "--numeric-owner",
            f"--mtime=@{epoch}",
            "-czf",
            str(archive),
            "-C",
            str(output),
            package.name,
        ]
    )
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / f"{archive.name}.sha256").write_text(
        f"{digest}  {archive.name}\n", encoding="utf-8"
    )
    return archive


def build_package(output: Path, args: argparse.Namespace) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    package = output / f"triscore-portatil-{stamp}"
    package.mkdir(parents=True, exist_ok=False)

    for item in COPY_ITEMS:
        _copy_item(item, package)

    readme = PROJECT_ROOT / "docs" / "README-PORTATIL.md"
    shutil.copy2(readme, package / "README-PORTATIL.md")

    for directory in (
        "dados/banco",
        "dados/backups",
        "dados/exports",
        "dados/uploads",
        "dados/logs",
        "dados/teste/banco",
        "dados/teste/backups",
        "dados/teste/exports",
        "dados/teste/uploads",
        "dados/teste/logs",
    ):
        (package / directory).mkdir(parents=True, exist_ok=True)
        (package / directory / ".gitkeep").touch()
    (package / "dados/.gitkeep").touch()

    if args.skip_wheels:
        (package / "wheels").mkdir()
        (package / "wheels" / "LEIA-ME.txt").write_text(
            "Pacote gerado com --skip-wheels (apenas desenvolvimento).\n",
            encoding="utf-8",
        )
        (package / "debs").mkdir()
        (package / "debs" / "LEIA-ME.txt").write_text(
            "Pacote gerado com --skip-wheels (apenas desenvolvimento).\n",
            encoding="utf-8",
        )
    else:
        _docker_build(package)

    _write_checksums(package)
    print(f"\nPacote portátil criado em: {package}")
    if args.tar_gz:
        archive = _make_archive(package, output)
        print(f"Tar.gz criado em: {archive}")
    return package


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera o pacote portátil do Triscore para Ubuntu 24.04 x86_64."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "dist",
        help="Pasta onde o pacote será criado (padrão: dist/).",
    )
    parser.add_argument(
        "--skip-wheels",
        action="store_true",
        help="Gera o pacote sem wheels/.venv/debs (apenas desenvolvimento).",
    )
    parser.add_argument(
        "--no-tar-gz",
        dest="tar_gz",
        action="store_false",
        help="Não cria o arquivo .tar.gz.",
    )
    parser.set_defaults(tar_gz=True)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    build_package(args.output.resolve(), args)


if __name__ == "__main__":
    main()
