import asyncio
import logging
import socket
import time
from pathlib import Path

from aiogram.exceptions import TelegramNetworkError
from aiogram.types import BotCommand

from bot import bot, dp
from database import init_db
from image_editor import router as image_editor_router
from scheduler import restore_jobs, scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("launcher")


def cleanup_generated_files() -> None:
    """Удаляет временные изображения, оставшиеся после аварийного перезапуска."""
    generated_dir = Path("generated")
    generated_dir.mkdir(parents=True, exist_ok=True)
    removed = 0
    for path in generated_dir.glob("sunset_*.png"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            logger.warning("Не удалось удалить временный файл %s", path)
    if removed:
        logger.info("Удалено временных изображений при старте: %s", removed)


def configure_fast_network() -> None:
    """Принудительно использует IPv4 и короткие тайм-ауты для Telegram API."""
    connector_init = getattr(bot.session, "_connector_init", None)
    if isinstance(connector_init, dict):
        connector_init.update(
            {
                "family": socket.AF_INET,
                "ttl_dns_cache": 300,
                "enable_cleanup_closed": True,
            }
        )
        logger.info("Telegram transport настроен на IPv4")


async def prepare_telegram() -> None:
    """Подготавливает Telegram API без долгого зависания при сетевом сбое."""
    for attempt in range(1, 6):
        try:
            await bot.delete_webhook(drop_pending_updates=False, request_timeout=12)
            await bot.set_my_commands(
                [
                    BotCommand(command="start", description="Открыть панель управления"),
                    BotCommand(command="menu", description="Главное меню"),
                    BotCommand(command="editor", description="Редактор картинки"),
                    BotCommand(command="help", description="Инструкция"),
                    BotCommand(command="cancel", description="Отменить действие"),
                ],
                request_timeout=12,
            )
            logger.info("Соединение с Telegram API установлено")
            return
        except TelegramNetworkError as exc:
            delay = min(attempt * 2, 8)
            logger.warning(
                "Telegram API временно недоступен, попытка %s/5; повтор через %s секунд: %s",
                attempt,
                delay,
                exc,
            )
            await asyncio.sleep(delay)

    logger.warning("Запускаю polling без предварительной настройки команд")


async def main() -> None:
    cleanup_generated_files()
    configure_fast_network()
    dp.include_router(image_editor_router)
    await init_db()
    await prepare_telegram()
    await restore_jobs(bot)

    if not scheduler.running:
        scheduler.start()

    logger.info("Бот запущен; восстановлено задач: %s", len(scheduler.get_jobs()))

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            polling_timeout=5,
            request_timeout=12,
            handle_as_tasks=True,
            handle_signals=True,
            close_bot_session=False,
        )
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
            break
        except KeyboardInterrupt:
            break
        except Exception:
            logger.exception("Бот аварийно остановился; перезапуск через 3 секунды")
            time.sleep(3)
