from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from image_generator import STYLE_TITLES, create_sunset_image

router = Router(name="image_editor")


class EditorState(StatesGroup):
    waiting_title = State()
    waiting_time = State()
    waiting_city = State()


def _keyboard(data: dict) -> InlineKeyboardMarkup:
    style = data.get("style", "modern")
    rows = []
    style_buttons = []
    for key, title in STYLE_TITLES.items():
        mark = "✅ " if key == style else ""
        style_buttons.append(InlineKeyboardButton(text=f"{mark}{title}", callback_data=f"editor:style:{key}"))
    for index in range(0, len(style_buttons), 2):
        rows.append(style_buttons[index:index + 2])
    rows.extend([
        [InlineKeyboardButton(text="✏️ Заголовок", callback_data="editor:title"), InlineKeyboardButton(text="🕒 Время", callback_data="editor:time")],
        [InlineKeyboardButton(text="🏙 Город", callback_data="editor:city"), InlineKeyboardButton(text="📅 День недели", callback_data="editor:weekday")],
        [InlineKeyboardButton(text="👁 Предпросмотр", callback_data="editor:preview")],
        [InlineKeyboardButton(text="🔄 Сбросить", callback_data="editor:reset")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _summary(data: dict) -> str:
    return (
        "🎨 <b>Редактор картинки</b>\n\n"
        f"Стиль: <b>{STYLE_TITLES.get(data.get('style', 'modern'), 'modern')}</b>\n"
        f"Заголовок: <b>{data.get('title', 'Заход солнца')}</b>\n"
        f"Время: <b>{data.get('time', '18:00')}</b>\n"
        f"Город: <b>{data.get('city') or 'скрыт'}</b>\n"
        f"День недели: <b>{'да' if data.get('weekday') else 'нет'}</b>\n\n"
        "Нажми «Предпросмотр», чтобы получить готовую картинку."
    )


async def _defaults(state: FSMContext) -> dict:
    data = await state.get_data()
    if not data.get("editor_ready"):
        data = {
            "editor_ready": True,
            "style": "modern",
            "title": "Заход солнца",
            "time": "18:00",
            "city": "",
            "weekday": False,
        }
        await state.set_data(data)
    return data


@router.message(Command("editor"))
async def open_editor(message: Message, state: FSMContext) -> None:
    data = await _defaults(state)
    await message.answer(_summary(data), reply_markup=_keyboard(data), parse_mode="HTML")


@router.callback_query(F.data.startswith("editor:style:"))
async def choose_style(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    style = callback.data.rsplit(":", 1)[-1]
    if style not in STYLE_TITLES:
        return
    await state.update_data(style=style)
    data = await _defaults(state)
    await callback.message.edit_text(_summary(data), reply_markup=_keyboard(data), parse_mode="HTML")


@router.callback_query(F.data == "editor:title")
async def ask_title(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(EditorState.waiting_title)
    await callback.message.answer("Отправь новый заголовок, до 42 символов.")


@router.message(EditorState.waiting_title)
async def save_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()[:42]
    if not title:
        await message.answer("Заголовок не должен быть пустым.")
        return
    await state.update_data(title=title)
    await state.set_state(None)
    data = await _defaults(state)
    await message.answer(_summary(data), reply_markup=_keyboard(data), parse_mode="HTML")


@router.callback_query(F.data == "editor:time")
async def ask_time(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(EditorState.waiting_time)
    await callback.message.answer("Отправь время в формате ЧЧ:ММ, например 19:45.")


@router.message(EditorState.waiting_time)
async def save_time(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Пример: 19:45")
        return
    await state.update_data(time=value)
    await state.set_state(None)
    data = await _defaults(state)
    await message.answer(_summary(data), reply_markup=_keyboard(data), parse_mode="HTML")


@router.callback_query(F.data == "editor:city")
async def ask_city(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(EditorState.waiting_city)
    await callback.message.answer("Отправь название города или «-», чтобы скрыть его.")


@router.message(EditorState.waiting_city)
async def save_city(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    await state.update_data(city="" if value == "-" else value[:36])
    await state.set_state(None)
    data = await _defaults(state)
    await message.answer(_summary(data), reply_markup=_keyboard(data), parse_mode="HTML")


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
    await state.clear()
    data = await _defaults(state)
    await callback.message.edit_text(_summary(data), reply_markup=_keyboard(data), parse_mode="HTML")


@router.callback_query(F.data == "editor:preview")
async def preview(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Создаю изображение…")
    data = await _defaults(state)
    status = await callback.message.answer("🎨 Генерирую предпросмотр…")
    path = None
    try:
        path = await asyncio.to_thread(
            create_sunset_image,
            data.get("time", "18:00"),
            datetime.now().strftime("%Y-%m-%d"),
            data.get("style", "modern"),
            data.get("title", "Заход солнца"),
            data.get("city", ""),
            bool(data.get("city")),
            bool(data.get("weekday")),
        )
        await callback.message.answer_photo(
            FSInputFile(path),
            caption="✅ Предпросмотр готов. Настройки можно изменить командой /editor.",
        )
    except Exception as exc:
        await callback.message.answer(f"Не удалось создать картинку: {exc}")
    finally:
        with suppress(Exception):
            await status.delete()
        if path:
            with suppress(OSError):
                Path(path).unlink()
