from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import init_db, resolve_db_path, transaction
from app.services import athletes as athlete_service
from app.services import events as event_service
from app.services import heats as heat_service
from app.services import teams as team_service

DEMO_EVENT = "Triatlo das Montanhas 2026"
SECOND_EVENT = "Copa Cidade 2026"


def seed(db_path: Path) -> None:
    init_db(db_path)
    with transaction(db_path) as db:
        existing = db.execute(
            "SELECT id FROM events WHERE name = ?", (DEMO_EVENT,)
        ).fetchone()
        if existing is not None:
            print(f'O banco já contém a prova de demonstração "{DEMO_EVENT}".')
            print("Nada foi duplicado. Abra a aplicação para visualizar os dados.")
            return

        event_id = event_service.create_event(
            db,
            name=DEMO_EVENT,
            event_date="2026-09-13",
            location="Serra do Capivari · São Paulo",
        )
        event_service.update_event(
            db,
            event_id,
            name=DEMO_EVENT,
            event_date="2026-09-13",
            location="Serra do Capivari · São Paulo",
            heat_limit=4,
            schedule_enabled=True,
            schedule_start="07:00",
            athlete_interval_seconds=60,
            heat_interval_seconds=300,
        )

        category_defs = [
            ("Elite 18-29", 18, 29),
            ("Adulto 30-39", 30, 39),
            ("Master 40-49", 40, 49),
            ("Veterano 50-59", 50, 59),
        ]
        category_ids: dict[str, int] = {}
        for name, min_age, max_age in category_defs:
            category_ids[name] = event_service.create_category(
                db,
                event_id=event_id,
                name=name,
                min_age=min_age,
                max_age=max_age,
            )

        team_ids = {
            name: team_service.create_team(db, event_id, name)
            for name in (
                "Cardume",
                "Pedal Sul",
                "Vento Norte",
                "Independente",
                "Tri Clube Central",
                "All Sports",
            )
        }

        athletes = [
            ("Helena Duarte", 34, "Adulto 30-39", "Cardume", "F", 101),
            ("Renata Alves", 37, "Adulto 30-39", "Pedal Sul", "F", 102),
            ("Paula Nogueira", 31, "Adulto 30-39", "Vento Norte", "F", 103),
            ("Sofia Martins", 29, "Adulto 30-39", "Independente", "F", 104),
            ("Laura Pires", 35, "Adulto 30-39", "Cardume", "F", 105),
            ("Rafael Costa", 33, "Adulto 30-39", "Cardume", "M", 106),
            ("Diego Farias", 38, "Adulto 30-39", "Pedal Sul", "M", 107),
            ("Lucas Menezes", 30, "Adulto 30-39", "Vento Norte", "M", 108),
            ("Thiago Barros", 42, "Adulto 30-39", "Independente", "M", 109),
            ("Márcia Reis", 44, "Master 40-49", "Tri Clube Central", "F", 110),
            ("Célia Fontes", 47, "Master 40-49", "Independente", "F", 111),
            ("Paulo Tavares", 45, "Master 40-49", "Cardume", "M", 112),
            ("Sérgio Lopes", 49, "Master 40-49", "Pedal Sul", "M", 113),
            ("Vera Campos", 53, "Veterano 50-59", "Vento Norte", "F", 114),
            ("Lúcia Prado", 57, "Veterano 50-59", "Independente", "F", 115),
            ("Nelson Freire", 55, "Veterano 50-59", "Tri Clube Central", "M", 116),
            ("Otávio Braga", 58, "Veterano 50-59", "Cardume", "M", 117),
            ("Alice Ferraz", 26, "Elite 18-29", "Pedal Sul", "F", 118),
            ("Bruna Vidal", 24, "Elite 18-29", "Vento Norte", "F", 119),
            ("Gabriel Prado", 27, "Elite 18-29", "Cardume", "M", 120),
            ("Henrique Luz", 22, "Elite 18-29", "All Sports", "M", 121),
        ]
        for name, age, category, team, sex, bib in athletes:
            athlete_service.create_athlete(
                db,
                event_id=event_id,
                category_id=category_ids[category],
                name=name,
                age=age,
                team_id=team_ids[team],
                sex=sex,
                bib=bib,
            )

        event = event_service.get_event(db, event_id)
        heat_service.generate_heats(
            db,
            event,
            category_id=category_ids["Adulto 30-39"],
            sex_mode="F",
            criterion="bib",
        )
        heat_service.generate_heats(
            db,
            event,
            category_id=category_ids["Master 40-49"],
            sex_mode="F",
            criterion="alpha",
        )
        heat_service.generate_heats(
            db,
            event,
            category_id=category_ids["Elite 18-29"],
            sex_mode="X",
            criterion="bib",
        )

        second_id = event_service.create_event(
            db,
            name=SECOND_EVENT,
            event_date="2026-11-22",
            location="Parque Municipal · Campinas",
        )
        second_categories = {
            "Juventude 16-19": event_service.create_category(
                db,
                event_id=second_id,
                name="Juventude 16-19",
                min_age=16,
                max_age=19,
            ),
            "Adulto 20-39": event_service.create_category(
                db,
                event_id=second_id,
                name="Adulto 20-39",
                min_age=20,
                max_age=39,
            ),
        }
        second_team_ids = {
            name: team_service.create_team(db, second_id, name)
            for name in ("Escola Ativa", "Parque Run")
        }
        for name, age, category, team, sex, bib in [
            ("Isabela Reis", 18, "Juventude 16-19", "Escola Ativa", "F", 201),
            ("Murilo Dias", 19, "Juventude 16-19", "Escola Ativa", "M", 202),
            ("Patrícia Gomes", 32, "Adulto 20-39", "Parque Run", "F", 203),
            ("André Nunes", 29, "Adulto 20-39", "Parque Run", "M", 204),
        ]:
            athlete_service.create_athlete(
                db,
                event_id=second_id,
                category_id=second_categories[category],
                name=name,
                age=age,
                team_id=second_team_ids[team],
                sex=sex,
                bib=bib,
            )

    print(f"Banco de exemplo criado em: {db_path}")
    print(f"- {DEMO_EVENT}: 21 atletas, 4 categorias e 4 baterias montadas.")
    print(f"- {SECOND_EVENT}: 4 atletas, 2 categorias e nenhuma bateria.")
    print("Inicie a aplicação com: python run.py")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria dados de demonstração do Triscore.")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Caminho alternativo para o banco SQLite.",
    )
    args = parser.parse_args()
    seed(resolve_db_path(args.db))


if __name__ == "__main__":
    main()
