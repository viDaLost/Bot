from __future__ import annotations

import hashlib
import math
import random
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

IMAGE_FORMATS = {
    "16:9": {"title": "🖥 16:9 · горизонтальный", "size": (1280, 720)},
    "9:16": {"title": "📱 9:16 · Stories / Reels", "size": (1080, 1920)},
    "1:1": {"title": "◻️ 1:1 · квадрат", "size": (1080, 1080)},
    "4:5": {"title": "🖼 4:5 · публикация", "size": (1080, 1350)},
    "3:2": {"title": "📷 3:2 · фотография", "size": (1200, 800)},
}

STYLE_TITLES = {
    "modern": "✨ Obsidian Gold",
    "synth": "🌆 Neon Riviera",
    "arctic": "❄️ Aurora Crystal",
    "dune": "🏜 Desert Couture",
    "void": "🌌 Celestial Noir",
    "rose": "🌸 Rosé Horizon",
    "emerald": "🌿 Emerald Atelier",
    "ocean": "🌊 Azure Residence",
    "ivory": "🤍 Ivory Editorial",
    "noir": "🖤 Monochrome Prestige",
}

STYLES = {
    "modern": {
        "top": (7, 11, 25), "mid": (29, 34, 64), "bottom": (219, 111, 55),
        "sun": (255, 226, 169), "accent": (242, 190, 103), "text": (252, 249, 241),
        "muted": (214, 218, 230), "land": (5, 8, 17), "scene": "mountains", "glass": (8, 11, 25),
    },
    "synth": {
        "top": (15, 5, 39), "mid": (70, 20, 103), "bottom": (239, 55, 117),
        "sun": (255, 218, 132), "accent": (255, 80, 183), "text": (255, 248, 255),
        "muted": (231, 207, 242), "land": (15, 4, 30), "scene": "city", "glass": (23, 5, 40),
    },
    "arctic": {
        "top": (2, 13, 34), "mid": (8, 63, 91), "bottom": (75, 193, 185),
        "sun": (229, 253, 255), "accent": (120, 238, 226), "text": (246, 254, 255),
        "muted": (203, 232, 237), "land": (3, 17, 29), "scene": "aurora", "glass": (3, 24, 39),
    },
    "dune": {
        "top": (39, 20, 30), "mid": (115, 55, 49), "bottom": (241, 155, 86),
        "sun": (255, 232, 171), "accent": (249, 183, 101), "text": (255, 250, 239),
        "muted": (239, 216, 195), "land": (32, 17, 18), "scene": "dunes", "glass": (41, 19, 23),
    },
    "void": {
        "top": (2, 3, 13), "mid": (17, 18, 43), "bottom": (79, 37, 67),
        "sun": (239, 211, 255), "accent": (181, 116, 255), "text": (248, 245, 255),
        "muted": (207, 200, 226), "land": (1, 2, 9), "scene": "cosmos", "glass": (7, 7, 20),
    },
    "rose": {
        "top": (42, 21, 49), "mid": (131, 70, 94), "bottom": (244, 170, 158),
        "sun": (255, 235, 213), "accent": (255, 184, 185), "text": (255, 250, 247),
        "muted": (245, 219, 218), "land": (41, 22, 38), "scene": "clouds", "glass": (48, 22, 40),
    },
    "emerald": {
        "top": (4, 23, 24), "mid": (15, 76, 66), "bottom": (116, 186, 125),
        "sun": (241, 240, 191), "accent": (166, 222, 156), "text": (248, 253, 243),
        "muted": (205, 231, 210), "land": (3, 24, 19), "scene": "botanical", "glass": (4, 31, 26),
    },
    "ocean": {
        "top": (3, 18, 45), "mid": (19, 90, 132), "bottom": (106, 198, 210),
        "sun": (255, 237, 190), "accent": (117, 219, 232), "text": (246, 253, 255),
        "muted": (202, 232, 240), "land": (2, 25, 44), "scene": "ocean", "glass": (3, 29, 49),
    },
    "ivory": {
        "top": (77, 67, 64), "mid": (166, 137, 116), "bottom": (241, 211, 173),
        "sun": (255, 247, 222), "accent": (226, 184, 132), "text": (255, 253, 246),
        "muted": (241, 229, 211), "land": (65, 55, 53), "scene": "minimal", "glass": (70, 58, 55),
    },
    "noir": {
        "top": (3, 3, 5), "mid": (31, 31, 36), "bottom": (112, 101, 92),
        "sun": (245, 234, 215), "accent": (207, 190, 165), "text": (252, 250, 245),
        "muted": (211, 207, 200), "land": (2, 2, 3), "scene": "noir", "glass": (8, 8, 10),
    },
}

STYLE_ALIASES = {"classic": "modern"}


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates: Iterable[str] = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, max(8, int(size)))
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


def normalize_style(style: str) -> str:
    normalized = STYLE_ALIASES.get(style, style)
    return normalized if normalized in STYLES else "modern"


def normalize_format(image_format: str) -> str:
    return image_format if image_format in IMAGE_FORMATS else "16:9"


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(_lerp(a[i], b[i], t) for i in range(3))


def _gradient(size: tuple[int, int], stops: list[tuple[float, tuple[int, int, int]]]) -> Image.Image:
    w, h = size
    strip = Image.new("RGB", (1, h))
    px = strip.load()
    for y in range(h):
        pos = y / max(1, h - 1)
        left, right = stops[0], stops[-1]
        for index in range(len(stops) - 1):
            if stops[index][0] <= pos <= stops[index + 1][0]:
                left, right = stops[index], stops[index + 1]
                break
        span = max(1e-6, right[0] - left[0])
        t = (pos - left[0]) / span
        px[0, y] = tuple(_lerp(left[1][channel], right[1][channel], t) for channel in range(3))
    return strip.resize((w, h), Image.Resampling.BICUBIC)


def _radial_glow(
    size: tuple[int, int],
    center: tuple[int, int],
    radius: int,
    color: tuple[int, int, int],
    alpha: int,
) -> Image.Image:
    """Рисует свечение в уменьшенном буфере и масштабирует его без тяжёлого blur на 2K."""
    w, h = size
    scale = min(0.28, 360 / max(w, h))
    sw, sh = max(64, int(w * scale)), max(64, int(h * scale))
    cx, cy = int(center[0] * scale), int(center[1] * scale)
    scaled_radius = max(12, int(radius * scale))
    layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    step = max(2, scaled_radius // 30)
    for r in range(scaled_radius, 0, -step):
        t = 1 - r / max(1, scaled_radius)
        a = int(alpha * (t ** 2.2))
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*color, a))
    layer = layer.filter(ImageFilter.GaussianBlur(max(5, scaled_radius // 9)))
    return layer.resize(size, Image.Resampling.BICUBIC)


def _seed(style: str, publish_date: str, image_format: str) -> int:
    digest = hashlib.sha256(f"{style}|{publish_date}|{image_format}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _draw_stars(img: Image.Image, count: int, seed: int, height_ratio: float = 0.62) -> None:
    rng = random.Random(seed)
    draw = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    margin = max(12, int(min(w, h) * 0.018))
    for _ in range(count):
        x = rng.randrange(margin, max(margin + 1, w - margin))
        y = rng.randrange(margin, max(margin + 1, int(h * height_ratio)))
        r = rng.choice((1, 1, 1, 2, 2)) * max(1, min(w, h) // 900)
        a = rng.randrange(35, 145)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, a))


def _draw_aurora(img: Image.Image, accent: tuple[int, int, int], seed: int) -> None:
    rng = random.Random(seed)
    w, h = img.size
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for ribbon in range(4):
        points = []
        base_y = h * (0.18 + ribbon * 0.08)
        amplitude = h * (0.045 + ribbon * 0.01)
        phase = rng.random() * math.pi * 2
        for x in range(-w // 10, w + w // 10, max(8, w // 80)):
            y = base_y + math.sin((x / w) * math.pi * 2.2 + phase) * amplitude
            y += math.sin((x / w) * math.pi * 5.5 + phase / 2) * amplitude * 0.25
            points.append((x, int(y)))
        width = max(18, int(min(w, h) * (0.025 + ribbon * 0.006)))
        color = _mix(accent, (181, 138, 255), ribbon / 5)
        draw.line(points, fill=(*color, 58), width=width)
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(max(18, min(w, h) // 28))))


def _draw_clouds(img: Image.Image, color: tuple[int, int, int], seed: int) -> None:
    rng = random.Random(seed)
    w, h = img.size
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for _ in range(18):
        x = rng.randint(-w // 8, w)
        y = rng.randint(int(h * 0.12), int(h * 0.62))
        rx = rng.randint(max(35, w // 18), max(45, w // 8))
        ry = rng.randint(max(14, h // 70), max(24, h // 28))
        draw.ellipse((x - rx, y - ry, x + rx, y + ry), fill=(*color, rng.randint(10, 28)))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(max(14, min(w, h) // 32))))


def _draw_scene(img: Image.Image, style: dict, seed: int) -> None:
    w, h = img.size
    scene = style["scene"]
    land = style["land"]
    accent = style["accent"]
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    horizon = int(h * (0.74 if h <= w else 0.72))

    if scene in {"mountains", "aurora", "noir"}:
        back = _mix(land, accent, 0.10 if scene != "noir" else 0.03)
        draw.polygon(
            [(0, horizon + h * 0.03), (w * 0.14, horizon - h * 0.08), (w * 0.27, horizon + h * 0.015),
             (w * 0.42, horizon - h * 0.13), (w * 0.58, horizon), (w * 0.72, horizon - h * 0.09),
             (w * 0.87, horizon + h * 0.025), (w, horizon - h * 0.045), (w, h), (0, h)],
            fill=(*back, 205),
        )
        draw.polygon(
            [(0, horizon + h * 0.12), (w * 0.20, horizon + h * 0.01), (w * 0.38, horizon + h * 0.11),
             (w * 0.61, horizon - h * 0.005), (w * 0.82, horizon + h * 0.10), (w, horizon + h * 0.04),
             (w, h), (0, h)],
            fill=(*land, 255),
        )
    elif scene == "dunes":
        draw.polygon(
            [(0, horizon + h * 0.05), (w * 0.22, horizon - h * 0.02), (w * 0.42, horizon + h * 0.07),
             (w * 0.67, horizon - h * 0.055), (w * 0.84, horizon + h * 0.045), (w, horizon - h * 0.01),
             (w, h), (0, h)],
            fill=(*_mix(land, accent, 0.10), 230),
        )
        draw.polygon(
            [(0, horizon + h * 0.13), (w * 0.27, horizon + h * 0.05), (w * 0.50, horizon + h * 0.15),
             (w * 0.76, horizon + h * 0.035), (w, horizon + h * 0.12), (w, h), (0, h)],
            fill=(*land, 255),
        )
    elif scene == "city":
        draw.rectangle((0, horizon, w, h), fill=(*land, 255))
        rng = random.Random(seed)
        x = 0
        while x < w:
            building_w = rng.randint(max(24, w // 42), max(42, w // 24))
            building_h = rng.randint(max(45, h // 12), max(90, h // 4))
            draw.rectangle((x, horizon - building_h, x + building_w, h), fill=(*land, 245))
            if rng.random() > 0.55:
                window_w = max(2, building_w // 8)
                for wx in range(x + window_w, x + building_w - window_w, window_w * 3):
                    for wy in range(horizon - building_h + window_w * 2, horizon - window_w, window_w * 3):
                        draw.rectangle((wx, wy, wx + window_w, wy + window_w), fill=(*accent, rng.randint(30, 85)))
            x += building_w + rng.randint(2, 7)
    elif scene == "ocean":
        draw.rectangle((0, horizon, w, h), fill=(*land, 235))
        for index in range(7):
            y = horizon + int((index + 1) * (h - horizon) / 9)
            alpha = max(12, 48 - index * 5)
            draw.arc((-w * 0.1, y - h * 0.03, w * 0.55, y + h * 0.04), 185, 350, fill=(*accent, alpha), width=max(2, min(w, h) // 360))
            draw.arc((w * 0.35, y - h * 0.02, w * 1.1, y + h * 0.05), 185, 350, fill=(255, 255, 255, alpha // 2), width=max(2, min(w, h) // 420))
    elif scene == "botanical":
        draw.rectangle((0, horizon + h * 0.04, w, h), fill=(*land, 248))
        rng = random.Random(seed)
        for side in (-1, 1):
            base_x = w * (0.08 if side < 0 else 0.92)
            for index in range(7):
                y = h * (0.16 + index * 0.105)
                length = w * rng.uniform(0.09, 0.18)
                end_x = base_x + side * length
                draw.line((base_x, h * 0.86, end_x, y), fill=(*accent, 45), width=max(3, min(w, h) // 230))
                leaf_r = max(10, min(w, h) // 38)
                draw.ellipse((end_x - leaf_r, y - leaf_r * 0.55, end_x + leaf_r, y + leaf_r * 0.55), fill=(*accent, 25))
    elif scene == "minimal":
        draw.rectangle((0, horizon + h * 0.04, w, h), fill=(*land, 205))
        for index in range(3):
            inset = int(min(w, h) * (0.045 + index * 0.028))
            draw.arc((inset, int(h * 0.10) + inset, w - inset, int(h * 0.92) - inset), 200, 340, fill=(*accent, 24), width=max(2, min(w, h) // 420))
    elif scene == "clouds":
        draw.polygon(
            [(0, horizon + h * 0.08), (w * 0.24, horizon + h * 0.01), (w * 0.48, horizon + h * 0.09),
             (w * 0.74, horizon - h * 0.015), (w, horizon + h * 0.07), (w, h), (0, h)],
            fill=(*land, 245),
        )
    elif scene == "cosmos":
        draw.polygon(
            [(0, horizon + h * 0.06), (w * 0.22, horizon - h * 0.03), (w * 0.47, horizon + h * 0.08),
             (w * 0.69, horizon - h * 0.02), (w, horizon + h * 0.05), (w, h), (0, h)],
            fill=(*land, 255),
        )
        ring = max(2, min(w, h) // 330)
        draw.ellipse((w * 0.67, h * 0.10, w * 0.92, h * 0.24), outline=(*accent, 34), width=ring)
        draw.ellipse((w * 0.69, h * 0.12, w * 0.90, h * 0.22), outline=(255, 255, 255, 18), width=ring)

    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(max(1, min(w, h) // 720))))


def _rounded_glass(
    base: Image.Image,
    box: tuple[int, int, int, int],
    tint_color: tuple[int, int, int],
    radius: int,
    light: bool = False,
) -> None:
    x1, y1, x2, y2 = box
    crop = base.crop(box).convert("RGBA")
    scale = min(0.30, 420 / max(crop.size))
    small_size = (max(48, int(crop.width * scale)), max(48, int(crop.height * scale)))
    small = crop.resize(small_size, Image.Resampling.BILINEAR)
    small = small.filter(ImageFilter.GaussianBlur(max(5, int(radius * scale * 0.55))))
    crop = small.resize(crop.size, Image.Resampling.BICUBIC)
    tint_alpha = 108 if light else 142
    crop = Image.alpha_composite(crop, Image.new("RGBA", crop.size, (*tint_color, tint_alpha)))
    mask = Image.new("L", crop.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, crop.width - 1, crop.height - 1), radius=radius, fill=255)
    base.paste(crop, (x1, y1), mask)

    border = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(border)
    border_alpha = 64 if light else 50
    draw.rounded_rectangle(box, radius=radius, outline=(255, 255, 255, border_alpha), width=max(1, radius // 18))
    draw.line((x1 + radius, y1 + 1, x2 - radius, y1 + 1), fill=(255, 255, 255, border_alpha + 18), width=max(1, radius // 18))
    base.alpha_composite(border)


def _fit_font(text: str, max_width: int, start_size: int, bold: bool, min_size: int = 16):
    size = max(start_size, min_size)
    while size > min_size:
        font = load_font(size, bold)
        box = font.getbbox(text)
        if box[2] - box[0] <= max_width:
            return font
        size -= max(1, size // 18)
    return load_font(min_size, bold)


def _text_center(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font,
    fill: tuple[int, int, int, int],
    width: int,
    shadow: bool = True,
) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    x = (width - (box[2] - box[0])) / 2
    if shadow:
        shadow_offset = max(2, font.size // 25) if hasattr(font, "size") else 3
        draw.text((x, y + shadow_offset), text, font=font, fill=(0, 0, 0, 92))
    draw.text((x, y), text, font=font, fill=fill)


def _add_vignette(img: Image.Image, strength: int = 80) -> Image.Image:
    w, h = img.size
    scale = min(0.25, 360 / max(w, h))
    sw, sh = max(64, int(w * scale)), max(64, int(h * scale))
    mask = Image.new("L", (sw, sh), 0)
    draw = ImageDraw.Draw(mask)
    inset = -int(min(sw, sh) * 0.16)
    draw.ellipse((inset, inset, sw - inset, sh - inset), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(max(sw, sh) // 7))
    mask = mask.resize((w, h), Image.Resampling.BICUBIC)
    darkness = Image.new("RGBA", img.size, (0, 0, 0, strength))
    darkness.putalpha(Image.eval(mask, lambda value: 255 - value))
    return Image.alpha_composite(img.convert("RGBA"), darkness)


def _add_grain(img: Image.Image, opacity: int = 5) -> Image.Image:
    w, h = img.size
    noise_size = (max(160, w // 3), max(160, h // 3))
    noise = Image.effect_noise(noise_size, 18).convert("L").resize((w, h), Image.Resampling.BILINEAR)
    alpha = Image.new("L", img.size, opacity)
    noise_rgba = Image.merge("RGBA", (noise, noise, noise, alpha))
    return Image.alpha_composite(img.convert("RGBA"), noise_rgba)


def _layout(size: tuple[int, int]) -> dict[str, int | tuple[int, int, int, int]]:
    w, h = size
    portrait = h > w * 1.15
    squareish = not portrait and h > w * 0.78
    margin_x = int(w * (0.065 if portrait else 0.072))
    margin_y = int(h * (0.055 if portrait else 0.082))
    card = (margin_x, margin_y, w - margin_x, h - margin_y)

    if portrait:
        return {
            "card": card,
            "eyebrow_y": int(h * 0.205),
            "rule_y": int(h * 0.245),
            "title_y": int(h * 0.285),
            "time_y": int(h * 0.390),
            "date_y": int(h * 0.610),
            "city_y": int(h * 0.705),
            "title_size": int(w * 0.064),
            "time_size": int(w * 0.205),
            "date_size": int(w * 0.046),
            "city_size": int(w * 0.038),
            "micro_size": int(w * 0.025),
        }
    if squareish:
        return {
            "card": card,
            "eyebrow_y": int(h * 0.175),
            "rule_y": int(h * 0.225),
            "title_y": int(h * 0.275),
            "time_y": int(h * 0.385),
            "date_y": int(h * 0.625),
            "city_y": int(h * 0.715),
            "title_size": int(w * 0.055),
            "time_size": int(w * 0.175),
            "date_size": int(w * 0.040),
            "city_size": int(w * 0.032),
            "micro_size": int(w * 0.022),
        }
    return {
        "card": card,
        "eyebrow_y": int(h * 0.155),
        "rule_y": int(h * 0.207),
        "title_y": int(h * 0.252),
        "time_y": int(h * 0.355),
        "date_y": int(h * 0.645),
        "city_y": int(h * 0.755),
        "title_size": int(h * 0.061),
        "time_size": int(h * 0.212),
        "date_size": int(h * 0.047),
        "city_size": int(h * 0.039),
        "micro_size": int(h * 0.029),
    }


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
    palette = STYLES[style]
    seed = _seed(style, publish_date, image_format)
    layout = _layout((w, h))

    img = _gradient(
        (w, h),
        [(0.0, palette["top"]), (0.55, palette["mid"]), (1.0, palette["bottom"])],
    ).convert("RGBA")

    sun_x = w // 2
    sun_y = int(h * (0.73 if h > w else 0.70))
    sun_radius = int(min(w, h) * (0.105 if h > w else 0.112))
    img.alpha_composite(_radial_glow((w, h), (sun_x, sun_y), sun_radius * 4, palette["sun"], 165))
    img.alpha_composite(
        _radial_glow(
            (w, h),
            (int(w * 0.16), int(h * 0.27)),
            int(min(w, h) * 0.38),
            palette["accent"],
            44,
        )
    )

    if palette["scene"] in {"cosmos", "city", "aurora", "noir"}:
        _draw_stars(img, 100 if palette["scene"] == "cosmos" else 44, seed)
    if palette["scene"] == "aurora":
        _draw_aurora(img, palette["accent"], seed)
    if palette["scene"] in {"clouds", "minimal"}:
        _draw_clouds(img, palette["sun"], seed)

    sun_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sun_draw = ImageDraw.Draw(sun_layer)
    sun_draw.ellipse(
        (sun_x - sun_radius, sun_y - sun_radius, sun_x + sun_radius, sun_y + sun_radius),
        fill=(*palette["sun"], 244),
    )
    img.alpha_composite(sun_layer.filter(ImageFilter.GaussianBlur(max(2, sun_radius // 35))))
    _draw_scene(img, palette, seed)
    img = _add_vignette(img, 78 if style != "ivory" else 46)

    card = layout["card"]
    radius = max(28, int(min(w, h) * 0.052))
    _rounded_glass(img, card, palette["glass"], radius, light=style == "ivory")
    draw = ImageDraw.Draw(img, "RGBA")

    safe_title = (title_text or "Заход солнца").strip()[:42]
    date_text = russian_date(publish_date, include_weekday=bool(show_weekday))
    city = short_location_name(location_name).upper()[:36]
    max_text_width = int((card[2] - card[0]) * 0.78)

    title_font = _fit_font(safe_title, max_text_width, int(layout["title_size"]), True, 22)
    time_font = _fit_font(sunset_time, max_text_width, int(layout["time_size"]), True, 54)
    date_font = _fit_font(date_text, max_text_width, int(layout["date_size"]), False, 20)
    city_font = _fit_font(f"•  {city}" if city else "", max_text_width, int(layout["city_size"]), True, 18)
    micro_font = load_font(int(layout["micro_size"]), False)

    eyebrow = "SUNSET  •  GOLDEN HOUR"
    _text_center(draw, eyebrow, int(layout["eyebrow_y"]), micro_font, (*palette["muted"], 205), w, shadow=False)

    rule_y = int(layout["rule_y"])
    rule_w = int(min(w, h) * 0.19)
    rule_h = max(3, int(min(w, h) * 0.004))
    draw.rounded_rectangle(
        (w // 2 - rule_w // 2, rule_y, w // 2 + rule_w // 2, rule_y + rule_h),
        radius=rule_h,
        fill=(*palette["accent"], 220),
    )

    _text_center(draw, safe_title, int(layout["title_y"]), title_font, (*palette["text"], 255), w)
    _text_center(draw, sunset_time, int(layout["time_y"]), time_font, (*palette["text"], 255), w)

    date_box = draw.textbbox((0, 0), date_text, font=date_font)
    date_w = date_box[2] - date_box[0]
    date_h = date_box[3] - date_box[1]
    pill_pad_x = max(22, int(min(w, h) * 0.032))
    pill_pad_y = max(11, int(min(w, h) * 0.015))
    date_y = int(layout["date_y"])
    pill = (
        w // 2 - date_w // 2 - pill_pad_x,
        date_y - pill_pad_y,
        w // 2 + date_w // 2 + pill_pad_x,
        date_y + date_h + pill_pad_y,
    )
    draw.rounded_rectangle(
        pill,
        radius=(pill[3] - pill[1]) // 2,
        fill=(*palette["glass"], 116),
        outline=(255, 255, 255, 38),
        width=max(1, min(w, h) // 650),
    )
    _text_center(draw, date_text, date_y, date_font, (*palette["muted"], 246), w, shadow=False)

    if show_city and city:
        _text_center(draw, f"•  {city}", int(layout["city_y"]), city_font, (*palette["muted"], 226), w, shadow=False)

    dot_radius = max(3, min(w, h) // 240)
    for x in (card[0] + radius, card[2] - radius):
        y = card[1] + radius
        draw.ellipse((x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius), fill=(*palette["accent"], 185))

    img = _add_grain(img, opacity=4)
    out = OUTPUT_DIR / (
        f"sunset_{style}_{image_format.replace(':', 'x')}_{datetime.now():%Y%m%d_%H%M%S}_{secrets.token_hex(3)}.png"
    )
    img.convert("RGB").save(out, format="PNG", optimize=True)
    return str(out)
