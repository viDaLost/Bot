from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import ADMIN_IDS
from image_generator import IMAGE_FORMATS, STYLE_TITLES, create_sunset_image

router = Router(name="image_editor")
_cleanup_tasks: set[asyncio.Task] = set()


class EditorState(StatesGroup):
    waiting_title = State()
    waiting_time = State()
    waiting_city = State()


def _is_admin(user_id: int) -> bool:
    return not ADMIN_IDS or user_id in ADMIN_IDS


async def _safe_delete(bot, chat_id: int, message_id: int | None) -> None:
    if not message_id:
        return
    with suppress(Exception):
        await bot.delete_message(chat_id=chat_id, message_id=message_id)


async def _delete_after(bot, chat_id: int, message_id: int, delay: int = 90) -> None:
    await asyncio.sleep(delay)
    await _safe_delete(bot, chat_id, message_id)


def _schedule_cleanup(message: Message, delay: int = 90) -> None:
    task = asyncio.create_task(_delete_after(message.bot, message.chat.id, message.message_id, delay))
    _cleanup_tasks.add(task)
    task.add_done_callback(_cleanup_tasks.discard)


def _keyboard(data: dict) -> InlineKeyboardMarkup:
    style = data.get("style", "modern")
    rows = []
    style_buttons = []
    for key, title in STYLE_TITLES.items():
        mark = "✓ " if key == style else ""
        style_buttons.append(InlineKeyboardButton(text=f"{mark}{title}", callback_data=f"editor:style:{key}"))
    for index in range(0, len(style_buttons), 2):
        rows.append(style_buttons[index:index + 2])
    rows.extend([
        [
            InlineKeyboardButton(text="✏️ Заголовок", callback_data="editor:title"),
            InlineKeyboardButton(text="🕒 Время", callback_data="editor:time"),
        ],
        [
            InlineKeyboardButton(text="🏙 Город", callback_data="editor:city"),
            InlineKeyboardButton(text="📅 День недели", callback_data="editor:weekday"),
        ],
        [InlineKeyboardButton(text=f"📐 Формат · {data.get('format', '16:9')}", callback_data="editor:format")],
        [InlineKeyboardButton(text="👁 Создать предпросмотр", callback_data="editor:preview")],
        [InlineKeyboardButton(text="🔄 Сбросить настройки", callback_data="editor:reset")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _format_keyboard(current: str) -> InlineKeyboardMarkup:
    rows = []
    for key, config in IMAGE_FORMATS.items():
        mark = "✓ " if key == current else ""
        rows.append([InlineKeyboardButton(text=f"{mark}{config['title']}", callback_data=f"editor:format:{key}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="editor:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _summary(data: dict) -> str:
    return (
        "🎨 <b>Премиальный редактор</b>\n\n"
        f"Стиль: <b>{STYLE_TITLES.get(data.get('style', 'modern'), 'Obsidian Gold')}</b>\n"
        f"Формат: <b>{data.get('format', '16:9')}</b>\n"
        f"Заголовок: <b>{data.get('title', 'Заход солнца')}</b>\n"
        f"Время: <b>{data.get('time', '18:00')}</b>\n"
        f"Город: <b>{data.get('city') or 'скрыт'}</b>\n"
        f"День недели: <b>{'да' if data.get('weekday') else 'нет'}</b>\n\n"
        "Выберите стиль и нажмите «Создать предпросмотр»."
    )


async def _defaults(state: FSMContext) -> dict:
    data = await state.get_data()
    if not data.get("editor_ready"):
        data = {
            "editor_ready": True,
            "style": "modern",
            "format": "16:9",
            "title": "Заход солнца",
            "time": "18:00",
            "city": "",
            "weekday": False,
            "editor_preview_id": None,
            "editor_panel_id": None,
        }
        await state.set_data(data)
    return data


async def _replace_panel_after_input(message: Message, state: FSMContext, data: dict) -> None:
    previous_panel_id = data.get("editor_panel_id")
    with suppress(TelegramBadRequest):
        await message.delete()
    await _safe_delete(message.bot, message.chat.id, previous_panel_id)
    panel = await message.answer(_summary(data), reply_markup=_keyboard(data), parse_mode="HTML")
    await state.update_data(editor_panel_id=panel.message_id)


@router.message(Command("editor"))
async def open_editor(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await _defaults(state)
    await _safe_delete(message.bot, message.chat.id, data.get("editor_panel_id"))
    await _safe_delete(message.bot, message.chat.id, data.get("editor_preview_id"))
    with suppress(TelegramBadRequest):
        await message.delete()
    panel = await message.answer(_summary(data), reply_markup=_keyboard(data), parse_mode="HTML")
    await state.update_data(editor_panel_id=panel.message_id, editor_preview_id=None)


@router.callback_query(F.data.startswith("editor:style:"))
async def choose_style(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    style = callback.data.rsplit(":", 1)[-1]
    if style not in STYLE_TITLES:
        return
    await state.update_data(style=style)
    data = await _defaults(state)
    await callback.message.edit_text(_summary(data), reply_markup=_keyboard(data), parse_mode="HTML")


@router.callback_query(F.data == "editor:format")
async def open_format(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await _defaults(state)
    await callback.message.edit_text(
        "📐 <b>Выберите формат изображения</b>",
        reply_markup=_format_keyboard(data.get("format", "16:9")),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("editor:format:"))
async def choose_format(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    image_format = callback.data.replace("editor:format:", "", 1)
    if image_format not in IMAGE_FORMATS:
        return
    await state.update_data(format=image_format)
    data = await _defaults(state)
    await callback.message.edit_text(_summary(data), reply_markup=_keyboard(data), parse_mode="HTML")


@router.callback_query(F.data == "editor:back")
async def editor_back(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await _defaults(state)
    await callback.message.edit_text(_summary(data), reply_markup=_keyboard(data), parse_mode="HTML")


@router.callback_query(F.data == "editor:title")
async def ask_title(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(EditorState.waiting_title)
    await state.update_data(editor_panel_id=callback.message.message_id)
    await callback.message.edit_text("✏️ Отправьте новый заголовок, до 42 символов.")


@router.message(EditorState.waiting_title)
async def save_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()[:42]
    if not title:
        with suppress(TelegramBadRequest):
            await message.delete()
        notice = await message.answer("Заголовок не должен быть пустым.")
        _schedule_cleanup(notice, 45)
        return
    await state.update_data(title=title)
    await state.set_state(None)
    data = await _defaults(state)
    await _replace_panel_after_input(message, state, data)


@router.callback_query(F.data == "editor:time")
async def ask_time(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(EditorState.waiting_time)
    await state.update_data(editor_panel_id=callback.message.message_id)
    await callback.message.edit_text("🕒 Отправьте время в формате ЧЧ:ММ, например 19:45.")


@router.message(EditorState.waiting_time)
async def save_time(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError:
        with suppress(TelegramBadRequest):
            await message.delete()
        notice = await message.answer("Неверный формат. Пример: 19:45")
        _schedule_cleanup(notice, 45)
        return
    await state.update_data(time=value)
    await state.set_state(None)
    data = await _defaults(state)
    await _replace_panel_after_input(message, state, data)


@router.callback_query(F.data == "editor:city")
async def ask_city(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(EditorState.waiting_city)
    await state.update_data(editor_panel_id=callback.message.message_id)
    await callback.message.edit_text("🏙 Отправьте название города или «-», чтобы скрыть его.")


@router.message(EditorState.waiting_city)
async def save_city(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    await state.update_data(city="" if value == "-" else value[:36])
    await state.set_state(None)
    data = await _defaults(state)
    await _replace_panel_after_input(message, state, data)


@router.callback_query(F.data == "editor:weekday")
async def toggle_weekday(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await _defaults(state)
    await state.update_data(weekday=not data.get("weekday", False))
    data = await _defaults(state)
    await callback.message.edit_text(_summary(data), reply_markup=_keyboard(data), parse_mode="HTML")


@router.callback_query(F.data == "editor:reset")
async def reset_editor(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Настройки сброшены")
    old_data = await state.get_data()
    await _safe_delete(callback.bot, callback.message.chat.id, old_data.get("editor_preview_id"))
    await state.clear()
    data = await _defaults(state)
    await state.update_data(editor_panel_id=callback.message.message_id)
    await callback.message.edit_text(_summary(data), reply_markup=_keyboard(data), parse_mode="HTML")


@router.callback_query(F.data == "editor:preview")
async def preview(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Создаю изображение…")
    data = await _defaults(state)
    await _safe_delete(callback.bot, callback.message.chat.id, data.get("editor_preview_id"))
    status = await callback.message.answer("🎨 Генерирую премиальный предпросмотр…")
    path = None
    try:
        path = await asyncio.to_thread(
            create_sunset_image,
            sunset_time=data.get("time", "18:00"),
            publish_date=datetime.now().strftime("%Y-%m-%d"),
            style=data.get("style", "modern"),
            title_text=data.get("title", "Заход солнца"),
            location_name=data.get("city", ""),
            show_city=bool(data.get("city")),
            show_weekday=bool(data.get("weekday")),
            image_format=data.get("format", "16:9"),
        )
        preview_message = await callback.message.answer_photo(
            FSInputFile(path),
            caption="✨ Предпросмотр автоматически удалится через 90 секунд.",
        )
        await state.update_data(editor_preview_id=preview_message.message_id)
        _schedule_cleanup(preview_message, 90)
    except Exception as exc:
        notice = await callback.message.answer(f"Не удалось создать картинку: {exc}")
        _schedule_cleanup(notice, 90)
    finally:
        await _safe_delete(callback.bot, callback.message.chat.id, status.message_id)
        if path:
            Path(path).unlink(missing_ok=True)
