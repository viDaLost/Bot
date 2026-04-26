import asyncio
from datetime import datetime
from pathlib import Path
import shutil

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from geopy.geocoders import Nominatim
import pytz

from config import BOT_TOKEN, ADMIN_IDS, DATABASE_PATH
from database import (
    add_job,
    add_send_log,
    add_target,
    delete_job,
    delete_target,
    get_job_by_id,
    get_jobs,
    get_send_logs,
    get_target_by_id,
    get_targets,
    init_db,
    update_job_fields,
)
from image_generator import STYLE_TITLES, create_sunset_image, russian_date
from scheduler import (
    calculate_sunset_minus_hour,
    remove_scheduled_job,
    restore_jobs,
    schedule_single_job,
    scheduler,
)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
geocoder = Nominatim(user_agent="sunset_telegram_bot_pro")

TIMEZONES = [
    ("🇷🇺 Москва UTC+3", "Europe/Moscow"),
    ("🇳🇱 Амстердам", "Europe/Amsterdam"),
    ("🇩🇪 Берлин", "Europe/Berlin"),
    ("🇮🇱 Иерусалим", "Asia/Jerusalem"),
    ("🇺🇦 Киев", "Europe/Kyiv"),
    ("UTC", "UTC"),
    ("UTC+1", "Etc/GMT-1"),
    ("UTC+2", "Etc/GMT-2"),
    ("UTC+3", "Etc/GMT-3"),
    ("UTC+4", "Etc/GMT-4"),
    ("UTC+5", "Etc/GMT-5"),
]

WEEKDAYS = [
    ("Пн", "monday"),
    ("Вт", "tuesday"),
    ("Ср", "wednesday"),
    ("Чт", "thursday"),
    ("Пт", "friday"),
    ("Сб", "saturday"),
    ("Вс", "sunday"),
]

WEEKDAY_FULL = {
    "monday": "понедельник",
    "tuesday": "вторник",
    "wednesday": "среда",
    "thursday": "четверг",
    "friday": "пятница",
    "saturday": "суббота",
    "sunday": "воскресенье",
}

TITLE_PRESETS = [
    "Заход солнца",
    "Время перед закатом",
    "До захода солнца",
    "Вечернее время",
]


class AddTargetState(StatesGroup):
    waiting_chat_id = State()
    waiting_title = State()


class CreateJobState(StatesGroup):
    choosing_target = State()
    choosing_location = State()
    choosing_timezone = State()
    choosing_schedule_type = State()
    waiting_date = State()
    choosing_weekdays = State()
    waiting_month_day = State()
    waiting_time = State()
    choosing_style = State()
    choosing_title = State()
    choosing_text_options = State()
    preview = State()


class EditJobState(StatesGroup):
    waiting_time = State()
    waiting_title = State()
    choosing_style = State()


class ImportBackupState(StatesGroup):
    waiting_file = State()


def is_admin(user_id: int) -> bool:
    return not ADMIN_IDS or user_id in ADMIN_IDS


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Расписания", callback_data="schedules_menu")],
        [InlineKeyboardButton(text="📢 Каналы и чаты", callback_data="targets_menu")],
        [InlineKeyboardButton(text="🕘 История отправок", callback_data="logs")],
        [InlineKeyboardButton(text="💾 Резервная копия", callback_data="backup_menu")],
        [InlineKeyboardButton(text="ℹ️ Инструкция", callback_data="help")],
    ])


def back_to_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Главное меню", callback_data="menu")]])


def targets_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить канал/чат", callback_data="add_target")],
        [InlineKeyboardButton(text="📋 Список каналов/чатов", callback_data="targets_list")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="menu")],
    ])


def schedules_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать расписание", callback_data="create_job")],
        [InlineKeyboardButton(text="📋 Активные и сохранённые", callback_data="jobs_list")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="menu")],
    ])


def backup_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Экспорт bot.db", callback_data="backup_export")],
        [InlineKeyboardButton(text="📥 Импорт bot.db", callback_data="backup_import")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="menu")],
    ])


def timezone_keyboard(auto_tz: str | None = None):
    rows = []
    if auto_tz:
        rows.append([InlineKeyboardButton(text=f"✅ Использовать {auto_tz}", callback_data=f"tz_{auto_tz}")])
        rows.append([InlineKeyboardButton(text="🔧 Выбрать другой", callback_data="tz_manual")])
    else:
        for text, tz in TIMEZONES:
            rows.append([InlineKeyboardButton(text=text, callback_data=f"tz_{tz}")])
    rows.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def schedule_type_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Один раз", callback_data="schedule_once")],
        [InlineKeyboardButton(text="🔁 Каждый день", callback_data="schedule_daily")],
        [InlineKeyboardButton(text="🗓 По дням недели", callback_data="schedule_weekly")],
        [InlineKeyboardButton(text="📆 Каждый месяц", callback_data="schedule_monthly")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="menu")],
    ])


def weekday_keyboard(selected: set[str]):
    rows = []
    row = []
    for title, key in WEEKDAYS:
        mark = "✅" if key in selected else "⬜"
        row.append(InlineKeyboardButton(text=f"{mark} {title}", callback_data=f"weekday_toggle_{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="➡️ Продолжить", callback_data="weekday_done")])
    rows.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def style_keyboard(prefix: str = "style"):
    rows = []
    for key, label in STYLE_TITLES.items():
        rows.append([InlineKeyboardButton(text=label, callback_data=f"{prefix}_{key}")])
    rows.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def title_keyboard():
    rows = [[InlineKeyboardButton(text=t, callback_data=f"title_{i}")] for i, t in enumerate(TITLE_PRESETS)]
    rows.append([InlineKeyboardButton(text="✏️ Свой заголовок", callback_data="title_custom")])
    rows.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def text_options_keyboard(show_city: bool, show_weekday: bool):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=("✅" if show_city else "⬜") + " Показывать город", callback_data="opt_city")],
        [InlineKeyboardButton(text=("✅" if show_weekday else "⬜") + " Показывать день недели", callback_data="opt_weekday")],
        [InlineKeyboardButton(text="🖼 Предпросмотр", callback_data="opt_preview")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="menu")],
    ])


def preview_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Сохранить расписание", callback_data="save_job")],
        [InlineKeyboardButton(text="✏️ Изменить стиль", callback_data="preview_change_style")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="menu")],
    ])


def auto_timezone_from_address(address: str) -> str | None:
    low = address.lower()
    rules = [
        ("россия", "Europe/Moscow"),
        ("russia", "Europe/Moscow"),
        ("нидерланды", "Europe/Amsterdam"),
        ("netherlands", "Europe/Amsterdam"),
        ("nederland", "Europe/Amsterdam"),
        ("германия", "Europe/Berlin"),
        ("germany", "Europe/Berlin"),
        ("deutschland", "Europe/Berlin"),
        ("израиль", "Asia/Jerusalem"),
        ("israel", "Asia/Jerusalem"),
        ("украина", "Europe/Kyiv"),
        ("ukraine", "Europe/Kyiv"),
    ]
    for needle, tz in rules:
        if needle in low:
            return tz
    return None


def format_schedule_line(job) -> str:
    kind = job["schedule_type"]
    if kind == "once":
        return f"один раз: {russian_date(job['publish_date'])} в {job['publish_time']}"
    if kind == "daily":
        return f"каждый день в {job['publish_time']}"
    if kind == "weekly":
        days = [WEEKDAY_FULL.get(x, x) for x in (job["weekdays"] or "").split(",") if x]
        return f"по дням: {', '.join(days)} в {job['publish_time']}"
    if kind == "monthly":
        return f"каждый месяц, {job['month_day']} числа в {job['publish_time']}"
    return f"{kind} {job['publish_time']}"


def validate_time_text(text: str) -> bool:
    try:
        datetime.strptime(text, "%H:%M")
        return True
    except ValueError:
        return False


def validate_future_once(publish_date: str, publish_time: str, timezone: str) -> bool:
    tz = pytz.timezone(timezone)
    run_dt = tz.localize(datetime.strptime(f"{publish_date} {publish_time}", "%Y-%m-%d %H:%M"))
    return run_dt > datetime.now(tz)


async def send_creation_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    schedule_type = data.get("schedule_type", "once")
    target_date = data.get("publish_date")
    if schedule_type != "once":
        target_date = datetime.now(pytz.timezone(data["timezone"])).strftime("%Y-%m-%d")

    sunset_time = calculate_sunset_minus_hour(
        data["location_name"],
        data["latitude"],
        data["longitude"],
        data["timezone"],
        target_date,
    )
    image_path = create_sunset_image(
        sunset_time=sunset_time,
        publish_date=target_date,
        style=data.get("image_style", "classic"),
        title_text=data.get("title_text", "Заход солнца"),
        location_name=data["location_name"],
        show_city=bool(data.get("show_city", False)),
        show_weekday=bool(data.get("show_weekday", False)),
    )

    await message.answer_photo(FSInputFile(image_path))
    await message.answer(
        "Так будет выглядеть картинка. Сохранить расписание?",
        reply_markup=preview_keyboard(),
    )
    await state.set_state(CreateJobState.preview)


async def schedule_or_reschedule(job_id: int, owner_id: int):
    job = await get_job_by_id(job_id, owner_id)
    if job:
        schedule_single_job(bot, job)


@dp.message(CommandStart())
async def start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к управлению ботом.")
        return
    await message.answer(
        "🌅 <b>Бот публикации времени захода солнца</b>\n\n"
        "Управление каналами, расписаниями, предпросмотром и историей отправок.",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )


@dp.message(Command("menu"))
async def menu_command(message: Message, state: FSMContext):
    if is_admin(message.from_user.id):
        await state.clear()
        await message.answer("Главное меню:", reply_markup=main_menu())


@dp.callback_query(F.data == "menu")
async def menu_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu())
    await callback.answer()


@dp.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "ℹ️ <b>Инструкция</b>\n\n"
        "1. Добавьте бота в канал или чат.\n"
        "2. Сделайте бота администратором канала.\n"
        "3. Откройте «Каналы и чаты» и добавьте канал через @username или -100... ID.\n"
        "4. Откройте «Расписания» и создайте отправку.\n\n"
        "В канал бот отправляет только картинку, без подписи.\n"
        "Поддерживаются: один раз, ежедневно, по выбранным дням недели и ежемесячно.",
        reply_markup=back_to_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


# ---------- Каналы и чаты ----------

@dp.callback_query(F.data == "targets_menu")
async def targets_menu(callback: CallbackQuery):
    await callback.message.edit_text("📢 <b>Каналы и чаты</b>", reply_markup=targets_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "add_target")
async def add_target_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddTargetState.waiting_chat_id)
    await callback.message.edit_text(
        "Отправьте ID канала/чата.\n\n"
        "Примеры:\n<code>@my_channel</code>\n<code>-1001234567890</code>",
        reply_markup=back_to_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(AddTargetState.waiting_chat_id)
async def add_target_chat_id(message: Message, state: FSMContext):
    await state.update_data(chat_id=message.text.strip())
    await state.set_state(AddTargetState.waiting_title)
    await message.answer("Теперь отправьте название, например: <b>Основной канал</b>", parse_mode="HTML")


@dp.message(AddTargetState.waiting_title)
async def add_target_title(message: Message, state: FSMContext):
    data = await state.get_data()
    await add_target(message.from_user.id, data["chat_id"], message.text.strip())
    await state.clear()
    await message.answer("✅ Канал/чат добавлен.", reply_markup=targets_menu_keyboard())


@dp.callback_query(F.data == "targets_list")
async def targets_list(callback: CallbackQuery):
    targets = await get_targets(callback.from_user.id)
    if not targets:
        await callback.message.edit_text("Каналы и чаты ещё не добавлены.", reply_markup=targets_menu_keyboard())
        await callback.answer()
        return

    text = "📋 <b>Каналы и чаты</b>\n\n"
    rows = []
    for target in targets:
        text += f"<b>ID {target['id']}</b> — {target['title']}\n<code>{target['chat_id']}</code>\n\n"
        rows.append([
            InlineKeyboardButton(text=f"🧪 Проверить {target['id']}", callback_data=f"target_check_{target['id']}"),
            InlineKeyboardButton(text=f"🗑 Удалить {target['id']}", callback_data=f"target_delete_{target['id']}"),
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="targets_menu")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("target_check_"))
async def target_check(callback: CallbackQuery):
    target_id = int(callback.data.replace("target_check_", ""))
    target = await get_target_by_id(target_id)
    if not target:
        await callback.answer("Канал/чат не найден", show_alert=True)
        return
    try:
        chat = await bot.get_chat(target["chat_id"])
        await callback.answer("✅ Доступ есть", show_alert=True)
        await callback.message.answer(f"✅ Бот видит канал/чат: <b>{getattr(chat, 'title', None) or getattr(chat, 'full_name', None) or chat.id}</b>", parse_mode="HTML")
    except Exception as e:
        await callback.answer("❌ Нет доступа", show_alert=True)
        await callback.message.answer(
            "❌ Бот не смог получить доступ к каналу/чату.\n\n"
            "Проверь, что бот добавлен в канал и является администратором.\n"
            f"Ошибка: <code>{str(e)[:700]}</code>",
            parse_mode="HTML",
        )


@dp.callback_query(F.data.startswith("target_delete_"))
async def target_delete(callback: CallbackQuery):
    target_id = int(callback.data.replace("target_delete_", ""))
    await delete_target(target_id, callback.from_user.id)
    await callback.message.edit_text("🗑 Канал/чат и связанные расписания удалены.", reply_markup=targets_menu_keyboard())
    await callback.answer()


# ---------- Расписания ----------

@dp.callback_query(F.data == "schedules_menu")
async def schedules_menu(callback: CallbackQuery):
    await callback.message.edit_text("📅 <b>Расписания</b>", reply_markup=schedules_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "create_job")
async def create_job_start(callback: CallbackQuery, state: FSMContext):
    targets = await get_targets(callback.from_user.id)
    if not targets:
        await callback.message.edit_text("Сначала добавьте хотя бы один канал/чат.", reply_markup=targets_menu_keyboard())
        await callback.answer()
        return

    rows = [[InlineKeyboardButton(text=f"📢 {t['title']}", callback_data=f"target_{t['id']}")] for t in targets]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="schedules_menu")])
    await state.set_state(CreateJobState.choosing_target)
    await callback.message.edit_text("Выберите, куда отправлять картинку:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@dp.callback_query(F.data.regexp(r"^target_\d+$"))
async def choose_target(callback: CallbackQuery, state: FSMContext):
    if not callback.data.replace("target_", "").isdigit():
        return
    await state.update_data(target_id=int(callback.data.replace("target_", "")))
    await state.set_state(CreateJobState.choosing_location)
    await callback.message.edit_text(
        "📍 Отправьте город или локацию.\n\n"
        "Например: <code>Ессентуки</code>, <code>Москва</code>, <code>Amsterdam</code>",
        reply_markup=back_to_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(CreateJobState.choosing_location)
async def search_location(message: Message, state: FSMContext):
    query = message.text.strip()
    try:
        results = geocoder.geocode(query, language="ru", exactly_one=False, limit=5, timeout=10)
    except Exception:
        results = None

    if not results:
        await message.answer("Не удалось найти локацию. Попробуйте написать город и страну точнее.")
        return

    candidates = []
    rows = []
    for i, loc in enumerate(results[:5]):
        candidates.append({
            "address": loc.address,
            "latitude": loc.latitude,
            "longitude": loc.longitude,
        })
        short = loc.address[:55] + ("..." if len(loc.address) > 55 else "")
        rows.append([InlineKeyboardButton(text=short, callback_data=f"loc_{i}")])
    rows.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="menu")])

    await state.update_data(location_candidates=candidates)
    await message.answer("Выберите найденную локацию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("loc_"))
async def choose_location(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.replace("loc_", ""))
    data = await state.get_data()
    candidates = data.get("location_candidates", [])
    if index >= len(candidates):
        await callback.answer("Локация не найдена", show_alert=True)
        return

    loc = candidates[index]
    auto_tz = auto_timezone_from_address(loc["address"])
    await state.update_data(
        location_name=loc["address"],
        latitude=loc["latitude"],
        longitude=loc["longitude"],
    )
    await state.set_state(CreateJobState.choosing_timezone)
    await callback.message.edit_text(
        f"✅ Локация:\n<b>{loc['address']}</b>\n\n"
        "Выберите часовой пояс:",
        reply_markup=timezone_keyboard(auto_tz),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data == "tz_manual")
async def timezone_manual(callback: CallbackQuery):
    await callback.message.edit_text("Выберите часовой пояс:", reply_markup=timezone_keyboard(None))
    await callback.answer()


@dp.callback_query(F.data.startswith("tz_"))
async def choose_timezone(callback: CallbackQuery, state: FSMContext):
    timezone = callback.data.replace("tz_", "")
    await state.update_data(timezone=timezone)
    await state.set_state(CreateJobState.choosing_schedule_type)
    await callback.message.edit_text(
        f"✅ Часовой пояс: <code>{timezone}</code>\n\nВыберите тип расписания:",
        reply_markup=schedule_type_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data == "schedule_once")
async def schedule_once(callback: CallbackQuery, state: FSMContext):
    await state.update_data(schedule_type="once")
    await state.set_state(CreateJobState.waiting_date)
    await callback.message.edit_text(
        "📅 Отправьте дату в формате <code>2026-05-01</code>.",
        reply_markup=back_to_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data == "schedule_daily")
async def schedule_daily(callback: CallbackQuery, state: FSMContext):
    await state.update_data(schedule_type="daily", publish_date=None, weekdays="", month_day=None)
    await state.set_state(CreateJobState.waiting_time)
    await callback.message.edit_text("🕒 Отправьте время публикации: <code>18:30</code>", reply_markup=back_to_menu(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "schedule_weekly")
async def schedule_weekly(callback: CallbackQuery, state: FSMContext):
    await state.update_data(schedule_type="weekly", selected_weekdays=[])
    await state.set_state(CreateJobState.choosing_weekdays)
    await callback.message.edit_text(
        "Выберите один или несколько дней недели:",
        reply_markup=weekday_keyboard(set()),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("weekday_toggle_"))
async def weekday_toggle(callback: CallbackQuery, state: FSMContext):
    day = callback.data.replace("weekday_toggle_", "")
    data = await state.get_data()
    selected = set(data.get("selected_weekdays", []))
    if day in selected:
        selected.remove(day)
    else:
        selected.add(day)
    await state.update_data(selected_weekdays=list(selected))
    await callback.message.edit_reply_markup(reply_markup=weekday_keyboard(selected))
    await callback.answer()


@dp.callback_query(F.data == "weekday_done")
async def weekday_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_weekdays", [])
    if not selected:
        await callback.answer("Выберите хотя бы один день", show_alert=True)
        return
    ordered = [key for _, key in WEEKDAYS if key in selected]
    await state.update_data(weekdays=",".join(ordered))
    await state.set_state(CreateJobState.waiting_time)
    await callback.message.edit_text("🕒 Отправьте время публикации: <code>18:30</code>", reply_markup=back_to_menu(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "schedule_monthly")
async def schedule_monthly(callback: CallbackQuery, state: FSMContext):
    await state.update_data(schedule_type="monthly")
    await state.set_state(CreateJobState.waiting_month_day)
    await callback.message.edit_text(
        "📆 Напишите число месяца от 1 до 31.\n\nНапример: <code>15</code>",
        reply_markup=back_to_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(CreateJobState.waiting_date)
async def set_date(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        await message.answer("Дата должна быть в формате <code>ГГГГ-ММ-ДД</code>.", parse_mode="HTML")
        return
    await state.update_data(publish_date=text)
    await state.set_state(CreateJobState.waiting_time)
    await message.answer("🕒 Теперь отправьте время публикации: <code>18:30</code>", parse_mode="HTML")


@dp.message(CreateJobState.waiting_month_day)
async def set_month_day(message: Message, state: FSMContext):
    try:
        day = int(message.text.strip())
    except ValueError:
        await message.answer("Нужно число от 1 до 31.")
        return
    if day < 1 or day > 31:
        await message.answer("Число месяца должно быть от 1 до 31.")
        return
    await state.update_data(month_day=day, publish_date=None, weekdays="")
    await state.set_state(CreateJobState.waiting_time)
    await message.answer("🕒 Теперь отправьте время публикации: <code>18:30</code>", parse_mode="HTML")


@dp.message(CreateJobState.waiting_time)
async def set_time(message: Message, state: FSMContext):
    text = message.text.strip()
    if not validate_time_text(text):
        await message.answer("Время должно быть в формате <code>ЧЧ:ММ</code>, например <code>18:30</code>.", parse_mode="HTML")
        return

    data = await state.get_data()
    if data.get("schedule_type") == "once":
        if not validate_future_once(data["publish_date"], text, data["timezone"]):
            await message.answer("Эта дата и время уже прошли для выбранного часового пояса. Укажите будущее время.")
            return

    await state.update_data(publish_time=text)
    await state.set_state(CreateJobState.choosing_style)
    await message.answer("🎨 Выберите стиль картинки:", reply_markup=style_keyboard("style"))


@dp.callback_query(F.data.startswith("style_"))
async def choose_style(callback: CallbackQuery, state: FSMContext):
    style = callback.data.replace("style_", "")
    await state.update_data(image_style=style)
    await state.set_state(CreateJobState.choosing_title)
    await callback.message.edit_text("Выберите заголовок на картинке:", reply_markup=title_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("title_"))
async def choose_title(callback: CallbackQuery, state: FSMContext):
    value = callback.data.replace("title_", "")
    if value == "custom":
        await state.set_state(EditJobState.waiting_title)
        await state.update_data(custom_title_for_creation=True)
        await callback.message.edit_text("Напишите свой заголовок для картинки:", reply_markup=back_to_menu())
        await callback.answer()
        return
    title = TITLE_PRESETS[int(value)]
    await state.update_data(title_text=title, show_city=False, show_weekday=False)
    await state.set_state(CreateJobState.choosing_text_options)
    await callback.message.edit_text(
        "Настройте дополнительные элементы на картинке:",
        reply_markup=text_options_keyboard(False, False),
    )
    await callback.answer()


@dp.message(EditJobState.waiting_title)
async def title_text_input(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("custom_title_for_creation"):
        await state.update_data(title_text=message.text.strip()[:40], show_city=False, show_weekday=False, custom_title_for_creation=False)
        await state.set_state(CreateJobState.choosing_text_options)
        await message.answer("Настройте дополнительные элементы на картинке:", reply_markup=text_options_keyboard(False, False))
        return

    job_id = data.get("edit_job_id")
    if job_id:
        await update_job_fields(job_id, message.from_user.id, title_text=message.text.strip()[:40])
        await schedule_or_reschedule(job_id, message.from_user.id)
        await state.clear()
        await message.answer("✅ Заголовок изменён.", reply_markup=schedules_menu_keyboard())


@dp.callback_query(F.data == "opt_city")
async def opt_city(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    new_value = not bool(data.get("show_city", False))
    await state.update_data(show_city=new_value)
    await callback.message.edit_reply_markup(reply_markup=text_options_keyboard(new_value, bool(data.get("show_weekday", False))))
    await callback.answer()


@dp.callback_query(F.data == "opt_weekday")
async def opt_weekday(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    new_value = not bool(data.get("show_weekday", False))
    await state.update_data(show_weekday=new_value)
    await callback.message.edit_reply_markup(reply_markup=text_options_keyboard(bool(data.get("show_city", False)), new_value))
    await callback.answer()


@dp.callback_query(F.data == "opt_preview")
async def opt_preview(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await send_creation_preview(callback.message, state)


@dp.callback_query(F.data == "preview_change_style")
async def preview_change_style(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CreateJobState.choosing_style)
    await callback.message.edit_text("🎨 Выберите стиль картинки:", reply_markup=style_keyboard("style"))
    await callback.answer()


@dp.callback_query(F.data == "save_job")
async def save_job(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    target = await get_target_by_id(data["target_id"])
    if not target:
        await callback.answer("Канал/чат не найден", show_alert=True)
        return

    job_id = await add_job(
        owner_id=callback.from_user.id,
        target_id=data["target_id"],
        location_name=data["location_name"],
        latitude=data["latitude"],
        longitude=data["longitude"],
        timezone=data["timezone"],
        publish_time=data["publish_time"],
        schedule_type=data.get("schedule_type", "once"),
        publish_date=data.get("publish_date"),
        weekdays=data.get("weekdays", ""),
        month_day=data.get("month_day"),
        image_style=data.get("image_style", "classic"),
        title_text=data.get("title_text", "Заход солнца"),
        show_city=1 if data.get("show_city") else 0,
        show_weekday=1 if data.get("show_weekday") else 0,
    )
    await schedule_or_reschedule(job_id, callback.from_user.id)
    job = await get_job_by_id(job_id, callback.from_user.id)
    await state.clear()
    await callback.message.edit_text(
        "✅ <b>Расписание сохранено</b>\n\n"
        f"ID: <b>{job_id}</b>\n"
        f"Куда: <b>{target['title']}</b>\n"
        f"Локация: <b>{data['location_name']}</b>\n"
        f"Расписание: <b>{format_schedule_line(job)}</b>",
        reply_markup=schedules_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data == "jobs_list")
async def jobs_list(callback: CallbackQuery):
    jobs = await get_jobs(callback.from_user.id)
    if not jobs:
        await callback.message.edit_text("Расписаний пока нет.", reply_markup=schedules_menu_keyboard())
        await callback.answer()
        return

    text = "📋 <b>Расписания</b>\n\n"
    rows = []
    for job in jobs[:20]:
        icon = "🟢" if job["status"] == "active" else "⏸" if job["status"] == "paused" else "⚪"
        text += (
            f"{icon} <b>ID {job['id']}</b> — {job['target_title']}\n"
            f"📍 {job['location_name'].split(',')[0]}\n"
            f"🕒 {format_schedule_line(job)}\n"
            f"🎨 {STYLE_TITLES.get(job['image_style'], job['image_style'])}\n\n"
        )
        rows.append([InlineKeyboardButton(text=f"⚙️ Управлять ID {job['id']}", callback_data=f"job_manage_{job['id']}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="schedules_menu")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("job_manage_"))
async def job_manage(callback: CallbackQuery):
    job_id = int(callback.data.replace("job_manage_", ""))
    job = await get_job_by_id(job_id, callback.from_user.id)
    if not job:
        await callback.answer("Расписание не найдено", show_alert=True)
        return

    pause_text = "⏸ Пауза" if job["status"] == "active" else "▶️ Возобновить"
    rows = [
        [InlineKeyboardButton(text="🖼 Предпросмотр", callback_data=f"job_preview_{job_id}")],
        [InlineKeyboardButton(text="🧪 Тест в канал сейчас", callback_data=f"job_test_{job_id}")],
        [InlineKeyboardButton(text="✏️ Изменить время", callback_data=f"job_edit_time_{job_id}")],
        [InlineKeyboardButton(text="🎨 Изменить стиль", callback_data=f"job_edit_style_{job_id}")],
        [InlineKeyboardButton(text="🔤 Изменить заголовок", callback_data=f"job_edit_title_{job_id}")],
        [InlineKeyboardButton(text=pause_text, callback_data=f"job_toggle_{job_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"job_delete_{job_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="jobs_list")],
    ]
    await callback.message.edit_text(
        f"⚙️ <b>Расписание ID {job_id}</b>\n\n"
        f"Канал/чат: <b>{job['target_title']}</b>\n"
        f"Локация: <b>{job['location_name']}</b>\n"
        f"Расписание: <b>{format_schedule_line(job)}</b>\n"
        f"Статус: <b>{job['status']}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )
    await callback.answer()


async def make_job_image(job):
    target_date = job["publish_date"] if job["schedule_type"] == "once" else datetime.now(pytz.timezone(job["timezone"])).strftime("%Y-%m-%d")
    sunset_time = calculate_sunset_minus_hour(job["location_name"], job["latitude"], job["longitude"], job["timezone"], target_date)
    return create_sunset_image(
        sunset_time=sunset_time,
        publish_date=target_date,
        style=job["image_style"],
        title_text=job["title_text"],
        location_name=job["location_name"],
        show_city=bool(job["show_city"]),
        show_weekday=bool(job["show_weekday"]),
    ), target_date, sunset_time


@dp.callback_query(F.data.startswith("job_preview_"))
async def job_preview(callback: CallbackQuery):
    job_id = int(callback.data.replace("job_preview_", ""))
    job = await get_job_by_id(job_id, callback.from_user.id)
    if not job:
        await callback.answer("Расписание не найдено", show_alert=True)
        return
    image_path, _, _ = await make_job_image(job)
    await callback.message.answer_photo(FSInputFile(image_path))
    await callback.answer()


@dp.callback_query(F.data.startswith("job_test_"))
async def job_test(callback: CallbackQuery):
    job_id = int(callback.data.replace("job_test_", ""))
    job = await get_job_by_id(job_id, callback.from_user.id)
    if not job:
        await callback.answer("Расписание не найдено", show_alert=True)
        return
    try:
        image_path, target_date, sunset_time = await make_job_image(job)
        await bot.send_photo(chat_id=job["chat_id"], photo=FSInputFile(image_path))
        await add_send_log(job_id, callback.from_user.id, job["target_id"], "success", target_date, sunset_time)
        await callback.answer("✅ Тестовая картинка отправлена", show_alert=True)
    except Exception as e:
        await add_send_log(job_id, callback.from_user.id, job["target_id"], "error", "", "", str(e)[:900])
        await callback.answer("❌ Ошибка отправки", show_alert=True)
        await callback.message.answer(f"❌ Ошибка тестовой отправки:\n<code>{str(e)[:900]}</code>", parse_mode="HTML")


@dp.callback_query(F.data.startswith("job_toggle_"))
async def job_toggle(callback: CallbackQuery):
    job_id = int(callback.data.replace("job_toggle_", ""))
    job = await get_job_by_id(job_id, callback.from_user.id)
    if not job:
        await callback.answer("Расписание не найдено", show_alert=True)
        return
    new_status = "paused" if job["status"] == "active" else "active"
    await update_job_fields(job_id, callback.from_user.id, status=new_status)
    if new_status == "paused":
        remove_scheduled_job(job_id)
    else:
        await schedule_or_reschedule(job_id, callback.from_user.id)
    await callback.message.edit_text(f"✅ Новый статус: <b>{new_status}</b>", reply_markup=schedules_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("job_delete_"))
async def job_delete(callback: CallbackQuery):
    job_id = int(callback.data.replace("job_delete_", ""))
    remove_scheduled_job(job_id)
    await delete_job(job_id, callback.from_user.id)
    await callback.message.edit_text("🗑 Расписание удалено.", reply_markup=schedules_menu_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("job_edit_time_"))
async def job_edit_time(callback: CallbackQuery, state: FSMContext):
    job_id = int(callback.data.replace("job_edit_time_", ""))
    await state.update_data(edit_job_id=job_id)
    await state.set_state(EditJobState.waiting_time)
    await callback.message.edit_text("Напишите новое время в формате <code>18:30</code>", reply_markup=back_to_menu(), parse_mode="HTML")
    await callback.answer()


@dp.message(EditJobState.waiting_time)
async def edit_time_save(message: Message, state: FSMContext):
    text = message.text.strip()
    if not validate_time_text(text):
        await message.answer("Время должно быть в формате <code>ЧЧ:ММ</code>.", parse_mode="HTML")
        return
    data = await state.get_data()
    job_id = data["edit_job_id"]
    await update_job_fields(job_id, message.from_user.id, publish_time=text)
    await schedule_or_reschedule(job_id, message.from_user.id)
    await state.clear()
    await message.answer("✅ Время изменено.", reply_markup=schedules_menu_keyboard())


@dp.callback_query(F.data.startswith("job_edit_style_"))
async def job_edit_style(callback: CallbackQuery, state: FSMContext):
    job_id = int(callback.data.replace("job_edit_style_", ""))
    await state.update_data(edit_job_id=job_id)
    await state.set_state(EditJobState.choosing_style)
    await callback.message.edit_text("Выберите новый стиль:", reply_markup=style_keyboard("editstyle"))
    await callback.answer()


@dp.callback_query(F.data.startswith("editstyle_"))
async def edit_style_save(callback: CallbackQuery, state: FSMContext):
    style = callback.data.replace("editstyle_", "")
    data = await state.get_data()
    job_id = data["edit_job_id"]
    await update_job_fields(job_id, callback.from_user.id, image_style=style)
    await schedule_or_reschedule(job_id, callback.from_user.id)
    await state.clear()
    await callback.message.edit_text("✅ Стиль изменён.", reply_markup=schedules_menu_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("job_edit_title_"))
async def job_edit_title(callback: CallbackQuery, state: FSMContext):
    job_id = int(callback.data.replace("job_edit_title_", ""))
    await state.update_data(edit_job_id=job_id, custom_title_for_creation=False)
    await state.set_state(EditJobState.waiting_title)
    await callback.message.edit_text("Напишите новый заголовок для картинки:", reply_markup=back_to_menu())
    await callback.answer()


# ---------- История и резервные копии ----------

@dp.callback_query(F.data == "logs")
async def logs(callback: CallbackQuery):
    logs_list = await get_send_logs(callback.from_user.id, 20)
    if not logs_list:
        await callback.message.edit_text("История отправок пока пустая.", reply_markup=back_to_menu())
        await callback.answer()
        return

    text = "🕘 <b>История отправок</b>\n\n"
    for row in logs_list:
        icon = "✅" if row["status"] == "success" else "❌"
        target = row["target_title"] or "канал удалён"
        date = russian_date(row["target_date"]) if row["target_date"] else "—"
        text += f"{icon} {row['sent_at']}\n📢 {target}\n🗓 {date} — {row['sunset_time'] or '—'}\n"
        if row["error"]:
            text += f"Ошибка: <code>{row['error'][:160]}</code>\n"
        text += "\n"
    await callback.message.edit_text(text[:3900], reply_markup=back_to_menu(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "backup_menu")
async def backup_menu(callback: CallbackQuery):
    await callback.message.edit_text("💾 <b>Резервная копия</b>", reply_markup=backup_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "backup_export")
async def backup_export(callback: CallbackQuery):
    db_path = Path(DATABASE_PATH)
    if not db_path.exists():
        await callback.answer("База ещё не создана", show_alert=True)
        return
    await callback.message.answer_document(FSInputFile(str(db_path)), caption="Резервная копия bot.db")
    await callback.answer()


@dp.callback_query(F.data == "backup_import")
async def backup_import(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ImportBackupState.waiting_file)
    await callback.message.edit_text(
        "📥 Отправьте файл <b>bot.db</b>.\n\n"
        "Важно: импорт заменит текущую базу. После импорта сервер лучше перезапустить.",
        reply_markup=back_to_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(ImportBackupState.waiting_file, F.document)
async def import_backup_file(message: Message, state: FSMContext):
    if not message.document.file_name.endswith(".db"):
        await message.answer("Нужен файл базы с расширением .db")
        return
    backup_before = Path(DATABASE_PATH + ".before_import")
    db_path = Path(DATABASE_PATH)
    if db_path.exists():
        shutil.copyfile(db_path, backup_before)
    await bot.download(message.document, destination=db_path)
    await init_db()
    await state.clear()
    await message.answer("✅ База импортирована. Теперь перезапусти сервер на Wispbyte.", reply_markup=main_menu())


async def main():
    await init_db()
    await restore_jobs(bot)
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
