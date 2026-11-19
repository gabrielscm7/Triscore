from __future__ import annotations

import re
import sqlite3
from typing import Any

from app.services import classification as classification_service
from app.utils import clean_text

PRESETS = {
    "classic": {
        "label": "Clássico",
        "accent": "#f5a524",
        "background": "#0d2f3f",
        "text": "#f7fbfa",
    },
    "light": {
        "label": "Claro",
        "accent": "#0c6b64",
        "background": "#f4f2ec",
        "text": "#17323a",
    },
    "dark": {
        "label": "Escuro",
        "accent": "#48d6c8",
        "background": "#04141b",
        "text": "#f4fbf9",
    },
    "custom": {
        "label": "Personalizado",
        "accent": "#f5a524",
        "background": "#0d2f3f",
        "text": "#f7fbfa",
    },
}
DEFAULT_PRESET = "classic"
LAYOUTS = {
    "classic": "Clássico centralizado",
    "modern": "Moderno com faixa lateral",
    "highlight": "Destaque com número grande",
}
DEFAULT_LAYOUT = "classic"
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    return (
        int(value[1:3], 16),
        int(value[3:5], 16),
        int(value[5:7], 16),
    )


def _linear_channel(value: int) -> float:
    channel = value / 255
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _luminance(value: str) -> float:
    red, green, blue = _hex_to_rgb(value)
    return (
        0.2126 * _linear_channel(red)
        + 0.7152 * _linear_channel(green)
        + 0.0722 * _linear_channel(blue)
    )


def contrast_ratio(first: str, second: str) -> float:
    light, dark = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _rgba(value: str, alpha: float) -> str:
    red, green, blue = _hex_to_rgb(value)
    return f"rgba({red}, {green}, {blue}, {alpha})"


def validate_color(value: str | None, label: str) -> str:
    color = clean_text(value)
    if not HEX_COLOR.match(color):
        raise ValueError(f"{label} deve estar no formato hexadecimal #RRGGBB.")
    return color.upper()


def _validate_preset(value: str | None) -> str:
    preset = clean_text(value) or DEFAULT_PRESET
    if preset not in PRESETS:
        raise ValueError("Tema de premiação inválido.")
    return preset


def validate_layout(value: str | None) -> str:
    layout = clean_text(value) or DEFAULT_LAYOUT
    if layout not in LAYOUTS:
        raise ValueError("Layout de premiação inválido.")
    return layout


def _percentage(value: int | str | None, default: int, label: str) -> int:
    try:
        number = int(str(value)) if value is not None and str(value) != "" else default
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} deve ser um número entre 0 e 100.") from error
    if not 0 <= number <= 100:
        raise ValueError(f"{label} deve ser um número entre 0 e 100.")
    return number


def _settings_row(
    connection: sqlite3.Connection, event_id: int
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM award_settings WHERE event_id = ?", (event_id,)
    ).fetchone()


def get_settings(
    connection: sqlite3.Connection, event_id: int
) -> dict[str, Any]:
    row = _settings_row(connection, event_id)
    if row is None:
        return {
            "preset": DEFAULT_PRESET,
            "accent_color": None,
            "background_color": None,
            "text_color": None,
            "show_logo": True,
            "animations_enabled": True,
            "layout": DEFAULT_LAYOUT,
            "banner_filename": None,
            "background_filename": None,
            "background_opacity": 35,
            "background_dim": 55,
            "font_filename": None,
            "font_format": None,
            "opening_title": "Premiação",
            "opening_text": "",
            "closing_title": "Obrigado!",
            "closing_text": "",
        }
    settings = dict(row)
    settings["show_logo"] = bool(settings["show_logo"])
    settings["animations_enabled"] = bool(settings["animations_enabled"])
    settings["layout"] = settings.get("layout") or DEFAULT_LAYOUT
    return settings


def resolve_theme(settings: dict[str, Any]) -> dict[str, Any]:
    preset = _validate_preset(settings.get("preset"))
    fallback = PRESETS[preset]
    if preset == "custom":
        accent = settings.get("accent_color") or fallback["accent"]
        background = settings.get("background_color") or fallback["background"]
        text = settings.get("text_color") or fallback["text"]
    else:
        accent = fallback["accent"]
        background = fallback["background"]
        text = fallback["text"]
    is_dark = _luminance(background) < 0.45
    layout = validate_layout(settings.get("layout"))
    return {
        "preset": preset,
        "preset_label": PRESETS[preset]["label"],
        "layout": layout,
        "layout_label": LAYOUTS.get(layout, LAYOUTS[DEFAULT_LAYOUT]),
        "accent_color": accent,
        "background_color": background,
        "text_color": text,
        "is_dark": is_dark,
        "background_opacity": int(settings.get("background_opacity", 35)),
        "background_dim": int(settings.get("background_dim", 55)),
        "background_opacity_ratio": f"{int(settings.get('background_opacity', 35)) / 100:.2f}",
        "background_dim_ratio": f"{int(settings.get('background_dim', 55)) / 100:.2f}",
        "banner_filename": settings.get("banner_filename"),
        "background_filename": settings.get("background_filename"),
        "font_filename": settings.get("font_filename"),
        "font_format": settings.get("font_format"),
        "panel_color": (
            "rgba(255, 255, 255, 0.10)"
            if is_dark
            else "rgba(255, 255, 255, 0.74)"
        ),
        "panel_strong_color": (
            "rgba(255, 255, 255, 0.16)"
            if is_dark
            else "rgba(255, 255, 255, 0.92)"
        ),
        "border_color": (
            "rgba(255, 255, 255, 0.22)"
            if is_dark
            else "rgba(23, 50, 58, 0.14)"
        ),
        "muted_color": _rgba(text, 0.70),
        "accent_soft_color": _rgba(accent, 0.20),
        "show_logo": bool(settings.get("show_logo", True)),
        "animations_enabled": bool(settings.get("animations_enabled", True)),
    }


def update_settings(
    connection: sqlite3.Connection,
    event_id: int,
    *,
    preset: str,
    accent_color: str | None,
    background_color: str | None,
    text_color: str | None,
    show_logo: bool,
    animations_enabled: bool,
    layout: str = "classic",
    background_opacity: int | str | None = 35,
    background_dim: int | str | None = 55,
    opening_title: str = "Premiação",
    opening_text: str = "",
    closing_title: str = "Obrigado!",
    closing_text: str = "",
) -> dict[str, Any]:
    preset = _validate_preset(preset)
    if preset == "custom":
        accent = validate_color(accent_color, "A cor de destaque")
        background = validate_color(background_color, "A cor de fundo")
        text = validate_color(text_color, "A cor do texto")
        if contrast_ratio(text, background) < 4.5:
            raise ValueError(
                "O contraste entre texto e fundo deve ser de pelo menos 4.5:1."
            )
        if contrast_ratio(accent, background) < 3:
            raise ValueError(
                "O contraste entre destaque e fundo deve ser de pelo menos 3:1."
            )
    else:
        accent = background = text = None

    layout = validate_layout(layout)
    opacity = _percentage(
        background_opacity, 35, "A opacidade da imagem de fundo"
    )
    dim = _percentage(background_dim, 55, "O escurecimento da imagem de fundo")
    if dim < 30:
        raise ValueError(
            "O escurecimento da imagem de fundo deve ser de pelo menos 30%."
        )
    opening_title = clean_text(opening_title, 120) or "Premiação"
    opening_text = clean_text(opening_text, 300)
    closing_title = clean_text(closing_title, 120) or "Obrigado!"
    closing_text = clean_text(closing_text, 300)

    connection.execute(
        """
        INSERT INTO award_settings
            (event_id, preset, accent_color, background_color, text_color,
             show_logo, animations_enabled, layout, background_opacity,
             background_dim, opening_title, opening_text, closing_title,
             closing_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_id) DO UPDATE SET
            preset = excluded.preset,
            accent_color = excluded.accent_color,
            background_color = excluded.background_color,
            text_color = excluded.text_color,
            show_logo = excluded.show_logo,
            animations_enabled = excluded.animations_enabled,
            layout = excluded.layout,
            background_opacity = excluded.background_opacity,
            background_dim = excluded.background_dim,
            opening_title = excluded.opening_title,
            opening_text = excluded.opening_text,
            closing_title = excluded.closing_title,
            closing_text = excluded.closing_text,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        """,
        (
            event_id,
            preset,
            accent,
            background,
            text,
            1 if show_logo else 0,
            1 if animations_enabled else 0,
            layout,
            opacity,
            dim,
            opening_title,
            opening_text,
            closing_title,
            closing_text,
        ),
    )
    return get_settings(connection, event_id)


def update_assets(
    connection: sqlite3.Connection,
    event_id: int,
    *,
    banner_filename: str | None,
    background_filename: str | None,
    font_filename: str | None,
    font_format: str | None,
) -> dict[str, Any]:
    connection.execute(
        "INSERT INTO award_settings (event_id) VALUES (?) ON CONFLICT(event_id) DO NOTHING",
        (event_id,),
    )
    connection.execute(
        """
        UPDATE award_settings
        SET banner_filename = ?,
            background_filename = ?,
            font_filename = ?,
            font_format = ?,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE event_id = ?
        """,
        (
            banner_filename,
            background_filename,
            font_filename,
            font_format,
            event_id,
        ),
    )
    return get_settings(connection, event_id)


def _slide_text_map(
    connection: sqlite3.Connection, event_id: int
) -> dict[tuple[int, str], dict[str, Any]]:
    rows = connection.execute(
        "SELECT category_id, group_sex, title, call_text "
        "FROM award_slide_texts WHERE event_id = ?",
        (event_id,),
    ).fetchall()
    return {
        (row["category_id"], row["group_sex"]): dict(row) for row in rows
    }


def get_slide_text(
    connection: sqlite3.Connection,
    event_id: int,
    category_id: int,
    group_sex: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT * FROM award_slide_texts
        WHERE event_id = ? AND category_id = ? AND group_sex = ?
        """,
        (event_id, category_id, group_sex),
    ).fetchone()
    return dict(row) if row is not None else None


def update_slide_text(
    connection: sqlite3.Connection,
    event_id: int,
    category_id: int,
    group_sex: str,
    *,
    title: str,
    call_text: str,
) -> None:
    sex = clean_text(group_sex).upper()
    if sex not in ("M", "F", "X"):
        raise ValueError("Grupo de slide inválido.")
    category = connection.execute(
        "SELECT id FROM categories WHERE id = ? AND event_id = ?",
        (category_id, event_id),
    ).fetchone()
    if category is None:
        raise ValueError("Categoria não encontrada nesta prova.")
    title = clean_text(title, 140)
    call_text = clean_text(call_text, 260)
    if not title and not call_text:
        connection.execute(
            """
            DELETE FROM award_slide_texts
            WHERE event_id = ? AND category_id = ? AND group_sex = ?
            """,
            (event_id, category_id, sex),
        )
        return
    connection.execute(
        """
        INSERT INTO award_slide_texts
            (event_id, category_id, group_sex, title, call_text)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(event_id, category_id, group_sex) DO UPDATE SET
            title = excluded.title,
            call_text = excluded.call_text
        """,
        (event_id, category_id, sex, title, call_text),
    )


def build_awards(
    connection: sqlite3.Connection, event_id: int
) -> dict[str, Any]:
    groups = classification_service.build_classification(connection, event_id)
    slide_texts = _slide_text_map(connection, event_id)
    award_groups = []
    skipped_groups = 0
    for group in groups:
        podium: dict[int, list[dict[str, Any]]] = {1: [], 2: [], 3: []}
        for athlete in group["athletes"]:
            position = athlete["position"]
            if position in podium:
                podium[position].append(athlete)
        if not any(podium.values()):
            skipped_groups += 1
            continue
        override = slide_texts.get((group["category_id"], group["sex"]), {})
        award_groups.append(
            {
                "category_id": group["category_id"],
                "category_name": group["category_name"],
                "custom_title": override.get("title") or "",
                "custom_call_text": override.get("call_text") or "",
                "display_title": override.get("title") or group["category_name"],
                "call_text": override.get("call_text") or "",
                "sex": group["sex"],
                "sex_label": group["sex_label"],
                "classification_mode": group["classification_mode"],
                "podium": podium,
            }
        )
    return {
        "groups": award_groups,
        "stats": {
            "groups": len(groups),
            "podium_groups": len(award_groups),
            "skipped_groups": skipped_groups,
            "athletes": sum(
                len(athletes)
                for group in award_groups
                for athletes in group["podium"].values()
            ),
        },
    }
