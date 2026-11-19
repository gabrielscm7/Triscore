from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import init_db, resolve_db_path, transaction
from app.environment import TEST_DB_PATH
from app.services import athletes as athlete_service
from app.services import classification as classification_service
from app.services import events as event_service
from app.services import heats as heat_service
from app.services import results as result_service
from app.services import teams as team_service

TEST_EVENT = "Prova de Teste — Resultados"
DEFAULT_TEST_DB = TEST_DB_PATH


def seed(db_path: Path, *, reset: bool = False) -> None:
    if reset:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    init_db(db_path)
    with transaction(db_path) as db:
        existing = db.execute(
            "SELECT id FROM events WHERE name = ?", (TEST_EVENT,)
        ).fetchone()
        if existing is not None:
            print(f'O banco de teste já contém a prova "{TEST_EVENT}".')
            print("Use --reset para apagar o banco de teste e recriar os dados.")
            return

        event_id = event_service.create_event(
            db,
            name=TEST_EVENT,
            event_date="2026-12-06",
            location="Centro Esportivo Municipal · Cidade Teste",
        )
        event_service.update_event(
            db,
            event_id,
            name=TEST_EVENT,
            event_date="2026-12-06",
            location="Centro Esportivo Municipal · Cidade Teste",
            heat_limit=4,
            schedule_enabled=True,
            schedule_start="07:00",
            athlete_interval_seconds=60,
            heat_interval_seconds=300,
        )
        separate_id = event_service.create_category(
            db,
            event_id=event_id,
            name="Adulto 30-39",
            min_age=30,
            max_age=39,
            classification_mode="separate",
        )
        mixed_id = event_service.create_category(
            db,
            event_id=event_id,
            name="Open Misto",
            min_age=18,
            max_age=59,
            classification_mode="mixed",
        )
        team_ids = {
            name: team_service.create_team(db, event_id, name)
            for name in ("Equipe Alfa", "Equipe Beta", "Equipe Gama")
        }
        athletes = [
            ("Ana", 34, separate_id, "F", 101, "Equipe Alfa"),
            ("Bia", 36, separate_id, "F", 102, "Equipe Beta"),
            ("Caio", 32, separate_id, "M", 103, "Equipe Alfa"),
            ("Duda", 38, separate_id, "M", 104, "Equipe Gama"),
            ("Eva", 35, separate_id, "F", 105, "Equipe Beta"),
            ("Fábio", 37, separate_id, "M", 106, "Equipe Alfa"),
            ("Gabi", 27, mixed_id, "F", 201, "Equipe Beta"),
            ("Hugo", 31, mixed_id, "M", 202, "Equipe Gama"),
            ("Iara", 29, mixed_id, "F", 203, "Equipe Alfa"),
            ("João", 33, mixed_id, "M", 204, "Equipe Beta"),
            ("Kelly", 26, mixed_id, "F", 205, "Equipe Gama"),
        ]
        athlete_ids = {}
        for name, age, category_id, sex, bib, team_name in athletes:
            athlete_ids[name] = athlete_service.create_athlete(
                db,
                event_id=event_id,
                category_id=category_id,
                name=name,
                age=age,
                team_id=team_ids[team_name],
                sex=sex,
                bib=bib,
            )

        event = event_service.get_event(db, event_id)
        heat_service.generate_heats(
            db,
            event,
            category_id=separate_id,
            sex_mode="F",
            criterion="alpha",
        )
        heat_service.generate_heats(
            db,
            event,
            category_id=separate_id,
            sex_mode="M",
            criterion="bib",
        )
        heat_service.generate_heats(
            db,
            event,
            category_id=mixed_id,
            sex_mode="X",
            criterion="bib",
        )

        for name, status, final_time_cs in (
            ("Ana", "OK", 390000),
            ("Bia", "OK", 390000),
            ("Caio", "OK", 378000),
            ("Duda", "DNF", None),
            ("Eva", "DSQ", None),
            ("Gabi", "OK", 270000),
            ("Hugo", "OK", 261000),
            ("Iara", "OK", 261000),
            ("João", "DNS", None),
        ):
            result_service.save_result(
                db,
                event_id=event_id,
                athlete_id=athlete_ids[name],
                status=status,
                final_time_cs=final_time_cs,
            )
        classification_service.update_tiebreak(db, event_id, "real")

    print(f"Banco de teste criado em: {db_path}")
    print("Inclui empate no pódio, DNF, DSQ e atletas sem resultado.")
    print("Abra com:")
    print(f"  python run.py --modo teste --db {db_path} --no-browser")
    print("Para apagar e recriar:")
    print("  python scripts/seed_test_results.py --reset")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cria um banco descartável com resultados fictícios para testes."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_TEST_DB,
        help="Caminho do banco de teste.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Apaga o banco de teste antes de recriar.",
    )
    args = parser.parse_args()
    seed(resolve_db_path(args.db), reset=args.reset)


if __name__ == "__main__":
    main()
