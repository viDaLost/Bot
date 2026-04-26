from datetime import datetime
from pathlib import Path
import math
import random

from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUTPUT_DIR = Path("generated")
OUTPUT_DIR.mkdir(exist_ok=True)

MONTHS_RU = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}

WEEKDAYS_RU = {
    0: "понедельник",
    1: "вторник",
    2: "среда",
    3: "четверг",
    4: "пятница",
    5: "суббота",
    6: "воскресенье",
}

STYLE_TITLES = {
    "classic": "Классический закат",
    "night": "Ночной минимализм",
    "eastern": "Восточный стиль",
    "biblical": "Библейский стиль",
    "fire": "Огненный стиль",
}


def load_font(size: int, bold: bool = False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def russian_date(date_text: str, include_weekday: bool = False) -> str:
    try:
        d = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return date_text

    base = f"{d.day} {MONTHS_RU[d.month]} {d.year}"
    if include_weekday:
        return f"{WEEKDAYS_RU[d.weekday()]}, {base}"
    return base


def short_location_name(location_name: str) -> str:
    return location_name.split(",")[0].strip()


def _vertical_gradient(w: int, h: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGB", (w, h), top)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def _draw_centered(draw: ImageDraw.ImageDraw, text: str, y: int, font, fill, width: int):
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    draw.text(((width - text_w) / 2, y), text, font=font, fill=fill)


def _draw_stars(draw: ImageDraw.ImageDraw, w: int, h: int, amount: int = 70):
    for _ in range(amount):
        x = random.randint(25, w - 25)
        y = random.randint(20, int(h * 0.42))
        s = random.choice([1, 1, 1, 2])
        draw.ellipse([x, y, x + s, y + s], fill=(255, 255, 255))


def _classic_background(w: int, h: int) -> Image.Image:
    img = _vertical_gradient(w, h, (22, 34, 87), (96, 39, 50))
    draw = ImageDraw.Draw(img)
    _draw_stars(draw, w, h, 55)
    sun_x, sun_y, r = w // 2, int(h * 0.72), 130
    for i in range(9, 0, -1):
        rad = r + i * 22
        draw.ellipse([sun_x - rad, sun_y - rad, sun_x + rad, sun_y + rad], outline=(255, 171, 76), width=2)
    draw.ellipse([sun_x - r, sun_y - r, sun_x + r, sun_y + r], fill=(255, 182, 70))
    draw.rectangle([0, int(h * 0.75), w, h], fill=(10, 18, 38))
    return img


def _night_background(w: int, h: int) -> Image.Image:
    img = _vertical_gradient(w, h, (5, 12, 38), (3, 7, 18))
    draw = ImageDraw.Draw(img)
    _draw_stars(draw, w, h, 115)
    draw.arc([170, 130, w - 170, h + 170], 195, 345, fill=(160, 181, 216), width=2)
    return img


def _eastern_background(w: int, h: int) -> Image.Image:
    img = _vertical_gradient(w, h, (37, 20, 76), (147, 63, 47))
    draw = ImageDraw.Draw(img)
    for i in range(12):
        x = int(w * (i / 11))
        draw.line([(x, h), (w // 2, int(h * 0.25))], fill=(255, 202, 122), width=1)
    draw.ellipse([w // 2 - 95, int(h * 0.68) - 95, w // 2 + 95, int(h * 0.68) + 95], fill=(248, 177, 79))
    draw.rectangle([0, int(h * 0.73), w, h], fill=(26, 17, 36))
    return img


def _biblical_background(w: int, h: int) -> Image.Image:
    img = _vertical_gradient(w, h, (29, 34, 54), (75, 59, 43))
    draw = ImageDraw.Draw(img)
    for i in range(7):
        y = int(h * 0.24) + i * 38
        draw.arc([110 - i * 8, y, w - 110 + i * 8, y + 330], 195, 345, fill=(201, 177, 124), width=2)
    draw.rectangle([0, int(h * 0.74), w, h], fill=(19, 24, 36))
    return img


def _fire_background(w: int, h: int) -> Image.Image:
    img = _vertical_gradient(w, h, (56, 16, 24), (16, 9, 13))
    draw = ImageDraw.Draw(img)
    for _ in range(42):
        x = random.randint(0, w)
        y = random.randint(int(h * 0.55), h)
        length = random.randint(80, 230)
        draw.line([(x, y), (x + random.randint(-60, 60), y - length)], fill=(255, 128, 55), width=random.randint(1, 3))
    draw.ellipse([w // 2 - 120, int(h * 0.71) - 120, w // 2 + 120, int(h * 0.71) + 120], fill=(255, 176, 65))
    draw.rectangle([0, int(h * 0.76), w, h], fill=(19, 10, 16))
    return img


def create_sunset_image(
    sunset_time: str,
    publish_date: str,
    style: str = "classic",
    title_text: str = "Заход солнца",
    location_name: str = "",
    show_city: bool = False,
    show_weekday: bool = False,
) -> str:
    w, h = 1200, 675
    style = style or "classic"

    builders = {
        "classic": _classic_background,
        "night": _night_background,
        "eastern": _eastern_background,
        "biblical": _biblical_background,
        "fire": _fire_background,
    }
    img = builders.get(style, _classic_background)(w, h).convert("RGBA")

    # Мягкое затемнение вокруг краёв.
    vignette = Image.new("L", (w, h), 0)
    vd = ImageDraw.Draw(vignette)
    vd.ellipse([-180, -120, w + 180, h + 190], fill=180)
    vignette = vignette.filter(ImageFilter.GaussianBlur(120))
    dark = Image.new("RGBA", (w, h), (0, 0, 0, 130))
    img = Image.composite(img, dark, vignette)

    panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    pd.rounded_rectangle(
        [110, 105, w - 110, h - 105],
        radius=42,
        fill=(5, 10, 24, 135),
        outline=(255, 255, 255, 70),
        width=2,
    )
    img = Image.alpha_composite(img, panel)
    draw = ImageDraw.Draw(img)

    title_font = load_font(58, True)
    time_font = load_font(126, True)
    date_font = load_font(42, False)
    small_font = load_font(30, False)

    _draw_centered(draw, title_text or "Заход солнца", 165, title_font, (255, 255, 255), w)
    _draw_centered(draw, sunset_time, 278, time_font, (255, 255, 255), w)

    date_line = russian_date(publish_date, include_weekday=bool(show_weekday))
    _draw_centered(draw, date_line, 445, date_font, (230, 236, 246), w)

    if show_city and location_name:
        _draw_centered(draw, short_location_name(location_name), 510, small_font, (216, 226, 240), w)

    path = OUTPUT_DIR / f"sunset_{random.randint(100000, 999999)}.png"
    img.convert("RGB").save(path, quality=95)
    return str(path)
