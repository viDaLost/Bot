from datetime import datetime
from pathlib import Path
import math
import random

from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUTPUT_DIR = Path("generated")
OUTPUT_DIR.mkdir(exist_ok=True)

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}

WEEKDAYS_RU = {
    0: "понедельник", 1: "вторник", 2: "среда",
    3: "четверг", 4: "пятница", 5: "суббота", 6: "воскресенье",
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


def _vertical_gradient(w: int, h: int, top: tuple, bottom: tuple) -> Image.Image:
    """Создает плавный линейный градиент."""
    img = Image.new("RGBA", (w, h), top)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b, 255))
    return img


def _draw_glowing_sphere(img: Image.Image, x: int, y: int, radius: int, core_color: tuple, glow_color: tuple, steps: int = 30):
    """Рисует сферу с мягким свечением."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Свечение
    for i in range(steps, 0, -1):
        r = radius + (i * 4)
        alpha = int(120 * (1 - i / steps))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=glow_color[:3] + (alpha,))
        
    # Ядро
    draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=core_color)
    return Image.alpha_composite(img, overlay)


def _draw_stars(img: Image.Image, w: int, h: int, amount: int = 70):
    """Рисует звезды разного размера с легким свечением."""
    draw = ImageDraw.Draw(img)
    for _ in range(amount):
        x = random.randint(10, w - 10)
        y = random.randint(10, int(h * 0.6))
        s = random.choice([1, 1, 2, 2, 3])
        alpha = random.randint(100, 255)
        draw.ellipse([x, y, x + s, y + s], fill=(255, 255, 255, alpha))


def _draw_text_with_shadow(draw: ImageDraw.ImageDraw, text: str, y: int, font, fill: tuple, width: int):
    """Рисует центрированный текст с красивой мягкой тенью для читаемости."""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    x = (width - text_w) / 2
    
    # Тень
    draw.text((x + 3, y + 4), text, font=font, fill=(0, 0, 0, 160))
    # Основной текст
    draw.text((x, y), text, font=font, fill=fill)


# --- Стили фонов ---

def _classic_background(w: int, h: int) -> Image.Image:
    img = _vertical_gradient(w, h, (32, 26, 74), (204, 85, 61))
    _draw_stars(img, w, h, 40)
    img = _draw_glowing_sphere(img, w // 2, int(h * 0.75), 110, (255, 230, 150, 255), (255, 140, 50))
    # Земля (горизонт)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, int(h * 0.75), w, h], fill=(15, 10, 28, 255))
    return img


def _night_background(w: int, h: int) -> Image.Image:
    img = _vertical_gradient(w, h, (10, 14, 40), (25, 45, 80))
    _draw_stars(img, w, h, 120)
    img = _draw_glowing_sphere(img, w // 2, int(h * 0.65), 90, (220, 235, 255, 255), (100, 150, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, int(h * 0.75), w, h], fill=(5, 8, 20, 255))
    return img


def _eastern_background(w: int, h: int) -> Image.Image:
    img = _vertical_gradient(w, h, (70, 20, 80), (220, 100, 50))
    img = _draw_glowing_sphere(img, w // 2, int(h * 0.70), 130, (255, 180, 80, 255), (255, 80, 100))
    draw = ImageDraw.Draw(img)
    # Стилизованные горы
    draw.polygon([(0, h), (w*0.2, h*0.6), (w*0.5, h), (0, h)], fill=(30, 15, 40, 255))
    draw.polygon([(w*0.3, h), (w*0.7, h*0.55), (w, h*0.8), (w, h)], fill=(40, 20, 50, 255))
    return img


def _biblical_background(w: int, h: int) -> Image.Image:
    img = _vertical_gradient(w, h, (40, 50, 70), (180, 140, 90))
    img = _draw_glowing_sphere(img, w // 2, int(h * 0.6), 140, (255, 240, 200, 255), (200, 150, 80))
    draw = ImageDraw.Draw(img)
    # Песчаные дюны
    draw.ellipse([-w*0.2, h*0.65, w*0.6, h*1.2], fill=(60, 45, 35, 255))
    draw.ellipse([w*0.3, h*0.7, w*1.2, h*1.3], fill=(45, 30, 25, 255))
    return img


def _fire_background(w: int, h: int) -> Image.Image:
    img = _vertical_gradient(w, h, (40, 5, 10), (120, 20, 0))
    _draw_stars(img, w, h, 30) # искры
    img = _draw_glowing_sphere(img, w // 2, int(h * 0.8), 160, (255, 200, 50, 255), (255, 50, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, int(h * 0.8), w, h], fill=(15, 0, 0, 255))
    return img


def apply_glassmorphism_panel(img: Image.Image, box: tuple, radius: int) -> Image.Image:
    """Создает современную стеклянную панель (эффект матового стекла) для текста."""
    x1, y1, x2, y2 = box
    
    # 1. Вырезаем кусок фона и сильно размываем его
    panel_bg = img.crop(box)
    panel_bg = panel_bg.filter(ImageFilter.GaussianBlur(25))
    
    # 2. Добавляем полупрозрачный темный оттенок на размытый фон
    tint = Image.new("RGBA", panel_bg.size, (15, 20, 40, 110))
    panel_bg = Image.alpha_composite(panel_bg.convert("RGBA"), tint)
    
    # 3. Создаем маску со скругленными углами для вставки
    mask = Image.new("L", panel_bg.size, 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle((0, 0, panel_bg.width, panel_bg.height), radius=radius, fill=255)
    
    # 4. Вставляем стеклянную панель обратно на картинку
    img.paste(panel_bg, (x1, y1), mask)
    
    # 5. Рисуем тонкую светлую рамку вокруг панели (эффект блика на стекле)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    draw_overlay.rounded_rectangle(box, radius=radius, outline=(255, 255, 255, 60), width=2)
    
    return Image.alpha_composite(img, overlay)


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
    
    # Генерируем базовый фон со свечениями
    img = builders.get(style, _classic_background)(w, h).convert("RGBA")

    # Рисуем стеклянную панель (Glassmorphism)
    panel_box = (100, 90, w - 100, h - 90)
    img = apply_glassmorphism_panel(img, panel_box, radius=40)

    # Подготовка к отрисовке текста
    draw = ImageDraw.Draw(img)

    title_font = load_font(52, True)
    time_font = load_font(136, True)
    date_font = load_font(42, False)
    small_font = load_font(32, False)

    # Отрисовка текста с тенями
    _draw_text_with_shadow(draw, title_text or "Заход солнца", 150, title_font, (255, 255, 255), w)
    
    # Время делаем слегка золотистым/теплым для большего стиля
    _draw_text_with_shadow(draw, sunset_time, 240, time_font, (255, 245, 230), w)

    date_line = russian_date(publish_date, include_weekday=bool(show_weekday))
    _draw_text_with_shadow(draw, date_line, 420, date_font, (220, 230, 245), w)

    if show_city and location_name:
        _draw_text_with_shadow(draw, short_location_name(location_name), 490, small_font, (190, 210, 230), w)

    path = OUTPUT_DIR / f"sunset_{random.randint(100000, 999999)}.png"
    img.convert("RGB").save(path, quality=95)
    return str(path)
