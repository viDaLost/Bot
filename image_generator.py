import math
import random
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# Директория для сохранения готовых изображений
OUTPUT_DIR = Path("generated")
OUTPUT_DIR.mkdir(exist_ok=True)

# Русские названия месяцев
MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}

# Русские названия дней недели
WEEKDAYS_RU = {
    0: "понедельник", 1: "вторник", 2: "среда",
    3: "четверг", 4: "пятница", 5: "суббота", 6: "воскресенье",
}

# Краткие русские названия дней недели
WEEKDAYS_RU_SHORT = {
    0: "Пн", 1: "Вт", 2: "Ср",
    3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс",
}

# Заголовки стилей (для отображения в боте)
STYLE_TITLES = {
    "modern": "Ambient Минимализм",
    "synth": "Synthwave Закат",
    "arctic": "Арктическое Сияние",
    "dune": "Золотая Пустыня",
    "void": "Космическая Глубина",
}


def load_font(size: int, bold: bool = False):
    """Пытается загрузить системный шрифт. Если не удается, загружает шрифт по умолчанию."""
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",  # Если файл лежит в папке проекта
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def russian_date(date_text: str, include_weekday: bool = False) -> str:
    """Преобразует дату формата YYYY-MM-DD в красивый русский текст."""
    try:
        d = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return date_text

    base = f"{d.day} {MONTHS_RU[d.month]} {d.year}"
    if include_weekday:
        return f"{WEEKDAYS_RU_SHORT[d.weekday()]}, {base}"
    return base


def short_location_name(location_name: str) -> str:
    """Извлекает короткое название локации (обычно город)."""
    return location_name.split(",")[0].strip()


# =======================================================================================
# --- УТИЛИТЫ ДЛЯ ГЕНЕРАЦИИ ГРАФИКИ ---
# =======================================================================================

def _create_color_blob(w: int, h: int, color: tuple, steps: int = 40):
    """Создает мягкое размытое пятно света."""
    # Создаем холст побольше, чтобы размытие было плавным
    scale = 1.5
    pw, ph = int(w * scale), int(h * scale)
    img = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    x, y, r = pw // 2, ph // 2, min(pw, ph) // 2
    
    # Рисуем концентрические круги с убывающей прозрачностью
    for i in range(steps, 0, -1):
        rad = r * (i / steps)
        # Альфа убывает нелинейно
        alpha = int(180 * math.pow(i / steps, 2))
        draw.ellipse([x - rad, y - rad, x + rad, y + rad], fill=color[:3] + (alpha,))
        
    return img.resize((w, h), Image.Resampling.LANCZOS)


def _draw_text_centered_with_shadow(draw: ImageDraw.ImageDraw, text: str, y: int, font, fill: tuple, width: int):
    """Рисует центрированный текст с мягкой тенью для идеальной читаемости."""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    x = (width - text_w) / 2
    
    # Мягкая тень
    draw.text((x + 2, y + 3), text, font=font, fill=(0, 0, 0, 150))
    # Основной текст
    draw.text((x, y), text, font=font, fill=fill)


def _add_texture_grain(img: Image.Image, intensity: float = 0.05) -> Image.Image:
    """Накладывает легкую текстуру зернистости (шума) поверх изображения."""
    img = img.convert("RGBA")
    noise = Image.effect_noise(img.size, int(intensity * 100)).convert("RGBA")
    # Ослабляем шум, делаем его чуть сероватым
    noise = ImageEnhance.Color(noise).enhance(0.1)
    return Image.blend(img, noise, intensity)


# =======================================================================================
# --- КОМПОЗИЦИИ ФОНОВ (AMBIENT BLobs) ---
# =======================================================================================

def _create_ambient_composition(w: int, h: int, palette: list, style_name: str) -> Image.Image:
    """Создает фон в стиле 'color blobs' на основе выбранной палитры."""
    # 1. Базовый очень темный фон
    bg_color = palette[0]
    img = Image.new("RGBA", (w, h), bg_color)
    
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    
    # 2. Создаем и позиционируем размытые пятна света
    # Пятно 1: Основное сияние закатного солнца (оранжевый/золотой)
    sun_size = int(w * 1.3)
    sun_blob = _create_color_blob(sun_size, sun_size, palette[1], steps=50)
    overlay.paste(sun_blob, (w // 2 - sun_size // 2, h - int(h * 0.65)), sun_blob)
    
    # Пятно 2: Дополнительный оттенок неба (холодный/темный)
    sky_size = int(w * 1.0)
    sky_blob = _create_color_blob(sky_size, sky_size, palette[2], steps=50)
    overlay.paste(sky_blob, (w // 2 - sky_size // 2, -int(h * 0.4)), sky_blob)

    # Пятно 3: Небольшой акцент сбоку
    accent_size = int(w * 0.6)
    accent_blob = _create_color_blob(accent_size, accent_size, palette[3], steps=40)
    overlay.paste(accent_blob, (-int(w * 0.1), int(h * 0.4)), accent_blob)
    
    img = Image.alpha_composite(img, overlay)
    
    # 3. Легкое виньетирование (затемнение по краям)
    vignette = Image.new("L", (w, h), 255)
    vd = ImageDraw.Draw(vignette)
    vd.ellipse([-150, -100, w + 150, h + 150], fill=160)
    vignette = vignette.filter(ImageFilter.GaussianBlur(120))
    dark = Image.new("RGBA", (w, h), (0, 0, 0, 110))
    img = Image.composite(img, dark, vignette)
    
    return img


# =======================================================================================
# --- СОЗДАНИЕ ГЛАВНОГО ИЗОБРАЖЕНИЯ ---
# =======================================================================================

def create_sunset_image(
    sunset_time: str,
    publish_date: str,
    style: str = "modern",
    title_text: str = "Заход солнца",
    location_name: str = "",
    show_city: bool = False,
    show_weekday: bool = False,
) -> str:
    w, h = 1200, 675
    style = style or "modern"

    # Палитры цветов для разных стилей
    # Формат: [Фон, Солнце, Небо, Акцент]
    palettes = {
        # Глубокий синий и теплый золотой (Минимализм)
        "modern": [(10, 12, 30), (255, 160, 60), (30, 60, 110), (255, 230, 180)],
        
        # Фиолетовый неон и ярко-розовый (Synthwave)
        "synth": [(20, 5, 35), (255, 50, 120), (80, 20, 150), (255, 180, 50)],
        
        # Иссиня-черный, бирюзовый и белый (Arctic)
        "arctic": [(2, 8, 20), (60, 200, 220), (10, 50, 90), (230, 245, 255)],
        
        # Глубокий песочный, оранжевый и бледно-розовый (Dune)
        "dune": [(35, 20, 10), (255, 120, 30), (160, 80, 130), (255, 210, 170)],
        
        # Почти черный, темно-красный и серый (Void)
        "void": [(5, 5, 10), (150, 30, 30), (30, 35, 50), (100, 100, 120)],
    }
    
    # 1. Генерируем базовый Ambient-фон
    palette = palettes.get(style, palettes["modern"])
    img = _create_ambient_composition(w, h, palette, style).convert("RGBA")

    # 2. Накладываем Glassmorphism панель (матовое стекло)
    # Позиция панели
    panel_box = (100, 100, w - 100, h - 100)
    x1, y1, x2, y2 = panel_box
    panel_w, panel_h = x2 - x1, y2 - y1
    radius = 40
    
    # 2.1. Извлекаем область фона под панелью и сильно размываем
    glass_bg = img.crop(panel_box)
    glass_bg = glass_bg.filter(ImageFilter.GaussianBlur(30))
    
    # 2.2. Добавляем затемняющий оттенок на "стекло"
    tint = Image.new("RGBA", (panel_w, panel_h), (10, 15, 30, 125))
    glass_bg = Image.alpha_composite(glass_bg.convert("RGBA"), tint)
    
    # 2.3. Создаем маску скругленных углов для вставки
    mask = Image.new("L", (panel_w, panel_h), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle((0, 0, panel_w, panel_h), radius=radius, fill=255)
    
    # 2.4. Вставляем "матовое стекло" обратно
    img.paste(glass_bg, (x1, y1), mask)
    
    # 2.5. Накладываем тонкую светлую рамку вокруг панели (блик)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    draw_overlay.rounded_rectangle(panel_box, radius=radius, outline=(255, 255, 255, 55), width=2)
    
    img = Image.alpha_composite(img, overlay)

    # 3. Отрисовка текста
    draw = ImageDraw.Draw(img)

    # Загрузка шрифтов
    title_font = load_font(48, True)
    time_font = load_font(136, True)
    date_font = load_font(40, False)
    city_font = load_font(32, False)

    # Отрисовка элементов текста
    # 3.1. Заголовок
    _draw_text_centered_with_shadow(draw, title_text or "Заход солнца", 160, title_font, (255, 255, 255), w)
    
    # 3.2. Время (главный акцент, делаем теплее)
    time_fill = (255, 245, 230) # Слегка золотистый
    if style == "arctic": time_fill = (230, 250, 255) # Холодный
    if style == "void": time_fill = (250, 220, 220) # Красный
    
    _draw_text_centered_with_shadow(draw, sunset_time, 245, time_font, time_fill, w)

    # 3.3. Дата
    date_line = russian_date(publish_date, include_weekday=bool(show_weekday))
    _draw_text_centered_with_shadow(draw, date_line, 425, date_font, (220, 230, 245), w)

    # 3.4. Город
    if show_city and location_name:
        _draw_text_centered_with_shadow(draw, short_location_name(location_name), 495, city_font, (180, 200, 230), w)

    # 4. Накладываем текстуру зернистости для "дорогого" вида
    img = _add_texture_grain(img, intensity=0.04)

    # 5. Сохранение файла
    path = OUTPUT_DIR / f"sunset_{random.randint(100000, 999999)}.png"
    img.convert("RGB").save(path, quality=95)
    return str(path)
