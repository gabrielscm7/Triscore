from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

AUDITED_SUFFIXES = {".html", ".css", ".js", ".svg"}
ALLOWED_URL_PARTS = ("www.w3.org/",)
URL_PATTERN = re.compile(
    r"""(?ix)
    https?://[^\s"'()<>]+
    |
    //[a-z0-9][a-z0-9.-]*\.[a-z]{2,}(?:/[^\s"'()<>]*)?
    """
)


@dataclass(frozen=True)
class ExternalReference:
    path: Path
    line: int
    value: str


def scan_external_references(root: str | Path) -> list[ExternalReference]:
    base = Path(root)
    findings: list[ExternalReference] = []
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in AUDITED_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(content.splitlines(), start=1):
            for match in URL_PATTERN.finditer(line):
                value = match.group(0)
                if any(part in value for part in ALLOWED_URL_PARTS):
                    continue
                findings.append(
                    ExternalReference(path=path, line=number, value=value)
                )
    return findings
