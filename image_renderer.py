from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from background_data import get_background_bytes
from image_styles import (
    FONT_SOURCES,
    FONT_THEMES,
    IMAGE_FORMATS,
    MONTHS_RU,
    STYLES,
    STYLE_ALIASES,
    STYLE_TITLES,
    WEEKDAYS_RU_SHORT,
)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def load_font_from_sources(sources: Iterable[str | Path], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in sources:
        try:
            return ImageFont.truetype(str(path), max(8, int(size)))
        except OSError:
            continue
    return ImageFont.load_default()


def themed_font(theme: str, role: str, size: int):
    theme_map = FONT_THEMES.get(theme, FONT_THEMES["clean"])
    font_key = theme_map.get(role, "inter_regular")
    return load_font_from_sources(FONT_SOURCES[font_key], size)


def russian_date(date_text: str, include_weekday: bool = False) -> str:
    try:
        value = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return date_text
    result = f"{value.day} {MONTHS_RU[value.month]} {value.year}"
    return f"{WEEKDAYS_RU_SHORT[value.weekday()]}, {result}" if include_weekday else result


def short_location_name(location_name: str) -> str:
    return (location_name or "").split(",")[0].strip()


def normalize_style(style: str) -> str:
    normalized = STYLE_ALIASES.get(style, style)
    return normalized if normalized in STYLES else "modern"


def normalize_format(image_format: str) -> str:
    return image_format if image_format in IMAGE_FORMATS else "16:9"


def _seed(style: str, publish_date: str, image_format: str) -> int:
    digest = hashlib.sha256(f"{style}|{publish_date}|{image_format}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _cover_crop(image: Image.Image, size: tuple[int, int], anchor: tuple[float, float]) -> Image.Image:
    target_w, target_h = size
    src_w, src_h = image.size
    if src_w == target_w and src_h == target_h:
        return image.copy()

    scale = max(target_w / src_w, target_h / src_h)
    resized = image.resize((max(1, int(src_w * scale)), max(1, int(src_h * scale))), Image.Resampling.LANCZOS)
    rw, rh = resized.size
    extra_x = max(0, rw - target_w)
    extra_y = max(0, rh - target_h)
    center_x = min(1.0, max(0.0, anchor[0]))
    center_y = min(1.0, max(0.0, anchor[1]))
    left = int(extra_x * center_x)
    top = int(extra_y * center_y)
    left = max(0, min(left, extra_x))
    top = max(0, min(top, extra_y))
    return resized.crop((left, top, left + target_w, top + target_h))


def _apply_overlay(base: Image.Image, mode: str) -> Image.Image:
    w, h = base.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    if mode == "dark":
        top_h = int(h * 0.32)
        bottom_h = int(h * 0.42)
        for i in range(top_h):
            alpha = int(125 * (1 - i / max(1, top_h)) ** 1.65)
            draw.line((0, i, w, i), fill=(6, 8, 12, alpha))
        for idx in range(bottom_h):
            y = h - bottom_h + idx
            alpha = int(95 * (idx / max(1, bottom_h)) ** 1.2)
            draw.line((0, y, w, y), fill=(6, 8, 12, alpha))
        draw.ellipse((-w * 0.1, int(h * 0.04), int(w * 1.1), int(h * 0.92)), fill=(0, 0, 0, 34))
        overlay = overlay.filter(ImageFilter.GaussianBlur(max(8, min(w, h) // 55)))
    elif mode == "light":
        wash = Image.new("RGBA", (w, h), (255, 255, 255, 34))
        overlay.alpha_composite(wash)
    elif mode == "soft-light":
        wash = Image.new("RGBA", (w, h), (255, 255, 255, 18))
        overlay.alpha_composite(wash)
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        for idx in range(int(h * 0.22)):
            alpha = int(42 * (1 - idx / max(1, int(h * 0.22))) ** 1.5)
            shadow_draw.line((0, idx, w, idx), fill=(0, 0, 0, alpha))
        overlay.alpha_composite(shadow)

    return Image.alpha_composite(base.convert("RGBA"), overlay)


def _add_grain(image: Image.Image, opacity: int = 6) -> Image.Image:
    w, h = image.size
    noise = Image.effect_noise((max(180, w // 3), max(180, h // 3)), 12).convert("L")
    noise = noise.resize((w, h), Image.Resampling.BILINEAR)
    alpha = Image.new("L", (w, h), opacity)
    layer = Image.merge("RGBA", (noise, noise, noise, alpha))
    return Image.alpha_composite(image.convert("RGBA"), layer)


def _layout(size: tuple[int, int]) -> dict[str, int | tuple[int, int, int, int] | bool]:
    w, h = size
    portrait = h > w * 1.12
    squareish = not portrait and h > w * 0.86
    margin_x = int(w * (0.07 if not portrait else 0.06))
    margin_y = int(h * (0.07 if not portrait else 0.052))
    card = (margin_x, margin_y, w - margin_x, h - margin_y)

    if portrait:
        return {
            "portrait": True,
            "card": card,
            "eyebrow_y": int(h * 0.15),
            "title_y": int(h * 0.24),
            "time_y": int(h * 0.42),
            "date_y": int(h * 0.64),
            "city_y": int(h * 0.74),
            "title_size": int(w * 0.078),
            "time_size": int(w * 0.185),
            "date_size": int(w * 0.043),
            "city_size": int(w * 0.036),
            "eyebrow_size": int(w * 0.022),
            "max_text_width": int(w * 0.78),
        }
    if squareish:
        return {
            "portrait": False,
            "card": card,
            "eyebrow_y": int(h * 0.145),
            "title_y": int(h * 0.235),
            "time_y": int(h * 0.415),
            "date_y": int(h * 0.65),
            "city_y": int(h * 0.74),
            "title_size": int(w * 0.066),
            "time_size": int(w * 0.155),
            "date_size": int(w * 0.038),
            "city_size": int(w * 0.031),
            "eyebrow_size": int(w * 0.018),
            "max_text_width": int(w * 0.76),
        }
    return {
        "portrait": False,
        "card": card,
        "eyebrow_y": int(h * 0.14),
        "title_y": int(h * 0.245),
        "time_y": int(h * 0.43),
        "date_y": int(h * 0.69),
        "city_y": int(h * 0.79),
        "title_size": int(h * 0.09),
        "time_size": int(h * 0.20),
        "date_size": int(h * 0.05),
        "city_size": int(h * 0.036),
        "eyebrow_size": int(h * 0.026),
        "max_text_width": int(w * 0.74),
    }


def _text_size(font, text: str, spacing: int = 0) -> tuple[int, int]:
    box = font.getbbox(text, anchor=None)
    return box[2] - box[0], box[3] - box[1]


def _fit_single_line(text: str, max_width: int, start_size: int, min_size: int, theme: str, role: str):
    size = start_size
    while size >= min_size:
        font = themed_font(theme, role, size)
        width, _ = _text_size(font, text)
        if width <= max_width:
            return font
        size -= max(1, size // 12)
    return themed_font(theme, role, min_size)


def _wrap_text(text: str, font, max_width: int, max_lines: int = 2) -> list[str] | None:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}".strip()
        if _text_size(font, candidate)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                return None
    lines.append(current)
    if len(lines) > max_lines:
        return None
    return lines


def _fit_multiline(text: str, max_width: int, start_size: int, min_size: int, theme: str, role: str, max_lines: int = 2):
    size = start_size
    best_lines = [text]
    while size >= min_size:
        font = themed_font(theme, role, size)
        lines = _wrap_text(text, font, max_width, max_lines=max_lines)
        if lines:
            return font, lines
        size -= max(1, size // 12)
    font = themed_font(theme, role, min_size)
    shortened = text[: max(12, min(42, len(text)))]
    best_lines = _wrap_text(shortened, font, max_width, max_lines=max_lines) or [shortened]
    return font, best_lines


def _draw_centered_text(draw: ImageDraw.ImageDraw, text: str, y: int, font, fill, width: int, shadow_alpha: int = 80):
    text_w, _ = _text_size(font, text)
    x = (width - text_w) / 2
    if shadow_alpha > 0:
        offset = max(2, getattr(font, "size", 20) // 18)
        draw.text((x, y + offset), text, font=font, fill=(0, 0, 0, shadow_alpha))
    draw.text((x, y), text, font=font, fill=fill)


def _draw_multiline_centered(draw: ImageDraw.ImageDraw, lines: list[str], top_y: int, font, fill, width: int, line_gap: int = 10, shadow_alpha: int = 80) -> int:
    sizes = [_text_size(font, line) for line in lines]
    total_h = sum(height for _, height in sizes) + line_gap * max(0, len(lines) - 1)
    y = top_y - total_h // 2
    for idx, line in enumerate(lines):
        _draw_centered_text(draw, line, y, font, fill, width, shadow_alpha=shadow_alpha)
        y += sizes[idx][1] + line_gap
    return total_h


def _rounded_card(base: Image.Image, box: tuple[int, int, int, int], fill: tuple[int, int, int, int], outline: tuple[int, int, int, int], radius: int) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=max(1, radius // 11))
    base.alpha_composite(layer)


def _draw_eyebrow(draw: ImageDraw.ImageDraw, text: str, y: int, font, cfg: dict, width: int) -> None:
    fill = (*cfg["secondary"], 220)
    _draw_centered_text(draw, text, y, font, fill, width, shadow_alpha=0)
    text_w, text_h = _text_size(font, text)
    line_w = max(40, int(text_w * 0.22))
    cy = y + text_h // 2 + 2
    gap = max(18, text_h)
    x1 = width / 2 - text_w / 2 - gap
    x2 = width / 2 + text_w / 2 + gap
    draw.line((x1 - line_w, cy, x1, cy), fill=(*cfg["accent"], 120), width=max(2, getattr(font, "size", 14) // 10))
    draw.line((x2, cy, x2 + line_w, cy), fill=(*cfg["accent"], 120), width=max(2, getattr(font, "size", 14) // 10))


def _draw_date_badge(base: Image.Image, text: str, y: int, font, cfg: dict, width: int) -> None:
    draw = ImageDraw.Draw(base, "RGBA")
    text_w, text_h = _text_size(font, text)
    pad_x = max(20, getattr(font, "size", 20))
    pad_y = max(10, getattr(font, "size", 20) // 3)
    x1 = int(width / 2 - text_w / 2 - pad_x)
    y1 = int(y - pad_y)
    x2 = int(width / 2 + text_w / 2 + pad_x)
    y2 = int(y + text_h + pad_y)
    radius = max(18, (y2 - y1) // 2)

    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    style = cfg.get("date_style", "pill")
    if style == "frame":
        layer_draw.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=cfg["date_fill"], outline=cfg["date_outline"], width=max(2, radius // 10))
        inner_y = y2 + max(10, text_h // 2)
        layer_draw.line((x1 + radius, inner_y, x2 - radius, inner_y), fill=(*cfg["accent"], 88), width=max(2, text_h // 8))
    elif style == "glass":
        layer_draw.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=cfg["date_fill"], outline=cfg["date_outline"], width=max(2, radius // 12))
        layer_draw.line((x1 + radius, y1 + 2, x2 - radius, y1 + 2), fill=(255, 255, 255, 50), width=max(1, radius // 10))
    else:
        layer_draw.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=cfg["date_fill"], outline=cfg["date_outline"], width=max(2, radius // 12))
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(max(1, radius // 20))))
    draw = ImageDraw.Draw(base, "RGBA")
    _draw_centered_text(draw, text, y, font, (*cfg["secondary"], 245), width, shadow_alpha=0)


def _compose_background(style: str, size: tuple[int, int]) -> Image.Image:
    cfg = STYLES[style]
    with Image.open(BytesIO(get_background_bytes(cfg["background"]))) as bg:
        bg = ImageOps.exif_transpose(bg).convert("RGB")
        composed = _cover_crop(bg, size, cfg["anchor"])
    return _apply_overlay(composed.convert("RGBA"), cfg.get("overlay", "soft-light"))


def create_sunset_image(
    sunset_time: str,
    publish_date: str,
    style: str = "modern",
    title_text: str = "Заход солнца",
    location_name: str = "",
    show_city: bool = False,
    show_weekday: bool = False,
    image_format: str = "16:9",
) -> str:
    style = normalize_style(style)
    image_format = normalize_format(image_format)
    w, h = IMAGE_FORMATS[image_format]["size"]
    cfg = STYLES[style]
    layout = _layout((w, h))
    seed = _seed(style, publish_date, image_format)
    safe_title = (title_text or "Заход солнца").strip()[:52]
    date_text = russian_date(publish_date, include_weekday=bool(show_weekday))
    city = short_location_name(location_name).upper()[:36]

    image = _compose_background(style, (w, h))
    card = layout["card"]
    radius = max(28, int(min(w, h) * 0.05))
    _rounded_card(image, card, cfg["card_fill"], cfg["card_outline"], radius)

    draw = ImageDraw.Draw(image, "RGBA")
    theme = cfg.get("font_theme", "clean")
    max_text_width = int(layout["max_text_width"])

    eyebrow_font = themed_font(theme, "eyebrow", int(layout["eyebrow_size"]))
    title_font, title_lines = _fit_multiline(
        safe_title,
        max_width=max_text_width,
        start_size=int(layout["title_size"]),
        min_size=max(22, int(layout["title_size"]) // 2),
        theme=theme,
        role="title",
        max_lines=2,
    )
    time_font = _fit_single_line(
        sunset_time,
        max_width=max_text_width,
        start_size=int(layout["time_size"]),
        min_size=max(42, int(layout["time_size"]) // 2),
        theme=theme,
        role="time",
    )
    date_font = _fit_single_line(
        date_text,
        max_width=int(max_text_width * 0.92),
        start_size=int(layout["date_size"]),
        min_size=max(18, int(layout["date_size"]) // 2),
        theme=theme,
        role="date",
    )
    city_font = _fit_single_line(
        f"•  {city}" if city else "",
        max_width=int(max_text_width * 0.9),
        start_size=int(layout["city_size"]),
        min_size=max(16, int(layout["city_size"]) // 2),
        theme=theme,
        role="city",
    )

    _draw_eyebrow(draw, cfg["eyebrow"], int(layout["eyebrow_y"]), eyebrow_font, cfg, w)
    _draw_multiline_centered(
        draw,
        title_lines,
        int(layout["title_y"]),
        title_font,
        (*cfg["text"], 255),
        w,
        line_gap=max(8, getattr(title_font, "size", 24) // 4),
        shadow_alpha=70 if cfg.get("overlay") == "dark" else 28,
    )
    _draw_centered_text(
        draw,
        sunset_time,
        int(layout["time_y"]),
        time_font,
        (*cfg["text"], 255),
        w,
        shadow_alpha=82 if cfg.get("overlay") == "dark" else 30,
    )
    _draw_date_badge(image, date_text, int(layout["date_y"]), date_font, cfg, w)
    if show_city and city:
        _draw_centered_text(draw, f"•  {city}", int(layout["city_y"]), city_font, (*cfg["secondary"], 245), w, shadow_alpha=0)

    image = _add_grain(image, opacity=4 if cfg.get("overlay") == "light" else 6)

    out = OUTPUT_DIR / (
        f"sunset_{style}_{image_format.replace(':', 'x')}_{seed % 10000:04d}_{datetime.now():%Y%m%d_%H%M%S}_{secrets.token_hex(3)}.png"
    )
    image.convert("RGB").save(out, format="PNG", optimize=True)
    return str(out)
