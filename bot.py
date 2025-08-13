import os
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from aiogram.utils.executor import start_webhook
from aiogram.dispatcher.filters import Command
from aiogram.contrib.middlewares.logging import LoggingMiddleware

# ==== Настройки ====
TOKEN = os.getenv("BOT_TOKEN", "7988401496:AAG1bLJFfLrQoohxCpL-NKP6e3LlHf30SQ8")
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if WEBHOOK_HOST else None
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.getenv("PORT", 5000))

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# ==== Списки ====
warnings_count = {}  # {user_id: количество предупреждений}
pending_verifications = {}  # {user_id: время входа}

bad_words = [
    # Русский мат
    "блять", "бля", "сука", "хуй", "пизда", "ебать", "мразь", "шлюха", "гондон",
    # Украинский мат
    "курва", "срака", "хуйня", "блядь", "пизда", "єбать",
    # Английский мат
    "fuck", "bitch", "asshole", "bastard", "dick", "slut", "shit", "whore", "cunt",
    # Немецкий мат
    "scheisse", "fotze", "arschloch", "hurensohn", "wichser", "schlampe"
]

# ==== Обработчики ====
@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    await message.answer("Привет! Я — защитный бот группы.")

@dp.message_handler(content_types=["new_chat_members"])
async def welcome_user(message: types.Message):
    for user in message.new_chat_members:
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("✅ Я не робот", callback_data=f"verify_{user.id}")
        )
        await message.reply(
            f"👋 Добро пожаловать, {user.full_name}!\nНажмите кнопку, чтобы подтвердить, что вы не бот.",
            reply_markup=kb
        )
        pending_verifications[user.id] = datetime.now()
        asyncio.create_task(kick_if_not_verified(message.chat.id, user.id))

async def kick_if_not_verified(chat_id, user_id):
    await asyncio.sleep(600)  # 10 минут
    if user_id in pending_verifications:
        try:
            await bot.ban_chat_member(chat_id, user_id)
            await bot.unban_chat_member(chat_id, user_id)
            del pending_verifications[user_id]
        except Exception as e:
            pass

@dp.callback_query_handler(lambda c: c.data.startswith("verify_"))
async def verify_user(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    if user_id == callback.from_user.id:
        pending_verifications.pop(user_id, None)
        await callback.message.edit_text("✅ Вы прошли проверку!")
    else:
        await callback.answer("Это не ваша кнопка!")

@dp.message_handler()
async def filter_bad_words(message: types.Message):
    if not message.text:
        return
    text = message.text.lower()
    if any(word in text for word in bad_words):
        user_id = message.from_user.id
        warnings_count[user_id] = warnings_count.get(user_id, 0) + 1
        if warnings_count[user_id] >= 3:
            try:
                await bot.ban_chat_member(message.chat.id, user_id)
                await bot.unban_chat_member(message.chat.id, user_id)
            except Exception as e:
                pass
            await message.reply(f"🚫 {message.from_user.full_name} забанен за мат.")
            warnings_count.pop(user_id)
        else:
            await message.reply(
                f"⚠️ {message.from_user.full_name}, предупреждение {warnings_count[user_id]}/3 за мат."
            )

@dp.message_handler(Command("ban"))
async def ban_user(message: types.Message):
    if message.reply_to_message:
        try:
            await bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
            await bot.unban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
            await message.reply(f"🚫 Пользователь {message.reply_to_message.from_user.full_name} забанен.")
        except Exception as e:
            await message.reply("❌ Не удалось забанить пользователя.")

@dp.message_handler(Command("kick"))
async def kick_user(message: types.Message):
    if message.reply_to_message:
        try:
            await bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
            await bot.unban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
            await message.reply(f"👢 Пользователь {message.reply_to_message.from_user.full_name} кикнут.")
        except Exception as e:
            await message.reply("❌ Не удалось кикнуть пользователя.")

@dp.message_handler(Command("mut"))
async def mute_user(message: types.Message):
    if message.reply_to_message:
        try:
            time = int(message.get_args())
            until_date = datetime.now() + timedelta(minutes=time)
            await bot.restrict_chat_member(
                message.chat.id,
                message.reply_to_message.from_user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=int(until_date.timestamp())
            )
            await message.reply(f"🤐 Пользователь {message.reply_to_message.from_user.full_name} замучен на {time} мин.")
        except Exception as e:
            await message.reply("❌ Укажите время мута в минутах, например /mut 10")

# ==== Запуск ====
async def on_startup(dp):
    if WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(dp):
    await bot.delete_webhook()

if __name__ == "__main__":
    if WEBHOOK_URL:
        start_webhook(
            dispatcher=dp,
            webhook_path=WEBHOOK_PATH,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            skip_updates=True,
            host=WEBAPP_HOST,
            port=WEBAPP_PORT,
        )
    else:
        import logging
        logging.basicConfig(level=logging.INFO)
        from aiogram import executor
        executor.start_polling(dp, skip_updates=True)
