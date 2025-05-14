import os
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram import Update

# === Настройки ===
ADMIN_CHAT_ID = 'ВАШ_CHAT_ID'  # ← Замени на свой Chat ID (через @userinfobot)
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Устанавливается через переменную окружения

# Хранилище для привязки chat_id пользователя к администратору
user_chats = {}  # {admin_reply_chat_id: user_chat_id}

# Команда /start
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    update.message.reply_text(f"Привет, {user.first_name}!\n\nНапишите ваше сообщение (текст, фото или голосовое), и я передам его владельцу бота.")

# Получение сообщения от пользователя
def handle_message(update: Update, context: CallbackContext):
    user = update.effective_user
    message = update.message

    if str(user.id) == ADMIN_CHAT_ID:
        # Если это админ — смотрим, на какое сообщение он отвечает
        if message.reply_to_message and message.reply_to_message.forward_from:
            original_user_id = message.reply_to_message.forward_from.id

            try:
                if message.text:
                    context.bot.send_message(
                        chat_id=original_user_id,
                        text=f"📨 Ответ от администратора:\n\n{message.text}"
                    )
                elif message.photo:
                    photo_file = message.photo[-1].get_file()
                    context.bot.send_photo(
                        chat_id=original_user_id,
                        photo=photo_file.file_id,
                        caption=message.caption or "🖼️ Фото от администратора"
                    )
                elif message.voice:
                    voice_file = message.voice.get_file()
                    context.bot.send_voice(
                        chat_id=original_user_id,
                        voice=voice_file.file_id,
                        caption="🎤 Голосовое сообщение от администратора"
                    )
                else:
                    message.forward(chat_id=original_user_id)

                update.message.reply_text("✅ Сообщение отправлено пользователю!")
            except Exception as e:
                update.message.reply_text(f"❌ Ошибка при отправке: {e}")
        return

    # Пересылаем сообщение админу
    if message.text:
        forwarded = message.forward(chat_id=ADMIN_CHAT_ID)
        if forwarded:
            user_chats[forwarded.message_id] = user.id
            context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"💬 Текстовое сообщение от {user.first_name} (@{user.username} | ID: {user.id})"
            )

    elif message.photo:
        photo = message.photo[-1]
        caption = message.caption or "🖼️ Фото от пользователя"
        forwarded = context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=photo.file_id,
            caption=f"{caption}\n\n📸 От: {user.first_name} (@{user.username} | ID: {user.id})"
        )
        if forwarded:
            user_chats[forwarded.message_id] = user.id

    elif message.voice:
        forwarded = context.bot.send_voice(
            chat_id=ADMIN_CHAT_ID,
            voice=message.voice.file_id,
            caption=f"🎤 Голосовое от: {user.first_name} (@{user.username} | ID: {user.id})"
        )
        if forwarded:
            user_chats[forwarded.message_id] = user.id

# Основная функция
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(MessageHandler(Filters.photo, handle_message))
    dp.add_handler(MessageHandler(Filters.voice, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
