from __future__ import annotations

import math
import secrets
from datetime import datetime
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUTPUT_DIR = Path("generated")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}
WEEKDAYS_RU_SHORT = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}

STYLE_TITLES = {
    "modern": "✨ Obsidian Gold",
    "synth": "🌆 Neon Riviera",
    "arctic": "❄️ Polar Glass",
    "dune": "🏜 Desert Luxe",
    "void": "🌌 Midnight Cosmos",
}

PALETTES = {
    "modern": {
        "top": (8, 12, 28), "mid": (25, 31, 62), "bottom": (215, 101, 46),
        "sun": (255, 221, 154), "accent": (255, 194, 105), "text": (250, 248, 242),
        "muted": (211, 216, 230), "land": (7, 10, 20),
    },
    "synth": {
        "top": (16, 6, 38), "mid": (74, 22, 105), "bottom": (236, 58, 112),
        "sun": (255, 214, 124), "accent": (255, 82, 176), "text": (255, 247, 255),
        "muted": (226, 205, 241), "land": (18, 5, 32),
    },
    "arctic": {
        "top": (3, 13, 34), "mid": (13, 65, 92), "bottom": (82, 193, 186),
        "sun": (230, 252, 255), "accent": (126, 236, 229), "text": (245, 254, 255),
        "muted": (201, 230, 236), "land": (4, 18, 31),
    },
    "dune": {
        "top": (37, 20, 28), "mid": (113, 54, 48), "bottom": (239, 151, 83),
        "sun": (255, 229, 164), "accent": (247, 179, 97), "text": (255, 249, 238),
        "muted": (236, 214, 193), "land": (31, 17, 17),
    },
    "void": {
        "top": (3, 4, 14), "mid": (18, 19, 43), "bottom": (82, 39, 67),
        "sun": (236, 205, 255), "accent": (179, 113, 255), "text": (247, 244, 255),
        "muted": (205, 198, 224), "land": (2, 3, 10),
    },
}


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates: Iterable[str] = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def russian_date(date_text: str, include_weekday: bool = False) -> str:
    try:
        value = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return date_text
    result = f"{value.day} {MONTHS_RU[value.month]} {value.year}"
    return f"{WEEKDAYS_RU_SHORT[value.weekday()]}, {result}" if include_weekday else result


def short_location_name(location_name: str) -> str:
    return (location_name or "").split(",")[0].strip()


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _gradient(size: tuple[int, int], stops: list[tuple[float, tuple[int, int, int]]]) -> Image.Image:
    w, h = size
    strip = Image.new("RGB", (1, h))
    px = strip.load()
    for y in range(h):
        pos = y / max(1, h - 1)
        left, right = stops[0], stops[-1]
        for i in range(len(stops) - 1):
            if stops[i][0] <= pos <= stops[i + 1][0]:
                left, right = stops[i], stops[i + 1]
                break
        span = max(1e-6, right[0] - left[0])
        t = (pos - left[0]) / span
        px[0, y] = tuple(_lerp(left[1][c], right[1][c], t) for c in range(3))
    return strip.resize((w, h))


def _radial_glow(size: tuple[int, int], center: tuple[int, int], radius: int, color: tuple[int, int, int], alpha: int) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy = center
    for r in range(radius, 0, -8):
        t = 1 - r / radius
        a = int(alpha * (t ** 2))
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*color, a))
    return layer.filter(ImageFilter.GaussianBlur(max(12, radius // 10)))


def _draw_stars(img: Image.Image, count: int, seed: int) -> None:
    rng = __import__("random").Random(seed)
    draw = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    for _ in range(count):
        x = rng.randrange(24, w - 24)
        y = rng.randrange(18, int(h * 0.55))
        r = rng.choice((1, 1, 1, 2))
        a = rng.randrange(35, 130)
        draw.ellipse((x-r, y-r, x+r, y+r), fill=(255, 255, 255, a))


def _draw_landscape(img: Image.Image, land: tuple[int, int, int], style: str) -> None:
    w, h = img.size
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    horizon = int(h * 0.73)
    if style == "dune":
        d.polygon([(0, horizon+30), (200, horizon-10), (410, horizon+45), (690, horizon-30), (920, horizon+25), (w, horizon-15), (w, h), (0, h)], fill=(*land, 235))
        d.polygon([(0, horizon+70), (260, horizon+30), (520, horizon+78), (820, horizon+22), (w, horizon+65), (w, h), (0, h)], fill=(*tuple(max(0, c-4) for c in land), 255))
    else:
        d.polygon([(0, horizon+35), (150, horizon-25), (305, horizon+22), (470, horizon-62), (650, horizon+10), (820, horizon-35), (1010, horizon+30), (w, horizon-18), (w, h), (0, h)], fill=(*land, 235))
        d.polygon([(0, horizon+86), (250, horizon+25), (450, horizon+82), (710, horizon+18), (930, horizon+76), (w, horizon+35), (w, h), (0, h)], fill=(*tuple(max(0, c-5) for c in land), 255))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(1.2)))


def _rounded_glass(base: Image.Image, box: tuple[int, int, int, int], radius: int = 34) -> None:
    x1, y1, x2, y2 = box
    crop = base.crop(box).filter(ImageFilter.GaussianBlur(22)).convert("RGBA")
    tint = Image.new("RGBA", crop.size, (8, 11, 25, 138))
    crop = Image.alpha_composite(crop, tint)
    mask = Image.new("L", crop.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, crop.width-1, crop.height-1), radius=radius, fill=255)
    base.paste(crop, (x1, y1), mask)
    border = Image.new("RGBA", base.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bd.rounded_rectangle(box, radius=radius, outline=(255, 255, 255, 52), width=2)
    bd.line((x1+42, y1+1, x2-42, y1+1), fill=(255, 255, 255, 70), width=2)
    base.alpha_composite(border)


def _text_center(draw: ImageDraw.ImageDraw, text: str, y: int, font, fill, width: int, shadow: bool = True) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    x = (width - (box[2] - box[0])) / 2
    if shadow:
        draw.text((x, y + 4), text, font=font, fill=(0, 0, 0, 105))
    draw.text((x, y), text, font=font, fill=fill)


def _add_grain(img: Image.Image, opacity: int = 14) -> Image.Image:
    noise = Image.effect_noise(img.size, 22).convert("L")
    alpha = Image.new("L", img.size, opacity)
    noise_rgba = Image.merge("RGBA", (noise, noise, noise, alpha))
    return Image.alpha_composite(img.convert("RGBA"), noise_rgba)


def create_sunset_image(
    sunset_time: str,
    publish_date: str,
    style: str = "modern",
    title_text: str = "Заход солнца",
    location_name: str = "",
    show_city: bool = False,
    show_weekday: bool = False,
) -> str:
    w, h = 1280, 720
    style = style if style in PALETTES else "modern"
    p = PALETTES[style]

    img = _gradient((w, h), [(0.0, p["top"]), (0.56, p["mid"]), (1.0, p["bottom"])]).convert("RGBA")
    img.alpha_composite(_radial_glow((w, h), (w // 2, int(h * 0.69)), 300, p["sun"], 150))
    img.alpha_composite(_radial_glow((w, h), (int(w * 0.15), int(h * 0.28)), 260, p["accent"], 45))
    if style in {"void", "synth", "arctic"}:
        _draw_stars(img, 80 if style == "void" else 38, seed=hash((style, publish_date)) & 0xFFFF)

    sun_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sun_layer)
    sun_r = 82
    sun_cx, sun_cy = w // 2, int(h * 0.69)
    sd.ellipse((sun_cx-sun_r, sun_cy-sun_r, sun_cx+sun_r, sun_cy+sun_r), fill=(*p["sun"], 245))
    img.alpha_composite(sun_layer.filter(ImageFilter.GaussianBlur(2)))
    _draw_landscape(img, p["land"], style)

    card = (95, 78, w - 95, h - 78)
    _rounded_glass(img, card, radius=38)
    draw = ImageDraw.Draw(img, "RGBA")

    title_font = load_font(44, True)
    time_font = load_font(150, True)
    date_font = load_font(34, False)
    city_font = load_font(28, True)
    micro_font = load_font(21, False)

    eyebrow = "SUNSET  •  ONE HOUR BEFORE"
    _text_center(draw, eyebrow, 112, micro_font, (*p["muted"], 205), w, shadow=False)
    draw.rounded_rectangle((w//2-74, 150, w//2+74, 154), radius=2, fill=(*p["accent"], 220))

    safe_title = (title_text or "Заход солнца").strip()[:42]
    _text_center(draw, safe_title, 177, title_font, (*p["text"], 255), w)
    _text_center(draw, sunset_time, 254, time_font, (*p["text"], 255), w)

    date_text = russian_date(publish_date, include_weekday=bool(show_weekday))
    date_box = draw.textbbox((0, 0), date_text, font=date_font)
    date_w = date_box[2] - date_box[0]
    pill = (w//2-date_w//2-28, 458, w//2+date_w//2+28, 510)
    draw.rounded_rectangle(pill, radius=26, fill=(8, 11, 25, 118), outline=(255, 255, 255, 38), width=1)
    _text_center(draw, date_text, 465, date_font, (*p["muted"], 245), w, shadow=False)

    if show_city and location_name:
        city = short_location_name(location_name).upper()[:36]
        _text_center(draw, f"•  {city}", 538, city_font, (*p["muted"], 225), w, shadow=False)

    for x in (card[0]+28, card[2]-28):
        draw.ellipse((x-3, card[1]+27, x+3, card[1]+33), fill=(*p["accent"], 190))

    img = _add_grain(img, opacity=3)
    out = OUTPUT_DIR / f"sunset_{datetime.now():%Y%m%d_%H%M%S}_{secrets.token_hex(3)}.png"
    img.convert("RGB").save(out, format="PNG", optimize=True)
    return str(out)
