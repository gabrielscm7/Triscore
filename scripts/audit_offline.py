from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.offline_audit import scan_external_references


def main() -> None:
    findings = scan_external_references(PROJECT_ROOT / "app")
    if findings:
        print("URLs externas encontradas:")
        for item in findings:
            relative = item.path.relative_to(PROJECT_ROOT)
            print(f"  {relative}:{item.line}  {item.value}")
        raise SystemExit(1)
    print(
        "Auditoria offline OK: nenhuma URL externa em templates, CSS, JS ou SVG. "
        "O namespace xmlns do SVG (www.w3.org) não é uma requisição de rede."
    )


if __name__ == "__main__":
    main()
