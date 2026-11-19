from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.data_migration import migrate_legacy_data
from app.paths import APP_DIR, DATA_DIR


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copia o layout antigo (data/, backups/, exports/) para ./dados."
    )
    parser.add_argument(
        "--origem",
        type=Path,
        default=APP_DIR,
        help="Pasta do app que contém data/, backups/ e exports/ (padrão: pasta do app).",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DATA_DIR,
        help="Destino da pasta de dados (padrão: TRISCORE_DATA_DIR ou ./dados).",
    )
    args = parser.parse_args()

    result = migrate_legacy_data(args.origem, args.data_dir)
    print(f"Copiados: {len(result.copied)}")
    print(f"Ignorados por já existirem: {len(result.skipped)}")
    if result.errors:
        print("Erros:", file=sys.stderr)
        for error in result.errors:
            print(f"  {error}", file=sys.stderr)
        raise SystemExit(1)
    print(f"Dados disponíveis em: {Path(args.data_dir).expanduser().resolve()}")


if __name__ == "__main__":
    main()
