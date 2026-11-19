from __future__ import annotations

import argparse
import socket
import sys
import tempfile
from contextlib import contextmanager, nullcontext
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.database import connect
from app.main import create_app
from app.services.offline_audit import scan_external_references


@contextmanager
def block_external_network():
    original = socket.socket.connect

    def guarded(instance, address):
        if isinstance(address, tuple) and address:
            host = str(address[0])
            if host not in ("127.0.0.1", "::1", "localhost"):
                raise RuntimeError(f"Rede externa bloqueada durante o smoke test: {host}")
        return original(instance, address)

    socket.socket.connect = guarded
    try:
        yield
    finally:
        socket.socket.connect = original


def _event_id(response) -> int:
    assert response.status_code == 303, response.text
    return int(response.headers["location"].split("/")[2])


def _query_one(app, sql: str, params: tuple = ()) -> dict:
    connection = connect(app.state.db_path)
    try:
        row = connection.execute(sql, params).fetchone()
    finally:
        connection.close()
    assert row is not None, f"Consulta sem resultado: {sql}"
    return dict(row)


def run_smoke(work_dir: str | Path | None = None, *, block_network: bool = True) -> list[str]:
    base = Path(work_dir) if work_dir is not None else Path(tempfile.mkdtemp())
    test_dir = base / "teste"
    test_dir.mkdir(parents=True, exist_ok=True)
    db_path = test_dir / "triscore-smoke.db"
    checks: list[str] = []

    guard = block_external_network() if block_network else nullcontext()
    with guard:
        app = create_app(db_path)
        with TestClient(app) as client:
            assert "MODO TESTE" in client.get("/eventos").text
            checks.append("Faixa MODO TESTE visível no ambiente de teste")

            response = client.post(
                "/eventos",
                data={
                    "name": "Prova Smoke 2026",
                    "event_date": "2026-12-12",
                    "location": "Arena de Teste",
                },
                follow_redirects=False,
            )
            event_id = _event_id(response)
            checks.append("Prova fictícia criada")

            response = client.post(
                f"/eventos/{event_id}/configuracao",
                data={
                    "name": "Prova Smoke 2026",
                    "event_date": "2026-12-12",
                    "location": "Arena de Teste",
                    "heat_limit": "2",
                    "schedule_enabled": "1",
                    "schedule_start": "07:00",
                    "athlete_interval_seconds": "30",
                    "heat_interval_seconds": "120",
                },
                follow_redirects=False,
            )
            assert response.status_code == 303
            checks.append("Configuração e cronograma salvos")

            for name, mode in (("Adulto 30-39", "separate"), ("Open Misto", "mixed")):
                response = client.post(
                    f"/eventos/{event_id}/categorias",
                    data={
                        "name": name,
                        "min_age": "18",
                        "max_age": "59",
                        "classification_mode": mode,
                    },
                    follow_redirects=False,
                )
                assert response.status_code == 303
            adult = _query_one(
                app,
                "SELECT id FROM categories WHERE event_id = ? AND name = ?",
                (event_id, "Adulto 30-39"),
            )["id"]
            mixed = _query_one(
                app,
                "SELECT id FROM categories WHERE event_id = ? AND name = ?",
                (event_id, "Open Misto"),
            )["id"]
            checks.append("Categorias separada e mista criadas")

            response = client.post(
                f"/eventos/{event_id}/equipes",
                data={"name": "Equipe Smoke"},
                follow_redirects=False,
            )
            assert response.status_code == 303
            team = _query_one(
                app,
                "SELECT id FROM teams WHERE event_id = ? AND name = ?",
                (event_id, "Equipe Smoke"),
            )["id"]

            athletes = (
                ("Ana Smoke", 34, adult, "F", "101"),
                ("Bia Smoke", 36, adult, "F", "102"),
                ("Caio Smoke", 32, adult, "M", "103"),
                ("Davi Smoke", 38, adult, "M", "104"),
                ("Eva Smoke", 28, mixed, "F", "201"),
                ("Fábio Smoke", 33, mixed, "M", "202"),
            )
            for name, age, category_id, sex, bib in athletes:
                response = client.post(
                    f"/eventos/{event_id}/atletas/novo",
                    data={
                        "name": name,
                        "age": str(age),
                        "category_id": str(category_id),
                        "team_id": str(team),
                        "sex": sex,
                        "bib": bib,
                    },
                    follow_redirects=False,
                )
                assert response.status_code == 303, response.text
            checks.append("Seis atletas fictícios cadastrados")

            for category_id, mode in (
                (adult, "F"),
                (adult, "M"),
                (mixed, "X"),
            ):
                response = client.post(
                    f"/eventos/{event_id}/baterias/gerar",
                    data={
                        "category_id": str(category_id),
                        "sex_mode": mode,
                        "criterion": "bib",
                    },
                    follow_redirects=False,
                )
                assert response.status_code == 303
            heat_count = _query_one(
                app,
                "SELECT COUNT(*) AS total FROM heats WHERE event_id = ?",
                (event_id,),
            )["total"]
            assert heat_count >= 3
            checks.append(f"{heat_count} baterias geradas")

            connection = connect(app.state.db_path)
            try:
                athlete_rows = connection.execute(
                    "SELECT id, bib FROM athletes WHERE event_id = ?", (event_id,)
                ).fetchall()
            finally:
                connection.close()
            by_bib = {int(row["bib"]): int(row["id"]) for row in athlete_rows}
            results = (
                (101, "OK", "40:00.00"),
                (102, "OK", "40:00.00"),
                (103, "OK", "38:00.00"),
                (104, "DNF", ""),
                (201, "OK", "35:00.00"),
                (202, "OK", "36:00.00"),
            )
            for bib, status, final_time in results:
                response = client.post(
                    f"/eventos/{event_id}/sumula/{by_bib[bib]}",
                    data={"status": status, "final_time": final_time},
                    follow_redirects=False,
                )
                assert response.status_code == 303
            checks.append("Tempos, empate, DNF e demais resultados lançados")

            backups = list(app.state.backup_dir.glob("triscore-pre-sumula-*.db"))
            assert len(backups) >= len(results)
            checks.append(f"{len(backups)} backups automáticos da súmula confirmados")

            response = client.post(
                f"/eventos/{event_id}/classificacao/desempate",
                data={"tiebreak": "real"},
                follow_redirects=False,
            )
            assert response.status_code == 303
            classification = client.get(f"/eventos/{event_id}/classificacao")
            assert classification.status_code == 200
            assert "Ana Smoke" in classification.text
            assert "DNF" in classification.text
            checks.append("Classificação por categoria e empate real conferidos")

            pdf_paths = (
                "cronograma",
                "lista-largada",
                "relatorio-final",
            )
            for kind in pdf_paths:
                response = client.get(f"/eventos/{event_id}/pdfs/{kind}")
                assert response.status_code == 200, response.text
                assert response.content.startswith(b"%PDF")
            awards_page = client.get(f"/premiacao/{event_id}")
            assert awards_page.status_code == 200
            assert "Prova Smoke 2026" in awards_page.text
            assert "MODO TESTE" in awards_page.text
            awards_pdf = client.get(f"/premiacao/{event_id}/pdf")
            assert awards_pdf.status_code == 200
            assert awards_pdf.content.startswith(b"%PDF")
            checks.append("PDFs de cronograma, largada, relatório e premiação gerados")

            destination = base / "pendrive"
            destination.mkdir()
            response = client.post(
                "/backup",
                data={"destination": str(destination)},
                follow_redirects=False,
            )
            assert response.status_code == 303, response.text
            folders = list(destination.glob("triscore-backup-teste-*"))
            assert len(folders) == 1
            backup = folders[0]
            assert (backup / db_path.name).exists()
            assert (backup / "manifest.json").exists()
            copied_pdfs = list((backup / "exports").glob("*.pdf"))
            assert len(copied_pdfs) >= 4
            checks.append(
                f"Backup manual copiou o banco e {len(copied_pdfs)} PDFs para {backup}"
            )

            findings = scan_external_references(PROJECT_ROOT / "app")
            assert findings == []
            checks.append("Auditoria offline sem URLs externas")

    return checks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Executa o smoke test do fluxo completo com dados fictícios."
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Pasta de trabalho. Sem ela, usa um diretório temporário.",
    )
    parser.add_argument(
        "--permitir-rede",
        action="store_true",
        help="Não bloqueia conexões externas durante o teste.",
    )
    args = parser.parse_args()
    checks = run_smoke(args.work_dir, block_network=not args.permitir_rede)
    print("\nSmoke test concluído com sucesso:")
    for item in checks:
        print(f"  [ok] {item}")


if __name__ == "__main__":
    main()
