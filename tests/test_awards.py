from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader

from app.database import transaction
from app.main import create_app
from app.services import awards as award_service
from app.services import classification as classification_service
from app.services import results as result_service
from tests.conftest import create_athlete, create_category, create_event


def _build_podium_event(client, db, app):
    event_id = create_event(client, "Premiação Teste")
    create_category(
        client,
        event_id,
        "Open",
        18,
        59,
        classification_mode="mixed",
    )
    create_category(client, event_id, "Sem Resultado", 30, 39)
    categories = {
        row["name"]: row["id"]
        for row in db.execute(
            "SELECT id, name FROM categories WHERE event_id = ?", (event_id,)
        ).fetchall()
    }
    for name, bib, sex, category in (
        ("Bruno", 10, "M", "Open"),
        ("Ana", 11, "F", "Open"),
        ("Carla", 12, "F", "Open"),
        ("Diego", 13, "M", "Open"),
        ("Eva", 14, "F", "Open"),
        ("Fernanda", 20, "F", "Sem Resultado"),
    ):
        create_athlete(
            client,
            event_id,
            name=name,
            age=34,
            category_id=categories[category],
            sex=sex,
            bib=bib,
            team="",
        )
    athletes = {
        row["name"]: row["id"]
        for row in db.execute(
            "SELECT id, name FROM athletes WHERE event_id = ?", (event_id,)
        ).fetchall()
    }
    with transaction(app.state.db_path) as connection:
        for name, status, final_time in (
            ("Bruno", "OK", 120000),
            ("Ana", "OK", 126000),
            ("Carla", "OK", 126000),
            ("Diego", "DNF", None),
        ):
            result_service.save_result(
                connection,
                event_id=event_id,
                athlete_id=athletes[name],
                status=status,
                final_time_cs=final_time,
            )
        classification_service.update_tiebreak(connection, event_id, "real")
    return event_id, athletes


def test_awards_build_mixed_podium_with_real_ties_and_skip_empty_group(
    client, db, app
):
    event_id, _ = _build_podium_event(client, db, app)
    data = award_service.build_awards(db, event_id)
    assert data["stats"] == {
        "groups": 2,
        "podium_groups": 1,
        "skipped_groups": 1,
        "athletes": 3,
    }
    assert len(data["groups"]) == 1
    group = data["groups"][0]
    assert group["category_name"] == "Open"
    assert group["sex_label"] == "Misto"
    assert [athlete["name"] for athlete in group["podium"][1]] == ["Bruno"]
    assert [athlete["name"] for athlete in group["podium"][2]] == ["Ana", "Carla"]
    assert group["podium"][3] == []
    all_podium_names = {
        athlete["name"]
        for athletes in group["podium"].values()
        for athlete in athletes
    }
    assert all_podium_names == {"Bruno", "Ana", "Carla"}

    page = client.get(f"/premiacao/{event_id}")
    assert page.status_code == 200
    assert "Premiação Teste" in page.text
    assert "Open" in page.text and "Misto" in page.text
    assert "Revelar 3º lugar" in page.text
    assert "Configurar tema" in page.text
    assert 'data-group-index="0"' in page.text
    assert "Posição não ocupada" in page.text
    assert "Diego" not in page.text and "Eva" not in page.text


def test_awards_selector_theme_persistence_and_validation(client, db, app):
    event_id, _ = _build_podium_event(client, db, app)
    selector = client.get("/premiacao")
    assert selector.status_code == 200
    assert f"/premiacao/{event_id}" in selector.text
    assert "Premiação Teste" in selector.text

    default = client.get(f"/premiacao/{event_id}")
    assert default.status_code == 200
    assert "--award-bg: #0d2f3f" in default.text
    assert "--award-accent: #f5a524" in default.text
    assert re.search(r'value="classic".*?selected', default.text, re.S)

    saved = client.post(
        f"/premiacao/{event_id}/tema",
        data={
            "preset": "light",
            "show_logo": "1",
            "animations_enabled": "1",
        },
        follow_redirects=True,
    )
    assert "Tema da premiação atualizado" in saved.text
    assert "--award-bg: #f4f2ec" in saved.text
    row = db.execute(
        "SELECT preset, show_logo, animations_enabled FROM award_settings WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    assert tuple(row) == ("light", 1, 1)

    custom = client.post(
        f"/premiacao/{event_id}/tema",
        data={
            "preset": "custom",
            "accent_color": "#0c6b64",
            "background_color": "#ffffff",
            "text_color": "#111111",
            "show_logo": "1",
        },
        follow_redirects=True,
    )
    assert "Tema da premiação atualizado" in custom.text
    assert "--award-bg: #FFFFFF" in custom.text
    assert "--award-accent: #0C6B64" in custom.text
    row = db.execute(
        "SELECT preset, accent_color, background_color, text_color FROM award_settings WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    assert tuple(row) == ("custom", "#0C6B64", "#FFFFFF", "#111111")

    invalid = client.post(
        f"/premiacao/{event_id}/tema",
        data={
            "preset": "custom",
            "accent_color": "red",
            "background_color": "#ffffff",
            "text_color": "#111111",
        },
        follow_redirects=True,
    )
    assert "formato hexadecimal" in invalid.text
    assert db.execute(
        "SELECT accent_color FROM award_settings WHERE event_id = ?", (event_id,)
    ).fetchone()[0] == "#0C6B64"

    low_contrast = client.post(
        f"/premiacao/{event_id}/tema",
        data={
            "preset": "custom",
            "accent_color": "#0c6b64",
            "background_color": "#ffffff",
            "text_color": "#aaaaaa",
        },
        follow_redirects=True,
    )
    assert "pelo menos 4.5:1" in low_contrast.text
    assert db.execute(
        "SELECT text_color FROM award_settings WHERE event_id = ?", (event_id,)
    ).fetchone()[0] == "#111111"

    low_accent = client.post(
        f"/premiacao/{event_id}/tema",
        data={
            "preset": "custom",
            "accent_color": "#eeeeee",
            "background_color": "#ffffff",
            "text_color": "#111111",
        },
        follow_redirects=True,
    )
    assert "pelo menos 3:1" in low_accent.text

    no_animation = client.post(
        f"/premiacao/{event_id}/tema",
        data={"preset": "dark"},
        follow_redirects=True,
    )
    assert "Tema da premiação atualizado" in no_animation.text
    assert "no-animations" in no_animation.text
    row = db.execute(
        "SELECT show_logo, animations_enabled FROM award_settings WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    assert tuple(row) == (0, 0)

    invalid_preset = client.post(
        f"/premiacao/{event_id}/tema",
        data={"preset": "neon"},
        follow_redirects=True,
    )
    assert "Tema de premiação inválido" in invalid_preset.text


def test_awards_pdf_and_export_buttons(client, db, app):
    event_id, _ = _build_podium_event(client, db, app)
    classification = client.get(f"/eventos/{event_id}/classificacao")
    assert f"/premiacao/{event_id}" in classification.text

    response = client.get(f"/premiacao/{event_id}/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert "premiacao_teste_premiacao_" in response.headers["content-disposition"]

    files = sorted(client.app.state.exports_dir.glob("premiacao_teste_premiacao_*.pdf"))
    assert len(files) == 1
    reader = PdfReader(str(files[0]))
    assert len(reader.pages) >= 2
    assert len(reader.pages[0].images) >= 1
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    for name in ("Bruno", "Ana", "Carla"):
        assert name in text
    assert "Open · Misto" in text
    assert "1º" in text and "2º" in text
    assert "Diego" not in text and "Fernanda" not in text


def test_award_settings_defaults_and_theme_resolution(db):
    settings = award_service.get_settings(db, 999)
    assert settings["preset"] == "classic"
    assert settings["show_logo"] is True
    assert settings["animations_enabled"] is True
    theme = award_service.resolve_theme(settings)
    assert theme["is_dark"] is True
    assert theme["accent_color"] == "#f5a524"
    assert theme["background_color"] == "#0d2f3f"


def _png_bytes(color=(245, 165, 36), size=(320, 120)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_awards_asset_uploads_replacement_removal_and_persistence(client, db, app):
    event_id, _ = _build_podium_event(client, db, app)
    font_bytes = (
        Path(__file__).resolve().parent.parent
        / "app"
        / "static"
        / "fonts"
        / "FiraSans-Regular.ttf"
    ).read_bytes()
    response = client.post(
        f"/premiacao/{event_id}/tema/assets",
        files={
            "banner": ("banner.png", _png_bytes(), "image/png"),
            "background": ("background.png", _png_bytes((20, 80, 90)), "image/png"),
            "custom_font": ("custom.ttf", font_bytes, "font/ttf"),
        },
        follow_redirects=True,
    )
    assert "Arquivos da premiação atualizados" in response.text
    settings = award_service.get_settings(db, event_id)
    assert settings["banner_filename"]
    assert settings["background_filename"]
    assert settings["font_filename"]
    assert settings["font_format"] == "truetype"
    media_dir = app.state.awards_media_dir / str(event_id)
    for kind in ("banner", "background", "font"):
        assert (media_dir / settings[f"{kind}_filename"]).exists()

    banner = client.get(f"/premiacao/{event_id}/asset/banner")
    assert banner.status_code == 200 and banner.headers["content-type"] == "image/png"
    background = client.get(f"/premiacao/{event_id}/asset/background")
    assert background.status_code == 200
    assert background.headers["content-type"] == "image/png"
    font = client.get(f"/premiacao/{event_id}/asset/font")
    assert font.status_code == 200 and font.headers["content-type"] == "font/ttf"

    page = client.get(f"/premiacao/{event_id}")
    assert f"/premiacao/{event_id}/asset/banner" in page.text
    assert f"/premiacao/{event_id}/asset/background" in page.text
    assert f"/premiacao/{event_id}/asset/font" in page.text
    assert "AwardCustom" in page.text
    assert "data-layout-preview" in page.text

    pdf_response = client.get(f"/premiacao/{event_id}/pdf")
    assert pdf_response.status_code == 200
    pdf_path = next(
        client.app.state.exports_dir.glob("premiacao_teste_premiacao_*.pdf")
    )
    pdf_reader = PdfReader(str(pdf_path))
    assert len(pdf_reader.pages[0].images) >= 3

    old_banner = settings["banner_filename"]
    replaced = client.post(
        f"/premiacao/{event_id}/tema/assets",
        files={"banner": ("novo.png", _png_bytes((10, 40, 60)), "image/png")},
        follow_redirects=True,
    )
    assert "Arquivos da premiação atualizados" in replaced.text
    new_settings = award_service.get_settings(db, event_id)
    assert new_settings["banner_filename"] != old_banner
    assert not (media_dir / old_banner).exists()
    assert (media_dir / new_settings["banner_filename"]).exists()

    invalid = client.post(
        f"/premiacao/{event_id}/tema/assets",
        files={"banner": ("falso.png", b"isto nao e imagem", "image/png")},
        follow_redirects=True,
    )
    assert "não é uma imagem válida" in invalid.text
    assert award_service.get_settings(db, event_id)["banner_filename"] == new_settings[
        "banner_filename"
    ]
    invalid_font = client.post(
        f"/premiacao/{event_id}/tema/assets",
        files={"custom_font": ("falsa.ttf", b"nao e fonte", "font/ttf")},
        follow_redirects=True,
    )
    assert "não é uma fonte TTF válida" in invalid_font.text

    old_background = award_service.get_settings(db, event_id)["background_filename"]
    removed = client.post(
        f"/premiacao/{event_id}/tema/assets",
        data={"remove_background": "1"},
        follow_redirects=True,
    )
    assert "Arquivos da premiação atualizados" in removed.text
    assert award_service.get_settings(db, event_id)["background_filename"] is None
    assert not (media_dir / old_background).exists()

    persisted_app = create_app(app.state.db_path)
    persisted_app.state.exports_dir = app.state.exports_dir
    with TestClient(persisted_app) as persisted_client:
        persisted_page = persisted_client.get(f"/premiacao/{event_id}")
        assert persisted_page.status_code == 200
        assert "/asset/banner" in persisted_page.text
        assert "/asset/font" in persisted_page.text


def test_awards_layout_slide_texts_and_pdf_reflect_visual_settings(client, db, app):
    event_id, _ = _build_podium_event(client, db, app)
    category_id = db.execute(
        "SELECT id FROM categories WHERE event_id = ? AND name = 'Open'", (event_id,)
    ).fetchone()["id"]
    theme = client.post(
        f"/premiacao/{event_id}/tema",
        data={
            "preset": "light",
            "layout": "modern",
            "background_opacity": "60",
            "background_dim": "70",
            "opening_title": "Boas-vindas",
            "opening_text": "Vamos começar a premiação.",
            "closing_title": "Até a próxima",
            "closing_text": "Obrigado a todos.",
            "show_logo": "1",
            "animations_enabled": "1",
        },
        follow_redirects=True,
    )
    assert "Tema da premiação atualizado" in theme.text
    settings = award_service.get_settings(db, event_id)
    assert settings["layout"] == "modern"
    assert settings["background_opacity"] == 60
    assert settings["background_dim"] == 70
    assert settings["opening_title"] == "Boas-vindas"
    assert settings["closing_title"] == "Até a próxima"

    text = client.post(
        f"/premiacao/{event_id}/slides/{category_id}/X",
        data={
            "title": "Open Especial",
            "call_text": "Vamos aplaudir os campeões!",
        },
        follow_redirects=True,
    )
    assert "Texto do slide atualizado" in text.text
    page = client.get(f"/premiacao/{event_id}")
    assert 'data-layout="modern"' in page.text
    assert "Open Especial" in page.text
    assert "Vamos aplaudir os campeões!" in page.text
    assert "Boas-vindas" in page.text
    assert "Até a próxima" in page.text
    assert "--award-bg-opacity: 0.60" in page.text
    assert "--award-bg-dim: 0.70" in page.text

    stored_text = db.execute(
        """
        SELECT title, call_text FROM award_slide_texts
        WHERE event_id = ? AND category_id = ? AND group_sex = 'X'
        """,
        (event_id, category_id),
    ).fetchone()
    assert tuple(stored_text) == ("Open Especial", "Vamos aplaudir os campeões!")

    invalid_layout = client.post(
        f"/premiacao/{event_id}/tema",
        data={"preset": "light", "layout": "invalido", "background_dim": "55"},
        follow_redirects=True,
    )
    assert "Layout de premiação inválido" in invalid_layout.text
    invalid_dim = client.post(
        f"/premiacao/{event_id}/tema",
        data={"preset": "light", "layout": "modern", "background_dim": "10"},
        follow_redirects=True,
    )
    assert "pelo menos 30%" in invalid_dim.text

    pdf_response = client.get(f"/premiacao/{event_id}/pdf")
    assert pdf_response.status_code == 200
    pdf_path = next(
        client.app.state.exports_dir.glob("premiacao_teste_premiacao_*.pdf")
    )
    reader = PdfReader(str(pdf_path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Boas-vindas" in text
    assert "Open Especial" in text
    assert "Vamos aplaudir os campeões!" in text
    assert "Até a próxima" in text
    assert "Obrigado a todos." in text

    cleared = client.post(
        f"/premiacao/{event_id}/slides/{category_id}/X",
        data={"title": "", "call_text": ""},
        follow_redirects=True,
    )
    assert "Texto do slide atualizado" in cleared.text
    assert db.execute(
        "SELECT COUNT(*) FROM award_slide_texts WHERE event_id = ?", (event_id,)
    ).fetchone()[0] == 0
