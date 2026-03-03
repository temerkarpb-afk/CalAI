import asyncio
import base64
import json
import os
import re
from threading import Thread  # Добавлено для фонового сервера
from flask import Flask        # Добавлено для обхода ошибки порта
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from groq import AsyncGroq
from aiogram.client.default import DefaultBotProperties

# --- БЛОК ДЛЯ RENDER (БЕСПЛАТНЫЙ ТАРИФ) ---
app = Flask('')

@app.route('/')
def home():
    return "Бот запущен и работает!"

def run_flask():
    # Render выдает порт динамически, берем его из настроек системы
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True # Поток умрет вместе с основным процессом
    t.start()

# Запускаем сервер-заглушку ПЕРЕД запуском бота
keep_alive()
# ------------------------------------------

BOT_TOKEN = "8235661857:AAHKeHstis6lxuVTh6fn574ack94ZYiVJcY"
GROQ_API_KEY = "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" # Не забудьте вставить свой ключ в панели Render!
ADMIN_ID = 6884407224 

class LoggingBot(Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def send_message(self, chat_id, text, **kwargs):
        result = await super().send_message(chat_id, text, **kwargs)
        try:
            if chat_id != ADMIN_ID:
                uname = user_names.get(chat_id, str(chat_id))
                await super().send_message(ADMIN_ID, f"🤖 Бот → {uname}:\n{text}")
        except Exception:
            pass
        return result

    async def send_photo(self, chat_id, photo, caption=None, **kwargs):
        result = await super().send_photo(chat_id, photo, caption=caption, **kwargs)
        try:
            if chat_id != ADMIN_ID:
                uname = user_names.get(chat_id, str(chat_id))
                await super().send_message(ADMIN_ID, f"🤖 Бот → {uname} [фото]: {caption or ''}")
        except Exception:
            pass
        return result

bot = LoggingBot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
client = AsyncGroq(api_key=GROQ_API_KEY)

# (Далее идет ваш остальной код без изменений: FOOD_DB, обработчики состояний и т.д.)
# Убедитесь, что в самом конце файла стоит стандартный запуск:
# if __name__ == "__main__":
#     asyncio.run(dp.start_polling(bot))


