import asyncio
import logging

from aiogram.exceptions import TelegramNetworkError
from aiogram.types import BotCommand

from bot import bot, dp
from database import init_db
from scheduler import restore_jobs, scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("launcher")


async def prepare_telegram() -> None:
    """Подготавливает Telegram API, не завершая приложение при временном тайм-ауте."""
    for attempt in range(1, 11):
        try:
            await bot.delete_webhook(
                drop_pending_updates=True,
                request_timeout=60,
            )
            await bot.set_my_commands(
                [
                    BotCommand(command="start", description="Открыть панель управления"),
                    BotCommand(command="menu", description="Главное меню"),
                    BotCommand(command="help", description="Инструкция"),
                    BotCommand(command="cancel", description="Отменить действие"),
                ],
                request_timeout=60,
            )
            logger.info("Соединение с Telegram API установлено")
            return
        except TelegramNetworkError as exc:
            delay = min(attempt * 5, 30)
            logger.warning(
                "Telegram API временно недоступен, попытка %s/10; повтор через %s секунд: %s",
                attempt,
                delay,
                exc,
            )
            await asyncio.sleep(delay)

    logger.warning("Запускаю polling без предварительного delete_webhook")


async def main() -> None:
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
            polling_timeout=30,
            request_timeout=60,
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
            logger.exception("Бот аварийно остановился; перезапуск через 10 секунд")
            import time

            time.sleep(10)
