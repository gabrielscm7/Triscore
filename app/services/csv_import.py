from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import unicodedata
import uuid
from collections import Counter
from typing import Any

from app.services import athletes as athlete_service
from app.services import events as event_service
from app.services import teams as team_service
from app.utils import age_warning, clean_text

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10_000

FIELD_ALIASES = {
    "name": {"nome", "atleta", "nome_atleta", "nome_completo"},
    "age": {"idade", "anos"},
    "category": {"categoria", "grupo", "faixa", "faixa_etaria"},
    "team": {"equipe", "time", "clube", "associacao", "agremiacao"},
    "sex": {"sexo", "genero"},
    "bib": {
        "peito",
        "numero_peito",
        "n_peito",
        "no_peito",
        "n_de_peito",
        "no_de_peito",
        "n_do_peito",
        "no_do_peito",
        "numero",
        "num_peito",
    },
}

FIELD_LABELS = {
    "name": "Nome",
    "age": "Idade",
    "category": "Categoria",
    "team": "Equipe",
    "sex": "Sexo",
    "bib": "Nº de peito",
}

REQUIRED_FIELDS = ("name", "age", "category", "sex")
SEX_ALIASES = {
    "M": "M",
    "MASC": "M",
    "MASCULINO": "M",
    "H": "M",
    "HOMEM": "M",
    "F": "F",
    "FEM": "F",
    "FEMININO": "F",
    "MULHER": "F",
}


class CSVImportError(Exception):
    pass


def normalize_header(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CSVImportError("Não foi possível identificar a codificação do arquivo.")


def _delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:20])
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except csv.Error:
        first_line = text.splitlines()[0] if text.splitlines() else ""
        counts = {delimiter: first_line.count(delimiter) for delimiter in (",", ";", "\t")}
        return max(counts, key=counts.get) if max(counts.values()) else ";"


def parse_csv(content: bytes) -> list[dict[str, Any]]:
    if len(content) > MAX_FILE_BYTES:
        raise CSVImportError("O arquivo excede o limite de 5 MB.")
    if not content.strip():
        raise CSVImportError("O arquivo está vazio.")
    text = _decode(content)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=_delimiter(text))

    header: list[str] | None = None
    header_line = 0
    parsed_rows: list[tuple[int, list[str]]] = []
    for line_number, row in enumerate(reader, start=1):
        if not any(str(cell).strip() for cell in row):
            continue
        if header is None:
            header = [str(cell).strip() for cell in row]
            header_line = line_number
            continue
        parsed_rows.append((line_number, [str(cell).strip() for cell in row]))
        if len(parsed_rows) > MAX_ROWS:
            raise CSVImportError(f"O arquivo excede o limite de {MAX_ROWS} linhas.")

    if header is None:
        raise CSVImportError("O arquivo não possui cabeçalho.")
    if not parsed_rows:
        raise CSVImportError("O arquivo não possui linhas de dados.")

    normalized_headers = [normalize_header(cell) for cell in header]
    mapping: dict[str, int] = {}
    for field, aliases in FIELD_ALIASES.items():
        for index, normalized in enumerate(normalized_headers):
            if normalized in aliases:
                mapping[field] = index
                break

    missing = [FIELD_LABELS[field] for field in REQUIRED_FIELDS if field not in mapping]
    if missing:
        raise CSVImportError(
            "Cabeçalhos obrigatórios ausentes: "
            + ", ".join(missing)
            + ". Use nome, idade, categoria e sexo; equipe e peito são opcionais."
        )

    result: list[dict[str, Any]] = []
    for line_number, row in parsed_rows:
        values = {field: "" for field in FIELD_ALIASES}
        for field, index in mapping.items():
            values[field] = str(row[index]).strip() if index < len(row) else ""
        raw = {
            header[index] if index < len(header) else f"coluna_{index + 1}": (
                row[index] if index < len(row) else ""
            )
            for index in range(max(len(header), len(row)))
        }
        result.append(
            {
                "line": line_number,
                "raw": raw,
                "values": values,
                "header_line": header_line,
            }
        )
    return result


def _category_map(categories: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {category["name"].casefold(): category for category in categories}


def _team_map(teams: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {team["name"].casefold(): team for team in teams}


def _bib_counts(rows: list[dict[str, Any]]) -> Counter:
    counts: Counter = Counter()
    for row in rows:
        raw = clean_text(row["values"].get("bib"))
        if raw.isdigit() and int(raw) > 0:
            counts[int(raw)] += 1
    return counts


def validate_values(
    values: dict[str, Any],
    categories: dict[str, dict[str, Any]],
    teams: dict[str, dict[str, Any]],
    existing_bibs: set[int],
    duplicate_bibs: Counter,
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    name = clean_text(values.get("name"), 120)
    team = clean_text(values.get("team"))
    category_name = clean_text(values.get("category"))
    category_key = category_name.casefold()
    team_key = team.casefold()

    if not name:
        errors.append("Nome obrigatório.")

    age_raw = clean_text(values.get("age"))
    age: int | None = None
    if not age_raw:
        errors.append("Idade obrigatória.")
    else:
        try:
            age = int(age_raw)
        except ValueError:
            errors.append("Idade inválida.")
        else:
            if not 1 <= age <= 120:
                errors.append("Idade deve estar entre 1 e 120.")

    if not category_name:
        errors.append("Categoria obrigatória.")
    elif len(category_name) > 80:
        errors.append("Categoria deve ter no máximo 80 caracteres.")

    if len(team) > 120:
        errors.append("Equipe deve ter no máximo 120 caracteres.")

    sex_raw = clean_text(values.get("sex"))
    sex = SEX_ALIASES.get(sex_raw.upper())
    if not sex_raw:
        errors.append("Sexo obrigatório.")
    elif sex is None:
        errors.append("Sexo inválido; use M/F ou masculino/feminino.")

    bib_raw = clean_text(values.get("bib"))
    bib: int | None = None
    if bib_raw:
        try:
            bib = int(bib_raw)
        except ValueError:
            errors.append("Número de peito inválido.")
        else:
            if bib <= 0:
                errors.append("Número de peito deve ser maior que zero.")
            elif duplicate_bibs.get(bib, 0) > 1:
                errors.append(f"Peito {bib} duplicado dentro do arquivo.")
            elif bib in existing_bibs:
                errors.append(f"Peito {bib} já está em uso nesta prova.")

    category = categories.get(category_key) if category_key else None
    if category_name and len(category_name) <= 80 and category is None:
        warnings.append(
            f"Categoria “{category_name}” não existe e será criada sem faixa etária."
        )
    if category is not None and age is not None:
        warning = age_warning(age, category["min_age"], category["max_age"])
        if warning:
            warnings.append(warning)

    team_entity = teams.get(team_key) if team_key else None
    if team and len(team) <= 120 and team_entity is None:
        warnings.append(f"Equipe “{team}” não existe e será criada.")

    if errors:
        return None, errors, warnings
    return (
        {
            "name": name,
            "age": age,
            "team": team,
            "team_key": team_key,
            "team_entity": team_entity,
            "category_name": category_name,
            "category": category,
            "sex": sex,
            "bib": bib,
        },
        errors,
        warnings,
    )


def prepare_batch(
    connection: sqlite3.Connection,
    *,
    event_id: int,
    filename: str,
    content: bytes,
) -> str:
    parsed = parse_csv(content)
    categories = _category_map(event_service.list_categories(connection, event_id))
    teams = _team_map(team_service.list_teams(connection, event_id))
    existing_bibs = {
        int(row["bib"])
        for row in connection.execute(
            "SELECT bib FROM athletes WHERE event_id = ?", (event_id,)
        ).fetchall()
    }
    duplicates = _bib_counts(parsed)
    batch_id = uuid.uuid4().hex
    connection.execute(
        "INSERT INTO import_batches (id, event_id, filename) VALUES (?, ?, ?)",
        (batch_id, event_id, clean_text(filename, 180) or "atletas.csv"),
    )

    for row in parsed:
        errors, warnings = [], []
        _, errors, warnings = validate_values(
            row["values"], categories, teams, existing_bibs, duplicates
        )
        status = "ERROR" if errors else ("WARNING" if warnings else "VALID")
        connection.execute(
            """
            INSERT INTO import_rows
                (batch_id, row_number, raw_json, normalized_json, errors_json, warnings_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                row["line"],
                json.dumps(row["raw"], ensure_ascii=False),
                json.dumps(row["values"], ensure_ascii=False),
                json.dumps(errors, ensure_ascii=False),
                json.dumps(warnings, ensure_ascii=False),
                status,
            ),
        )
    return batch_id


def get_batch(
    connection: sqlite3.Connection, event_id: int, batch_id: str
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM import_batches WHERE id = ? AND event_id = ?",
        (batch_id, event_id),
    ).fetchone()
    return dict(row) if row is not None else None


def preview_batch(
    connection: sqlite3.Connection, event_id: int, batch_id: str
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], dict[str, Any]]:
    batch = get_batch(connection, event_id, batch_id)
    if batch is None:
        return None, [], {}
    rows = connection.execute(
        "SELECT * FROM import_rows WHERE batch_id = ? ORDER BY row_number", (batch_id,)
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["values"] = json.loads(item["normalized_json"])
        item["errors"] = json.loads(item["errors_json"])
        item["warnings"] = json.loads(item["warnings_json"])
        result.append(item)
    categories = _category_map(event_service.list_categories(connection, event_id))
    teams = _team_map(team_service.list_teams(connection, event_id))
    new_categories: dict[str, str] = {}
    new_teams: dict[str, str] = {}
    for row in result:
        if row["status"] == "ERROR":
            continue
        category_name = clean_text(row["values"].get("category"))
        category_key = category_name.casefold()
        if (
            category_name
            and len(category_name) <= 80
            and category_key not in categories
        ):
            new_categories.setdefault(category_key, category_name)
        team_name = clean_text(row["values"].get("team"))
        team_key = team_name.casefold()
        if team_name and len(team_name) <= 120 and team_key not in teams:
            new_teams.setdefault(team_key, team_name)
    counts = {
        "total": len(result),
        "valid": sum(1 for row in result if row["status"] == "VALID"),
        "warning": sum(1 for row in result if row["status"] == "WARNING"),
        "error": sum(1 for row in result if row["status"] == "ERROR"),
        "new_categories": list(new_categories.values()),
        "new_teams": list(new_teams.values()),
    }
    return batch, result, counts


def cancel_batch(
    connection: sqlite3.Connection, event_id: int, batch_id: str
) -> bool:
    cursor = connection.execute(
        "DELETE FROM import_batches WHERE id = ? AND event_id = ?",
        (batch_id, event_id),
    )
    return cursor.rowcount > 0


def errors_csv(connection: sqlite3.Connection, event_id: int, batch_id: str) -> bytes:
    batch, rows, _ = preview_batch(connection, event_id, batch_id)
    if batch is None:
        raise CSVImportError("Prévia de importação não encontrada.")
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "linha",
            "nome",
            "idade",
            "categoria",
            "equipe",
            "sexo",
            "peito",
            "erros",
            "avisos",
        ]
    )
    for row in rows:
        values = row["values"]
        writer.writerow(
            [
                row["row_number"],
                values.get("name", ""),
                values.get("age", ""),
                values.get("category", ""),
                values.get("team", ""),
                values.get("sex", ""),
                values.get("bib", ""),
                " | ".join(row["errors"]),
                " | ".join(row["warnings"]),
            ]
        )
    return output.getvalue().encode("utf-8-sig")


def confirm_batch(
    connection: sqlite3.Connection, event_id: int, batch_id: str
) -> dict[str, Any]:
    batch, rows, _ = preview_batch(connection, event_id, batch_id)
    if batch is None:
        raise CSVImportError("Prévia de importação não encontrada.")

    categories = _category_map(event_service.list_categories(connection, event_id))
    teams = _team_map(team_service.list_teams(connection, event_id))
    existing_bibs = {
        int(row["bib"])
        for row in connection.execute(
            "SELECT bib FROM athletes WHERE event_id = ?", (event_id,)
        ).fetchall()
    }
    duplicate_bibs = _bib_counts(rows)
    skipped: list[str] = []
    candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []

    for row in rows:
        parsed, errors, _ = validate_values(
            row["values"], categories, teams, existing_bibs, duplicate_bibs
        )
        if errors:
            skipped.append(f"Linha {row['row_number']}: {errors[0]}")
            continue
        candidates.append((row, parsed))

    categories_created = 0
    teams_created = 0
    for _, parsed in candidates:
        category_key = parsed["category_name"].casefold()
        if parsed["category"] is None and category_key not in categories:
            category_id = event_service.create_category(
                connection,
                event_id=event_id,
                name=parsed["category_name"],
                min_age=None,
                max_age=None,
            )
            category = event_service.get_category(connection, event_id, category_id)
            if category is not None:
                categories[category_key] = category
                categories_created += 1
        team_key = parsed["team_key"]
        if team_key and team_key not in teams:
            team = team_service.get_or_create_team(
                connection, event_id, parsed["team"]
            )
            teams[team_key] = team
            teams_created += 1

    imported = 0
    for row, parsed in candidates:
        category = categories.get(parsed["category_name"].casefold())
        if category is None:
            skipped.append(
                f"Linha {row['row_number']}: não foi possível criar a categoria."
            )
            continue
        team = teams.get(parsed["team_key"]) if parsed["team_key"] else None
        try:
            athlete_service.create_athlete(
                connection,
                event_id=event_id,
                category_id=category["id"],
                name=parsed["name"],
                age=parsed["age"],
                team_id=team["id"] if team is not None else None,
                sex=parsed["sex"],
                bib=parsed["bib"],
            )
        except sqlite3.IntegrityError:
            skipped.append(
                f"Linha {row['row_number']}: conflito de número de peito ou dados."
            )
            continue

        imported += 1
        if parsed["bib"] is not None:
            existing_bibs.add(parsed["bib"])

    connection.execute("DELETE FROM import_batches WHERE id = ?", (batch_id,))
    return {
        "imported": imported,
        "skipped": skipped,
        "categories_created": categories_created,
        "teams_created": teams_created,
    }
