import asyncio
import base64
import json
import os
import re
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from groq import AsyncGroq

BOT_TOKEN = "8235661857:AAHKeHstis6lxuVTh6fn574ack94ZYiVJcY"
GROQ_API_KEY = "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"
ADMIN_ID = 6884407224  # твой Telegram ID для получения копий

from aiogram.client.default import DefaultBotProperties

class LoggingBot(Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_user_id = None

    async def send_message(self, chat_id, text, **kwargs):
        result = await super().send_message(chat_id, text, **kwargs)
        # Логируем ответы бота пользователям (не себе и не пустые служебные)
        try:
            if chat_id != ADMIN_ID and str(chat_id) != str(ADMIN_ID):
                uname = user_names.get(chat_id, str(chat_id))
                await super().send_message(ADMIN_ID, f"🤖 Бот → {uname}:\n{text}")
        except Exception:
            pass
        return result

    async def send_photo(self, chat_id, photo, caption=None, **kwargs):
        result = await super().send_photo(chat_id, photo, caption=caption, **kwargs)
        try:
            if chat_id != ADMIN_ID and str(chat_id) != str(ADMIN_ID):
                uname = user_names.get(chat_id, str(chat_id))
                await super().send_message(ADMIN_ID, f"🤖 Бот → {uname} [фото]: {caption or ''}")
        except Exception:
            pass
        return result

bot = LoggingBot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
client = AsyncGroq(api_key=GROQ_API_KEY)

# --- Middleware для логирования всех сообщений ---
@dp.message.middleware()
async def log_middleware(handler, message, data):
    try:
        if message.from_user.id != ADMIN_ID:
            user = message.from_user
            name = f"@{user.username}" if user.username else user.full_name
            user_names[user.id] = name
            if message.text and not message.photo:
                await bot.send_message(
                    ADMIN_ID,
                    f"💬 {name}: {message.text}"
                )
            elif message.photo:
                await bot.send_photo(
                    ADMIN_ID,
                    photo=message.photo[-1].file_id,
                    caption=f"📸 {name}"
                )
    except Exception:
        pass
    return await handler(message, data)

pending_photos = {}  # хранит image_data пока ждём вес от пользователя
user_names = {}  # chat_id -> @username для красивых логов

# --- Постоянное хранение профилей ---
PROFILES_FILE = "profiles.json"

def load_profiles() -> dict:
    if os.path.exists(PROFILES_FILE):
        with open(PROFILES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {int(k): v for k, v in data.items()}
    return {}

def save_profiles(profiles: dict):
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in profiles.items()}, f, ensure_ascii=False, indent=2)

user_profiles = load_profiles()

# --- База КБЖУ на 100г готового продукта ---
FOOD_DB = {
    # Молочные
    "творог": {"kcal": 116, "p": 18.0, "f": 4.0, "c": 3.3},
    "творог 0%": {"kcal": 71, "p": 16.5, "f": 0.1, "c": 1.3},
    "творог 5%": {"kcal": 121, "p": 17.0, "f": 5.0, "c": 1.8},
    "творог 9%": {"kcal": 159, "p": 16.7, "f": 9.0, "c": 2.0},
    "молоко": {"kcal": 52, "p": 2.8, "f": 2.5, "c": 4.7},
    "кефир": {"kcal": 40, "p": 3.4, "f": 1.0, "c": 4.7},
    "йогурт": {"kcal": 68, "p": 5.0, "f": 3.2, "c": 3.5},
    "сметана": {"kcal": 206, "p": 2.8, "f": 20.0, "c": 3.2},
    "сыр": {"kcal": 350, "p": 26.0, "f": 26.5, "c": 0.0},
    "яйцо": {"kcal": 157, "p": 12.7, "f": 11.5, "c": 0.7},
    # Крупы (варёные)
    "рис": {"kcal": 130, "p": 2.7, "f": 0.3, "c": 28.0},
    "гречка": {"kcal": 110, "p": 4.0, "f": 1.0, "c": 21.0},
    "овсянка": {"kcal": 88, "p": 3.0, "f": 1.7, "c": 15.0},
    "макароны": {"kcal": 112, "p": 3.7, "f": 0.4, "c": 23.0},
    "перловка": {"kcal": 109, "p": 3.1, "f": 0.4, "c": 22.0},
    "чечевица": {"kcal": 116, "p": 9.0, "f": 0.4, "c": 20.0},
    "горох": {"kcal": 130, "p": 8.0, "f": 0.5, "c": 22.0},
    "фасоль": {"kcal": 123, "p": 8.4, "f": 0.5, "c": 21.5},
    # Мясо (готовое)
    "куриная грудка": {"kcal": 165, "p": 31.0, "f": 3.6, "c": 0.0},
    "курица": {"kcal": 195, "p": 21.0, "f": 12.0, "c": 0.0},
    "говядина": {"kcal": 187, "p": 25.0, "f": 9.5, "c": 0.0},
    "свинина": {"kcal": 261, "p": 16.0, "f": 21.5, "c": 0.0},
    "баранина": {"kcal": 209, "p": 20.0, "f": 14.0, "c": 0.0},
    "индейка": {"kcal": 190, "p": 28.0, "f": 8.5, "c": 0.0},
    "рыба": {"kcal": 100, "p": 18.0, "f": 3.0, "c": 0.0},
    "лосось": {"kcal": 208, "p": 20.0, "f": 13.0, "c": 0.0},
    "тунец": {"kcal": 144, "p": 30.0, "f": 1.5, "c": 0.0},
    "фарш": {"kcal": 250, "p": 18.0, "f": 20.0, "c": 0.0},
    # Хлеб/выпечка
    "хлеб белый": {"kcal": 265, "p": 8.1, "f": 3.2, "c": 49.0},
    "хлеб чёрный": {"kcal": 214, "p": 6.6, "f": 1.2, "c": 42.5},
    "батон": {"kcal": 262, "p": 7.9, "f": 3.0, "c": 50.0},
    "лаваш": {"kcal": 277, "p": 9.1, "f": 1.1, "c": 57.0},
    # Овощи
    "картофель": {"kcal": 86, "p": 2.0, "f": 0.1, "c": 20.0},
    "капуста": {"kcal": 27, "p": 1.8, "f": 0.1, "c": 4.7},
    "морковь": {"kcal": 35, "p": 1.3, "f": 0.1, "c": 6.9},
    "помидор": {"kcal": 20, "p": 0.6, "f": 0.2, "c": 4.5},
    "огурец": {"kcal": 15, "p": 0.8, "f": 0.1, "c": 2.8},
    "лук": {"kcal": 41, "p": 1.4, "f": 0.0, "c": 8.2},
    "чеснок": {"kcal": 149, "p": 6.5, "f": 0.5, "c": 29.9},
    "баклажан": {"kcal": 25, "p": 1.2, "f": 0.1, "c": 4.5},
    "кабачок": {"kcal": 24, "p": 0.6, "f": 0.3, "c": 4.6},
    "перец": {"kcal": 27, "p": 1.3, "f": 0.1, "c": 5.3},
    "свёкла": {"kcal": 49, "p": 1.5, "f": 0.1, "c": 11.8},
    "шпинат": {"kcal": 23, "p": 2.9, "f": 0.4, "c": 2.0},
    # Фрукты
    "яблоко": {"kcal": 52, "p": 0.3, "f": 0.4, "c": 11.8},
    "банан": {"kcal": 96, "p": 1.5, "f": 0.2, "c": 21.0},
    "апельсин": {"kcal": 43, "p": 0.9, "f": 0.2, "c": 8.1},
    "груша": {"kcal": 42, "p": 0.4, "f": 0.3, "c": 9.5},
    "виноград": {"kcal": 72, "p": 0.6, "f": 0.2, "c": 17.5},
    # Масла и жиры
    "масло сливочное": {"kcal": 748, "p": 0.5, "f": 82.5, "c": 0.8},
    "масло подсолнечное": {"kcal": 899, "p": 0.0, "f": 99.9, "c": 0.0},
    "масло оливковое": {"kcal": 884, "p": 0.0, "f": 99.8, "c": 0.0},
    # Прочее
    "сахар": {"kcal": 399, "p": 0.0, "f": 0.0, "c": 99.8},
    "мёд": {"kcal": 329, "p": 0.8, "f": 0.0, "c": 80.3},
    "орехи": {"kcal": 607, "p": 15.0, "f": 53.0, "c": 11.0},
    "арахис": {"kcal": 567, "p": 25.8, "f": 49.2, "c": 16.1},
    "семечки": {"kcal": 582, "p": 20.7, "f": 52.9, "c": 5.0},
    "шоколад": {"kcal": 546, "p": 5.4, "f": 34.3, "c": 56.0},
    "майонез": {"kcal": 680, "p": 2.8, "f": 74.0, "c": 2.6},
    "кетчуп": {"kcal": 90, "p": 1.8, "f": 0.1, "c": 20.0},
    "соус": {"kcal": 80, "p": 1.5, "f": 2.0, "c": 12.0},
    # Супы (на 100г готового)
    "суп с фрикадельками": {"kcal": 45, "p": 3.5, "f": 2.0, "c": 3.5},
    "суп": {"kcal": 40, "p": 2.5, "f": 1.5, "c": 4.0},
    "борщ": {"kcal": 48, "p": 2.8, "f": 1.8, "c": 5.5},
    "щи": {"kcal": 35, "p": 2.2, "f": 1.2, "c": 3.8},
    "рассольник": {"kcal": 42, "p": 2.5, "f": 1.5, "c": 4.5},
    "солянка": {"kcal": 65, "p": 4.5, "f": 3.5, "c": 4.0},
    "харчо": {"kcal": 58, "p": 4.0, "f": 2.5, "c": 5.0},
    "уха": {"kcal": 45, "p": 5.0, "f": 1.5, "c": 2.5},
    "куриный суп": {"kcal": 40, "p": 4.0, "f": 1.5, "c": 3.0},
    "гороховый суп": {"kcal": 66, "p": 4.5, "f": 2.0, "c": 8.0},
    "грибной суп": {"kcal": 38, "p": 2.0, "f": 1.5, "c": 4.5},
    "молочный суп": {"kcal": 62, "p": 2.8, "f": 2.5, "c": 7.5},
    "окрошка": {"kcal": 42, "p": 2.5, "f": 1.8, "c": 4.0},
    "лагман": {"kcal": 95, "p": 5.5, "f": 4.0, "c": 10.0},
    "шурпа": {"kcal": 70, "p": 5.0, "f": 3.5, "c": 5.5},
    # Готовые блюда
    "плов": {"kcal": 185, "p": 7.0, "f": 8.5, "c": 22.0},
    "пельмени": {"kcal": 250, "p": 11.5, "f": 12.0, "c": 25.0},
    "манты": {"kcal": 215, "p": 10.0, "f": 10.5, "c": 22.0},
    "голубцы": {"kcal": 130, "p": 8.0, "f": 6.5, "c": 11.0},
    "котлета": {"kcal": 220, "p": 14.0, "f": 14.5, "c": 9.5},
    "оладьи": {"kcal": 230, "p": 6.5, "f": 9.5, "c": 30.0},
    "блины": {"kcal": 185, "p": 6.0, "f": 7.5, "c": 24.0},
    "омлет": {"kcal": 185, "p": 10.0, "f": 15.0, "c": 2.5},
    "каша": {"kcal": 100, "p": 3.5, "f": 1.5, "c": 19.0},
    "пюре": {"kcal": 95, "p": 2.2, "f": 3.5, "c": 14.5},
    "салат": {"kcal": 80, "p": 2.0, "f": 5.0, "c": 7.0},
    "оливье": {"kcal": 198, "p": 6.5, "f": 14.5, "c": 12.0},
    "винегрет": {"kcal": 110, "p": 2.0, "f": 6.5, "c": 11.5},
    "шаурма": {"kcal": 220, "p": 11.0, "f": 11.5, "c": 20.0},
    "пицца": {"kcal": 270, "p": 11.0, "f": 12.0, "c": 30.0},
    "бургер": {"kcal": 280, "p": 13.0, "f": 14.0, "c": 28.0},
    # Бульоны и вода
    "вода": {"kcal": 0, "p": 0.0, "f": 0.0, "c": 0.0},
    "бульон": {"kcal": 5, "p": 0.5, "f": 0.2, "c": 0.3},
    "куриный бульон": {"kcal": 7, "p": 0.8, "f": 0.2, "c": 0.3},
    "мясной бульон": {"kcal": 10, "p": 1.0, "f": 0.4, "c": 0.2},
    # Синонимы которые модель может написать
    "фрикадельки": {"kcal": 195, "p": 14.0, "f": 13.0, "c": 6.0},
    "фрикаделька": {"kcal": 195, "p": 14.0, "f": 13.0, "c": 6.0},
    "тефтели": {"kcal": 195, "p": 13.0, "f": 12.0, "c": 8.0},
    "котлеты": {"kcal": 220, "p": 14.0, "f": 14.5, "c": 9.5},
}

# Алиасы — что модель пишет → что искать в базе
FOOD_ALIASES = {
    "фарш": "фрикадельки",
    "мясо": "говядина",
    "мясные шарики": "фрикадельки",
    "шарики": "фрикадельки",
    "вермишель": "макароны",
    "лапша": "макароны",
    "пшено": "каша",
    "ячмень": "перловка",
    "жир": "масло подсолнечное",
    "зелень": "шпинат",
    "бульон куриный": "куриный бульон",
    "бульон мясной": "мясной бульон",
}

def find_food(name: str):
    """Ищет продукт в базе по частичному совпадению и алиасам"""
    name = name.lower().strip()
    # Прямое совпадение
    if name in FOOD_DB:
        return FOOD_DB[name]
    # Алиас
    if name in FOOD_ALIASES:
        return FOOD_DB.get(FOOD_ALIASES[name])
    # Частичное совпадение
    for key in FOOD_DB:
        if key in name or name in key:
            return FOOD_DB[key]
    # Алиас по частичному совпадению
    for alias, target in FOOD_ALIASES.items():
        if alias in name or name in alias:
            return FOOD_DB.get(target)
    return None

def calc_from_ingredients(ingredients: list) -> dict:
    """Считает итоговое КБЖУ по списку ингредиентов"""
    total = {"kcal": 0, "p": 0, "f": 0, "c": 0}
    found_any = False
    for item in ingredients:
        food = find_food(item["name"])
        if food:
            w = item["weight"] / 100
            total["kcal"] += food["kcal"] * w
            total["p"] += food["p"] * w
            total["f"] += food["f"] * w
            total["c"] += food["c"] * w
            found_any = True
    if not found_any:
        return None
    return {k: round(v) for k, v in total.items()}


# --- FSM состояния ---
class FoodAnalysis(StatesGroup):
    waiting_weight = State()

class ProfileSetup(StatesGroup):
    waiting_gender = State()
    waiting_age = State()
    waiting_weight = State()
    waiting_height = State()
    waiting_activity = State()
    waiting_goal = State()


def calculate_kbju(gender, age, weight, height, activity, goal):
    if gender == "м":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    activity_factors = {"1": 1.2, "2": 1.375, "3": 1.55, "4": 1.725, "5": 1.9}
    tdee = bmr * activity_factors.get(activity, 1.2)
    if goal == "похудение":
        calories = tdee - 400
        protein = weight * 2.0
        fat = weight * 0.9
    elif goal == "набор":
        calories = tdee + 300
        protein = weight * 1.8
        fat = weight * 1.1
    else:
        calories = tdee
        protein = weight * 1.6
        fat = weight * 1.0
    carbs = (calories - protein * 4 - fat * 9) / 4
    return {"calories": round(calories), "protein": round(protein), "fat": round(fat), "carbs": round(carbs)}


# --- /start ---
@dp.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.set_state(ProfileSetup.waiting_gender)
    await message.answer(
        "👋 Привет! Я бот для подсчёта калорий по фото.\n\n"
        "Сначала настроим твой профиль.\n\n"
        "👤 Укажи пол:\n*м* — мужской\n*ж* — женский",
        parse_mode="Markdown"
    )

@dp.message(ProfileSetup.waiting_gender)
async def process_gender(message: Message, state: FSMContext):
    gender = message.text.strip().lower()
    if gender not in ["м", "ж"]:
        await message.answer("Введи *м* или *ж*", parse_mode="Markdown")
        return
    await state.update_data(gender=gender)
    await state.set_state(ProfileSetup.waiting_age)
    await message.answer("🎂 Сколько лет?")

@dp.message(ProfileSetup.waiting_age)
async def process_age(message: Message, state: FSMContext):
    try:
        age = int(message.text.strip())
        assert 10 <= age <= 100
    except:
        await message.answer("Введи возраст числом (10–100)")
        return
    await state.update_data(age=age)
    await state.set_state(ProfileSetup.waiting_weight)
    await message.answer("⚖️ Вес в кг (например: 75)")

@dp.message(ProfileSetup.waiting_weight)
async def process_weight(message: Message, state: FSMContext):
    try:
        weight = float(message.text.strip().replace(",", "."))
        assert 30 <= weight <= 300
    except:
        await message.answer("Введи вес в кг (например: 75)")
        return
    await state.update_data(weight=weight)
    await state.set_state(ProfileSetup.waiting_height)
    await message.answer("📏 Рост в см (например: 175)")

@dp.message(ProfileSetup.waiting_height)
async def process_height(message: Message, state: FSMContext):
    try:
        height = float(message.text.strip().replace(",", "."))
        assert 100 <= height <= 250
    except:
        await message.answer("Введи рост в см (например: 175)")
        return
    await state.update_data(height=height)
    await state.set_state(ProfileSetup.waiting_activity)
    await message.answer(
        "🏃 Уровень активности:\n\n"
        "*1* — сидячий\n*2* — лёгкие нагрузки 1-3р/нед\n"
        "*3* — умеренные 3-5р/нед\n*4* — интенсивные 6-7р/нед\n*5* — физический труд",
        parse_mode="Markdown"
    )

@dp.message(ProfileSetup.waiting_activity)
async def process_activity(message: Message, state: FSMContext):
    if message.text.strip() not in ["1","2","3","4","5"]:
        await message.answer("Введи цифру от 1 до 5")
        return
    await state.update_data(activity=message.text.strip())
    await state.set_state(ProfileSetup.waiting_goal)
    await message.answer(
        "🎯 Цель:\n\n*похудение* / *поддержание* / *набор*",
        parse_mode="Markdown"
    )

@dp.message(ProfileSetup.waiting_goal)
async def process_goal(message: Message, state: FSMContext):
    goal = message.text.strip().lower()
    if goal not in ["похудение", "поддержание", "набор"]:
        await message.answer("Введи: *похудение*, *поддержание* или *набор*", parse_mode="Markdown")
        return
    data = await state.get_data()
    await state.clear()
    profile = {**data, "goal": goal}
    user_profiles[message.from_user.id] = profile
    save_profiles(user_profiles)
    kbju = calculate_kbju(**profile)
    goal_emoji = {"похудение": "📉", "поддержание": "⚖️", "набор": "📈"}
    activity_names = {"1": "сидячий", "2": "лёгкая", "3": "умеренная", "4": "высокая", "5": "очень высокая"}
    await message.answer(
        f"✅ Профиль сохранён!\n\n"
        f"👤 Пол: {'Мужской' if profile['gender'] == 'м' else 'Женский'}\n"
        f"🎂 Возраст: {profile['age']} лет\n"
        f"⚖️ Вес: {profile['weight']} кг\n"
        f"📏 Рост: {profile['height']} см\n"
        f"🏃 Активность: {activity_names[profile['activity']]}\n"
        f"🎯 Цель: {goal_emoji[goal]} {goal.capitalize()}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔥 Норма калорий: *{kbju['calories']} ккал*\n"
        f"💪 Белки: *{kbju['protein']} г*\n"
        f"🧈 Жиры: *{kbju['fat']} г*\n"
        f"🍞 Углеводы: *{kbju['carbs']} г*\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📸 Отправляй фото еды!",
        parse_mode="Markdown"
    )


# --- Шаг 1: получаем фото, спрашиваем вес ---
@dp.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    image_data = base64.b64encode(file_bytes.read()).decode("utf-8")
    pending_photos[message.from_user.id] = image_data
    await state.set_state(FoodAnalysis.waiting_weight)
    await message.answer(
        "⚖️ Укажи вес порции в граммах или напиши *авто* — и я определю сам",
        parse_mode="Markdown"
    )



# --- Шаг 2: получаем вес и анализируем ---
@dp.message(FoodAnalysis.waiting_weight)
async def handle_weight_and_analyze(message: Message, state: FSMContext):
    await state.clear()
    image_data = pending_photos.pop(message.from_user.id, None)
    if not image_data:
        await message.answer("Сначала отправь фото еды!")
        return

    user_weight_input = message.text.strip().lower()
    manual_weight = None
    if user_weight_input != "авто":
        try:
            manual_weight = int(float(user_weight_input.replace(",", ".")))
        except ValueError:
            await message.answer("Не понял вес. Напиши число (например 350) или *авто*", parse_mode="Markdown")
            pending_photos[message.from_user.id] = image_data
            await state.set_state(FoodAnalysis.waiting_weight)
            return

    profile = user_profiles.get(message.from_user.id)
    await message.answer("🔍 Анализирую еду на фото...")

    try:
        # Шаг 1: модель только распознаёт состав и вес, отдаёт JSON
        step1 = await client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                        },
                        {
                            "type": "text",
                            "text": (
                                "Определи что на фото. Верни ТОЛЬКО валидный JSON без markdown, без пояснений.\n"
                                "Формат:\n"
                                '{"dish": "название блюда", "total_weight": 250, '
                                '"ingredients": [{"name": "творог", "weight": 250}]}\n\n'
                                "Правила:\n"
                                "- total_weight — реальный вес порции в граммах, смотри на размер тарелки, не завышай\n"
                                "- dish — точное название блюда на русском (борщ, суп с фрикадельками, плов, гречка с курицей и т.д.)\n"
                                "- name — название ингредиента на русском (рис, фарш, картофель, морковь и т.д.)\n"
                                "- НЕ называй блюда японскими или экзотическими именами если это обычная домашняя еда\n"
                                "- суп с фрикадельками и рисом — это СУП С ФРИКАДЕЛЬКАМИ, не хаш и не мисо\n"
                                "- ВСЕГДА разбивай блюдо на отдельные ингредиенты, никогда не пиши блюдо целиком как один ингредиент\n"
                                "- Суп: бульон + крупа/картошка + мясо/фрикадельки + овощи\n"
                            
