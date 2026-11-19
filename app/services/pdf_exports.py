from __future__ import annotations

import os
import re
import sqlite3
import unicodedata
from datetime import date, datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image as PILImage
from PIL import ImageOps
from reportlab.lib import colors
from reportlab.lib import fonts as rl_fonts
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.paths import DEFAULT_EXPORTS_DIR, FONT_DIR, LOGO_PATH
from app.services import award_assets
from app.services import awards as award_service
from app.services import classification as classification_service
from app.services import heats as heat_service
from app.utils import display_date, mode_label

EXPORTS_DIR = DEFAULT_EXPORTS_DIR

FONT_REGULAR = "FiraSans"
FONT_MEDIUM = "FiraSansMedium"
FONT_SEMIBOLD = "FiraSansSemiBold"
FONT_BOLD = "FiraSansBold"

TEAL = colors.HexColor("#0c6b64")
TEAL_DARK = colors.HexColor("#0d2f3f")
INK = colors.HexColor("#213330")
MUTED = colors.HexColor("#61706c")
LINE = colors.HexColor("#d8e0dd")
SURFACE = colors.HexColor("#f2f6f4")
WHITE = colors.white

_FONTS_REGISTERED = False


def _register_fonts() -> None:
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(FONT_DIR / "FiraSans-Regular.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_MEDIUM, str(FONT_DIR / "FiraSans-Medium.ttf")))
    pdfmetrics.registerFont(
        TTFont(FONT_SEMIBOLD, str(FONT_DIR / "FiraSans-SemiBold.ttf"))
    )
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(FONT_DIR / "FiraSans-Bold.ttf")))
    for family in (FONT_REGULAR, FONT_MEDIUM, FONT_SEMIBOLD, FONT_BOLD):
        pdfmetrics.registerFontFamily(
            family,
            normal=family,
            bold=FONT_BOLD,
            italic=family,
            boldItalic=FONT_BOLD,
        )
        for bold in (0, 1):
            for italic in (0, 1):
                rl_fonts.addMapping(family, bold, italic, family)
    _FONTS_REGISTERED = True


def _styles() -> dict[str, ParagraphStyle]:
    _register_fonts()
    return {
        "title": ParagraphStyle(
            "title",
            fontName=FONT_BOLD,
            fontSize=20,
            leading=24,
            textColor=TEAL_DARK,
            spaceAfter=4 * mm,
        ),
        "cover_title": ParagraphStyle(
            "cover_title",
            fontName=FONT_BOLD,
            fontSize=25,
            leading=30,
            alignment=TA_CENTER,
            textColor=TEAL_DARK,
            spaceAfter=4 * mm,
        ),
        "cover_subtitle": ParagraphStyle(
            "cover_subtitle",
            fontName=FONT_MEDIUM,
            fontSize=14,
            leading=18,
            alignment=TA_CENTER,
            textColor=TEAL,
            spaceAfter=2 * mm,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta",
            fontName=FONT_REGULAR,
            fontSize=10,
            leading=15,
            alignment=TA_CENTER,
            textColor=MUTED,
        ),
        "heading": ParagraphStyle(
            "heading",
            fontName=FONT_SEMIBOLD,
            fontSize=13,
            leading=16,
            textColor=TEAL_DARK,
            spaceBefore=2 * mm,
            spaceAfter=2 * mm,
            keepWithNext=True,
        ),
        "subheading": ParagraphStyle(
            "subheading",
            fontName=FONT_SEMIBOLD,
            fontSize=10.5,
            leading=14,
            textColor=TEAL_DARK,
            spaceBefore=1.5 * mm,
            spaceAfter=1.5 * mm,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "body",
            fontName=FONT_REGULAR,
            fontSize=9,
            leading=13,
            textColor=INK,
        ),
        "small": ParagraphStyle(
            "small",
            fontName=FONT_REGULAR,
            fontSize=8,
            leading=11,
            textColor=MUTED,
        ),
        "cell": ParagraphStyle(
            "cell",
            fontName=FONT_REGULAR,
            fontSize=8,
            leading=10,
            textColor=INK,
        ),
        "cell_bold": ParagraphStyle(
            "cell_bold",
            fontName=FONT_MEDIUM,
            fontSize=8.5,
            leading=11,
            textColor=TEAL_DARK,
        ),
    }


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").casefold()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")
    return slug or "prova"


def output_path(
    event: dict[str, Any], kind: str, exports_dir: str | Path | None = None
) -> Path:
    target_dir = Path(exports_dir) if exports_dir is not None else EXPORTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / f"{_slug(event['name'])}_{kind}_{date.today().isoformat()}.pdf"


def _page_decorator(event_name: str, report_title: str, *, skip_cover: bool = False):
    def draw(canvas, doc):
        if skip_cover and doc.page == 1:
            return
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.6)
        canvas.line(15 * mm, A4[1] - 13 * mm, A4[0] - 15 * mm, A4[1] - 13 * mm)
        canvas.setFont(FONT_MEDIUM, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(15 * mm, A4[1] - 10.5 * mm, event_name)
        canvas.drawRightString(
            A4[0] - 15 * mm, A4[1] - 10.5 * mm, report_title
        )
        canvas.setFont(FONT_REGULAR, 7.5)
        canvas.drawCentredString(
            A4[0] / 2, 9 * mm, f"Triscore · página {doc.page}"
        )
        canvas.restoreState()

    return draw


def _table(
    data: list[list[Any]],
    widths: list[float],
    *,
    align: list[str] | None = None,
    header_background: colors.Color = SURFACE,
    header_text: colors.Color = TEAL_DARK,
) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), header_background),
        ("TEXTCOLOR", (0, 0), (-1, 0), header_text),
        ("FONTNAME", (0, 0), (-1, 0), FONT_SEMIBOLD),
        ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.45, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#fbfcfc")]),
    ]
    if align:
        for index, value in enumerate(align):
            commands.append(("ALIGN", (index, 0), (index, -1), value))
    table.setStyle(TableStyle(commands))
    return table


def _build_pdf(
    event: dict[str, Any],
    *,
    kind: str,
    title: str,
    story: list[Any],
    exports_dir: str | Path | None,
    skip_cover_header: bool = False,
) -> Path:
    _register_fonts()
    final_path = output_path(event, kind, exports_dir)
    temp_path = final_path.with_suffix(".tmp.pdf")
    document = SimpleDocTemplate(
        str(temp_path),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=20 * mm,
        bottomMargin=16 * mm,
        title=title,
        author="Triscore",
        subject=f"{title} · {event['name']}",
    )
    decorator = _page_decorator(event["name"], title, skip_cover=skip_cover_header)
    try:
        document.build(story, onFirstPage=decorator, onLaterPages=decorator)
        os.replace(temp_path, final_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return final_path


def cronograma_table_data(
    connection: sqlite3.Connection, event: dict[str, Any]
) -> list[list[str]]:
    builder = heat_service.load_builder(connection, event)
    rows: list[list[str]] = [
        [
            "Ordem",
            "Bateria",
            "Categoria",
            "Grupo",
            "Atletas",
            "Início previsto",
            "Última largada",
        ]
    ]
    for heat in builder["heats"]:
        entries = heat["entries"]
        last_start = entries[-1].get("scheduled_time") if entries else None
        rows.append(
            [
                str(heat["sequence"]),
                heat["label"],
                heat["category_name"],
                mode_label(heat["sex_mode"]),
                str(len(entries)),
                heat.get("scheduled_start") or "—",
                last_start or "—",
            ]
        )
    return rows


def export_cronograma(
    connection: sqlite3.Connection,
    event: dict[str, Any],
    exports_dir: str | Path | None = None,
) -> Path:
    styles = _styles()
    rows = cronograma_table_data(connection, event)
    story = [
        Paragraph("Cronograma da prova", styles["title"]),
        Paragraph(escape(event["name"]), styles["body"]),
        Spacer(1, 2 * mm),
    ]
    if not event["schedule_enabled"]:
        story.append(
            Paragraph(
                "O cronograma está desativado na configuração desta prova. "
                "Os horários previstos não são exibidos.",
                styles["small"],
            )
        )
        story.append(Spacer(1, 3 * mm))
    story.append(
        _table(
            rows,
            [12 * mm, 16 * mm, 47 * mm, 23 * mm, 16 * mm, 25 * mm, 25 * mm],
            align=["CENTER", "CENTER", "LEFT", "LEFT", "CENTER", "CENTER", "CENTER"],
        )
    )
    if len(rows) == 1:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("Nenhuma bateria cadastrada.", styles["small"]))
    return _build_pdf(
        event,
        kind="cronograma",
        title="Cronograma da prova",
        story=story,
        exports_dir=exports_dir,
    )


def start_list_sections(
    connection: sqlite3.Connection, event: dict[str, Any]
) -> list[dict[str, Any]]:
    builder = heat_service.load_builder(connection, event)
    sections = []
    for heat in builder["heats"]:
        sections.append(
            {
                "heat": heat,
                "heading": (
                    f"Bateria {heat['label']} · {heat['category_name']} · "
                    f"{mode_label(heat['sex_mode'])}"
                ),
                "scheduled_start": heat.get("scheduled_start"),
                "entries": heat["entries"],
            }
        )
    return sections


def export_start_list(
    connection: sqlite3.Connection,
    event: dict[str, Any],
    exports_dir: str | Path | None = None,
) -> Path:
    styles = _styles()
    sections = start_list_sections(connection, event)
    story: list[Any] = [
        Paragraph("Lista de largada / súmula em branco", styles["title"]),
        Paragraph(escape(event["name"]), styles["body"]),
        Spacer(1, 2 * mm),
        Paragraph(
            "Preencha o tempo de cada atleta no campo em branco. "
            "A lista segue a ordem de largada das baterias.",
            styles["small"],
        ),
        Spacer(1, 4 * mm),
    ]
    if not sections:
        story.append(Paragraph("Nenhuma bateria cadastrada.", styles["small"]))
    for index, section in enumerate(sections):
        heading = section["heading"]
        if section["scheduled_start"]:
            heading += f" · início {section['scheduled_start']}"
        story.append(Paragraph(escape(heading), styles["heading"]))
        if section["entries"]:
            data: list[list[str]] = [["Pos.", "Peito", "Nome", "Equipe", "Tempo"]]
            for entry in section["entries"]:
                data.append(
                    [
                        str(entry["position"]),
                        str(entry["bib"]),
                        entry["name"],
                        entry.get("team") or "Sem equipe",
                        "",
                    ]
                )
            story.append(
                _table(
                    data,
                    [13 * mm, 16 * mm, 67 * mm, 47 * mm, 32 * mm],
                    align=["CENTER", "CENTER", "LEFT", "LEFT", "CENTER"],
                )
            )
        else:
            story.append(Paragraph("Bateria sem atletas.", styles["small"]))
        if index < len(sections) - 1:
            story.append(PageBreak())
    return _build_pdf(
        event,
        kind="lista_largada",
        title="Lista de largada — súmula em branco",
        story=story,
        exports_dir=exports_dir,
    )


def final_report_groups(
    connection: sqlite3.Connection, event: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    groups = classification_service.build_classification(connection, event["id"])
    return groups, classification_service.classification_stats(groups)


def _cover_story(
    event: dict[str, Any],
    styles: dict[str, ParagraphStyle],
    subtitle: str = "Relatório final",
) -> list[Any]:
    logo = Image(str(LOGO_PATH), width=36 * mm, height=36 * mm)
    logo.hAlign = "CENTER"
    location = f" · {event['location']}" if event.get("location") else ""
    event_date = (
        f"Data da prova: {display_date(event['event_date'])}"
        if event.get("event_date")
        else "Data da prova não definida"
    )
    return [
        Spacer(1, 45 * mm),
        logo,
        Spacer(1, 8 * mm),
        Paragraph("TRISCORE", styles["cover_subtitle"]),
        Paragraph(escape(event["name"]), styles["cover_title"]),
        Paragraph(escape(subtitle), styles["cover_subtitle"]),
        Spacer(1, 7 * mm),
        Paragraph(
            f"{escape(event_date)}{escape(location)}",
            styles["cover_meta"],
        ),
        Spacer(1, 3 * mm),
        Paragraph(
            f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
            styles["cover_meta"],
        ),
        PageBreak(),
    ]


def export_final_report(
    connection: sqlite3.Connection,
    event: dict[str, Any],
    exports_dir: str | Path | None = None,
) -> Path:
    styles = _styles()
    groups, stats = final_report_groups(connection, event)
    story = _cover_story(event, styles)
    story.extend(
        [
            Paragraph("Resumo geral", styles["title"]),
            Paragraph(escape(event["name"]), styles["body"]),
            Spacer(1, 4 * mm),
        ]
    )
    summary_data = [
        ["Grupos", "Classificados", "Status especiais", "Pendentes", "Total"],
        [
            str(stats["groups"]),
            str(stats["finished"]),
            str(stats["special"]),
            str(stats["pending"]),
            str(stats["athletes"]),
        ],
    ]
    summary_table = Table(
        summary_data,
        colWidths=[27 * mm, 33 * mm, 36 * mm, 30 * mm, 27 * mm],
        hAlign="LEFT",
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SURFACE),
                ("FONTNAME", (0, 0), (-1, 0), FONT_SEMIBOLD),
                ("FONTNAME", (0, 1), (-1, 1), FONT_MEDIUM),
                ("TEXTCOLOR", (0, 0), (-1, -1), TEAL_DARK),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.extend([summary_table, Spacer(1, 6 * mm)])

    if groups:
        for group in groups:
            heading = (
                f"{escape(group['category_name'])} · {group['sex_label']}"
            )
            intro = (
                f"{group['finished_count']} classificado(s), "
                f"{group['special_count']} status especial(is), "
                f"{group['pending_count']} pendente(s)."
            )
            story.append(
                KeepTogether(
                    [
                        Paragraph(heading, styles["heading"]),
                        Paragraph(intro, styles["small"]),
                        Spacer(1, 1.5 * mm),
                    ]
                )
            )
            data: list[list[str]] = [
                ["Pos.", "Peito", "Nome", "Equipe", "Tempo", "Status"]
            ]
            for athlete in group["athletes"]:
                data.append(
                    [
                        str(athlete["position"]) if athlete["position"] else "—",
                        str(athlete["bib"]),
                        athlete["name"],
                        athlete.get("team") or "Sem equipe",
                        athlete["formatted_time"] if athlete["result_status"] == "OK" else "—",
                        athlete["result_status"] or "Sem resultado",
                    ]
                )
            story.append(
                _table(
                    data,
                    [13 * mm, 15 * mm, 56 * mm, 38 * mm, 28 * mm, 25 * mm],
                    align=["CENTER", "CENTER", "LEFT", "LEFT", "CENTER", "CENTER"],
                )
            )
            story.append(Spacer(1, 4 * mm))
    else:
        story.append(Paragraph("Nenhum atleta para classificar.", styles["body"]))

    story.extend(
        [
            PageBreak(),
            Paragraph("Observações", styles["title"]),
            Paragraph(
                "Use este espaço para anotações da organização da prova.",
                styles["body"],
            ),
            Spacer(1, 4 * mm),
        ]
    )
    observation_rows = [[""] for _ in range(14)]
    observation_table = Table(
        observation_rows, colWidths=[180 * mm], rowHeights=[11 * mm] * len(observation_rows)
    )
    observation_table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(observation_table)
    return _build_pdf(
        event,
        kind="relatorio_final",
        title="Relatório final",
        story=story,
        exports_dir=exports_dir,
        skip_cover_header=True,
    )


def _awards_background_reader(
    settings: dict[str, Any],
    theme: dict[str, Any],
    media_dir: str | Path | None,
    event_id: int,
):
    backdrop = award_assets.asset_path(
        media_dir, event_id, settings.get("background_filename")
    ) if media_dir is not None else None
    if backdrop is None:
        return None
    try:
        base_color = theme["background_color"].lstrip("#")
        base = PILImage.new(
            "RGB", (1240, 1754), tuple(int(base_color[i:i + 2], 16) for i in (0, 2, 4))
        )
        image = PILImage.open(backdrop).convert("RGB")
        image = ImageOps.fit(image, base.size, method=PILImage.Resampling.LANCZOS)
        opacity = int(settings.get("background_opacity", 35)) / 100
        dim = int(settings.get("background_dim", 55)) / 100
        image = PILImage.blend(base, image, opacity)
        image = PILImage.blend(image, base, dim)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return ImageReader(buffer), buffer
    except (OSError, ValueError):
        return None


def export_awards(
    connection: sqlite3.Connection,
    event: dict[str, Any],
    *,
    theme: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
    media_dir: str | Path | None = None,
    exports_dir: str | Path | None = None,
) -> Path:
    _register_fonts()
    styles = _styles()
    if settings is None:
        settings = award_service.get_settings(connection, event["id"])
    if theme is None:
        theme = award_service.resolve_theme(settings)
    data = award_service.build_awards(connection, event["id"])
    accent = colors.HexColor(theme["accent_color"])
    header_text = colors.HexColor("#08191d") if theme["is_dark"] else WHITE
    layout = settings.get("layout") or "classic"

    custom_font = None
    font_path = award_assets.asset_path(
        media_dir, event["id"], settings.get("font_filename")
    ) if media_dir is not None else None
    if font_path is not None and font_path.suffix.lower() == ".ttf":
        try:
            custom_font = "AwardCustomPdf"
            pdfmetrics.registerFont(TTFont(custom_font, str(font_path)))
        except Exception:
            custom_font = None
    heading_style = ParagraphStyle(
        "awards_heading",
        parent=styles["heading"],
        fontName=custom_font or FONT_SEMIBOLD,
        fontSize=18 if layout == "highlight" else 13,
        leading=22 if layout == "highlight" else 16,
        alignment=TA_CENTER if layout == "classic" else TA_LEFT,
        textColor=accent,
    )
    position_style = ParagraphStyle(
        "awards_position",
        parent=styles["cell_bold"],
        fontName=custom_font or FONT_BOLD,
        fontSize=18 if layout == "highlight" else 8.5,
        leading=20 if layout == "highlight" else 11,
        textColor=accent,
        alignment=TA_CENTER,
    )
    spotlight_style = ParagraphStyle(
        "awards_spotlight",
        parent=styles["cover_title"],
        fontName=custom_font or FONT_BOLD,
        fontSize=24 if layout == "classic" else 30,
        textColor=accent,
        alignment=TA_CENTER if layout == "classic" else TA_LEFT,
    )

    story = _cover_story(event, styles, subtitle="Premiação · plano B")
    story.extend(
        [
            Paragraph(escape(settings.get("opening_title") or "Premiação"), spotlight_style),
            Spacer(1, 4 * mm),
        ]
    )
    if settings.get("opening_text"):
        story.append(Paragraph(escape(settings["opening_text"]), styles["body"]))
    story.extend(
        [
            Spacer(1, 4 * mm),
            Paragraph(
                f"{data['stats']['podium_groups']} grupo(s) com pódio · "
                f"{data['stats']['skipped_groups']} grupo(s) sem atletas classificados.",
                styles["small"],
            ),
            PageBreak(),
        ]
    )

    if not data["groups"]:
        story.append(
            Paragraph(
                "Nenhum pódio disponível. Lance resultados válidos na súmula.",
                styles["body"],
            )
        )

    for index, group in enumerate(data["groups"]):
        if layout == "modern":
            story.append(
                Table(
                    [[""]],
                    colWidths=[180 * mm],
                    rowHeights=[1.8 * mm],
                    style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), accent)]),
                )
            )
            story.append(Spacer(1, 2 * mm))
        heading = (
            f"{escape(group.get('display_title') or group['category_name'])}"
            f" · {group['sex_label']}"
        )
        if layout == "highlight":
            heading = heading.upper()
        story.append(Paragraph(heading, heading_style))
        if group.get("call_text"):
            story.append(Paragraph(escape(group["call_text"]), styles["body"]))
        story.append(Spacer(1, 2 * mm))
        rows: list[list[Any]] = [["Pos.", "Peito", "Nome", "Equipe", "Tempo"]]
        for position in (1, 2, 3):
            for athlete in group["podium"][position]:
                position_cell = (
                    Paragraph(f"{position}º", position_style)
                    if layout == "highlight"
                    else f"{position}º"
                )
                rows.append(
                    [
                        position_cell,
                        str(athlete["bib"]),
                        athlete["name"],
                        athlete.get("team") or "Sem equipe",
                        athlete["formatted_time"],
                    ]
                )
        story.append(
            _table(
                rows,
                [16 * mm, 18 * mm, 68 * mm, 50 * mm, 28 * mm],
                align=["CENTER", "CENTER", "LEFT", "LEFT", "CENTER"],
                header_background=accent,
                header_text=header_text,
            )
        )
        if index < len(data["groups"]) - 1:
            story.append(PageBreak())

    if data["groups"]:
        story.append(PageBreak())
    story.extend(
        [
            Paragraph(
                escape(settings.get("closing_title") or "Obrigado!"),
                spotlight_style,
            ),
            Spacer(1, 4 * mm),
        ]
    )
    if settings.get("closing_text"):
        story.append(Paragraph(escape(settings["closing_text"]), styles["body"]))

    final_path = output_path(event, "premiacao", exports_dir)
    temp_path = final_path.with_suffix(".tmp.pdf")
    background = _awards_background_reader(
        settings, theme, media_dir, event["id"]
    )
    background_reader = background[0] if background else None
    banner_path = award_assets.asset_path(
        media_dir, event["id"], settings.get("banner_filename")
    ) if media_dir is not None else None
    banner_reader = None
    if banner_path is not None:
        try:
            image = PILImage.open(banner_path).convert("RGB")
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            buffer.seek(0)
            banner_reader = ImageReader(buffer)
        except (OSError, ValueError):
            banner_reader = None
    header = _page_decorator(event["name"], "Premiação — plano B", skip_cover=True)

    def draw_page(canvas, doc):
        if background_reader is not None:
            canvas.drawImage(
                background_reader,
                0,
                0,
                width=A4[0],
                height=A4[1],
                preserveAspectRatio=False,
            )
        if banner_reader is not None:
            width, height = banner_reader.getSize()
            max_width = A4[0] - 30 * mm
            max_height = 14 * mm if doc.page > 1 else 22 * mm
            ratio = min(max_width / width, max_height / height)
            draw_width = width * ratio
            draw_height = height * ratio
            canvas.drawImage(
                banner_reader,
                (A4[0] - draw_width) / 2,
                A4[1] - (18 * mm if doc.page > 1 else 20 * mm) - draw_height,
                width=draw_width,
                height=draw_height,
                mask="auto",
            )
        header(canvas, doc)

    document = SimpleDocTemplate(
        str(temp_path),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=(34 if banner_reader is not None else 20) * mm,
        bottomMargin=16 * mm,
        title="Premiação — plano B",
        author="Triscore",
        subject=f"Premiação · {event['name']}",
    )
    try:
        document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
        os.replace(temp_path, final_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return final_path
