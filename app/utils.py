from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from fastapi.responses import RedirectResponse


def clean_text(value: str | None, max_length: int | None = None) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip())
    if max_length is not None:
        return text[:max_length]
    return text


def parse_optional_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return int(text)


def parse_date_input(value: str | None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    parsed = datetime.strptime(text, "%Y-%m-%d").date()
    return parsed.isoformat()


def display_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return value


def parse_clock_minutes(value: str | None, default: str = "08:00") -> tuple[int, int]:
    text = clean_text(value) or default
    parsed = datetime.strptime(text, "%H:%M")
    return parsed.hour, parsed.minute


def age_range_label(min_age: int | None, max_age: int | None) -> str:
    if min_age is None and max_age is None:
        return "Sem faixa etária"
    if min_age is not None and max_age is not None:
        return f"{min_age} a {max_age} anos"
    if min_age is not None:
        return f"{min_age}+ anos"
    return f"Até {max_age} anos"


def age_warning(age: int | None, min_age: int | None, max_age: int | None) -> str | None:
    if age is None or (min_age is None and max_age is None):
        return None
    if min_age is not None and age < min_age:
        return f"Idade {age} abaixo da faixa da categoria ({age_range_label(min_age, max_age)})."
    if max_age is not None and age > max_age:
        return f"Idade {age} acima da faixa da categoria ({age_range_label(min_age, max_age)})."
    return None


def next_bib(connection: sqlite3.Connection, event_id: int) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(bib), 0) + 1 AS next_bib FROM athletes WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    return int(row["next_bib"])


def excel_label(index: int) -> str:
    if index < 0:
        raise ValueError("O índice do rótulo deve ser positivo.")
    label = ""
    current = index + 1
    while current:
        current, remainder = divmod(current - 1, 26)
        label = chr(65 + remainder) + label
    return label


def sort_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return normalized.encode("ascii", "ignore").decode("ascii").casefold()


def mode_label(mode: str) -> str:
    return {"M": "Masculino", "F": "Feminino", "X": "Misto"}.get(mode, mode)


def format_seconds_as_clock(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def build_schedule(
    heats: list[dict[str, Any]], event: dict[str, Any]
) -> None:
    if not event["schedule_enabled"]:
        return
    try:
        hour, minute = parse_clock_minutes(event["schedule_start"])
    except ValueError:
        hour, minute = 8, 0
    start_day = date.today()
    if event.get("event_date"):
        try:
            start_day = date.fromisoformat(event["event_date"])
        except ValueError:
            pass
    cursor = datetime.combine(start_day, datetime.min.time()).replace(hour=hour, minute=minute)
    athlete_interval = timedelta(seconds=int(event["athlete_interval_seconds"]))
    heat_interval = timedelta(seconds=int(event["heat_interval_seconds"]))
    base_day = start_day

    def label(moment: datetime) -> str:
        if moment.date() > base_day:
            return moment.strftime("%d/%m %H:%M")
        return moment.strftime("%H:%M")

    for heat in sorted(heats, key=lambda item: item["sequence"]):
        entries = heat["entries"]
        if not entries:
            heat["scheduled_start"] = None
            continue
        heat["scheduled_start"] = label(cursor)
        for index, entry in enumerate(entries):
            entry["scheduled_time"] = label(cursor + athlete_interval * index)
        cursor = cursor + athlete_interval * (len(entries) - 1) + heat_interval


def redirect_with(
    url: str,
    *,
    ok: str | None = None,
    error: str | None = None,
    warning: str | None = None,
    status_code: int = 303,
) -> RedirectResponse:
    params: dict[str, str] = {}
    if ok:
        params["ok"] = ok
    if error:
        params["error"] = error
    if warning:
        params["warning"] = warning
    if params:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode(params)}"
    return RedirectResponse(url=url, status_code=status_code)
