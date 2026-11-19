from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_FONT_BYTES = 3 * 1024 * 1024
IMAGE_EXTENSIONS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
IMAGE_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
FONT_MEDIA_TYPES = {".ttf": "font/ttf", ".woff2": "font/woff2"}
FONT_FORMATS = {".ttf": "truetype", ".woff2": "woff2"}


def event_media_dir(media_root: str | Path, event_id: int) -> Path:
    path = Path(media_root) / str(event_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalized_extension(filename: str) -> str:
    extension = Path(filename or "").suffix.lower()
    return ".jpg" if extension == ".jpeg" else extension


def validate_image(filename: str, content: bytes) -> str:
    extension = _normalized_extension(filename)
    expected_format = IMAGE_EXTENSIONS.get(extension)
    if expected_format is None:
        raise ValueError("Use uma imagem PNG, JPEG ou WebP.")
    if not content:
        raise ValueError("A imagem enviada está vazia.")
    if len(content) > MAX_IMAGE_BYTES:
        raise ValueError("A imagem deve ter no máximo 8 MB.")
    try:
        with Image.open(BytesIO(content)) as image:
            image_format = (image.format or "").upper()
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ValueError("O arquivo enviado não é uma imagem válida.") from error
    if image_format != expected_format:
        raise ValueError("A extensão da imagem não corresponde ao conteúdo.")
    return extension


def validate_font(filename: str, content: bytes) -> tuple[str, str]:
    extension = _normalized_extension(filename)
    if extension not in FONT_MEDIA_TYPES:
        raise ValueError("Use uma fonte WOFF2 ou TTF.")
    if not content:
        raise ValueError("A fonte enviada está vazia.")
    if len(content) > MAX_FONT_BYTES:
        raise ValueError("A fonte deve ter no máximo 3 MB.")
    if extension == ".woff2" and not content.startswith(b"wOF2"):
        raise ValueError("O arquivo não é uma fonte WOFF2 válida.")
    if extension == ".ttf" and not (
        content.startswith(b"\x00\x01\x00\x00") or content.startswith(b"true")
    ):
        raise ValueError("O arquivo não é uma fonte TTF válida.")
    return extension, FONT_FORMATS[extension]


def save_asset(
    media_root: str | Path,
    event_id: int,
    kind: str,
    filename: str,
    content: bytes,
) -> str:
    if kind not in ("banner", "background", "font"):
        raise ValueError("Tipo de arquivo inválido.")
    if kind == "font":
        extension, _ = validate_font(filename, content)
    else:
        extension = validate_image(filename, content)
    directory = event_media_dir(media_root, event_id)
    stored_name = f"{kind}-{uuid.uuid4().hex[:12]}{extension}"
    target = directory / stored_name
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    temporary.write_bytes(content)
    temporary.replace(target)
    return stored_name


def asset_path(media_root: str | Path, event_id: int, filename: str | None) -> Path | None:
    if not filename:
        return None
    directory = (Path(media_root) / str(event_id)).resolve()
    target = (directory / Path(filename).name).resolve()
    if target.parent != directory or not target.exists():
        return None
    return target


def delete_asset(media_root: str | Path, event_id: int, filename: str | None) -> None:
    target = asset_path(media_root, event_id, filename)
    if target is not None:
        target.unlink(missing_ok=True)


def media_type(filename: str) -> str:
    extension = _normalized_extension(filename)
    return IMAGE_MEDIA_TYPES.get(extension) or FONT_MEDIA_TYPES.get(
        extension, "application/octet-stream"
    )


def font_format(filename: str | None) -> str | None:
    if not filename:
        return None
    return FONT_FORMATS.get(_normalized_extension(filename))
