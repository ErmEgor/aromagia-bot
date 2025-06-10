import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
### ИЗМЕНЕНИЕ: Импорты для вебхука
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
###

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

### ИЗМЕНЕНИЕ: Настройки для вебхука
# Render предоставляет URL в переменной окружения RENDER_EXTERNAL_URL
# Локально для теста можно использовать ngrok или аналоги
BASE_WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL")
# Путь для вебхука, лучше сделать его секретным
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
# Полный адрес для установки вебхука
WEBHOOK_URL = f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}"
###

# Проверка на наличие токенов
if not BOT_TOKEN or not CHANNEL_ID:
    raise ValueError("Необходимо установить переменные окружения BOT_TOKEN и CHANNEL_ID")

# Настройка логирования
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# --- Клавиатуры (остаются без изменений) ---
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✍️ Оставить отзыв")],
        [KeyboardButton(text="ℹ️ О нас")],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)
cancel_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_review")]]
)

# --- Состояния (остаются без изменений) ---
class ReviewState(StatesGroup):
    waiting_for_review_text = State()
    waiting_for_rating = State()
    waiting_for_anonymity_choice = State()

# --- Все хендлеры (обработчики сообщений и кнопок) остаются БЕЗ ИЗМЕНЕНИЙ ---
# ... (здесь весь ваш код с cmd_start, about_us, start_review и т.д.) ...
# Я их скрыл для краткости, просто оставьте их как есть в вашем файле.

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 <b>Добро пожаловать в кофейню «Аромагия»!</b>\n\n"
        "Я ваш личный помощник для сбора отзывов. "
        "Ваше мнение очень важно для нас, ведь оно помогает нам становиться лучше! ☕️✨\n\n"
        "Чтобы оставить отзыв, нажмите на кнопку ниже.",
        reply_markup=main_kb,
    )

@dp.message(F.text == "ℹ️ О нас")
async def about_us(message: types.Message):
    await message.answer(
        "<b>Кофейня «Аромагия»</b> — это уютное место, где каждый глоток кофе "
        "наполнен волшебством.\n\n"
        "Мы используем только свежеобжаренные зерна и готовим напитки с любовью. "
        "Спасибо, что вы с нами! ❤️"
    )

@dp.message(F.text == "✍️ Оставить отзыв")
async def start_review(message: types.Message, state: FSMContext):
    await state.set_state(ReviewState.waiting_for_review_text)
    await message.answer(
        "📝 Пожалуйста, напишите ваш отзыв. Расскажите, что вам понравилось или что можно улучшить.",
        reply_markup=cancel_kb,
    )

@dp.callback_query(F.data == "cancel_review")
async def cancel_review_handler(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await callback.answer()
        return
    await state.clear()
    await callback.message.edit_text("Действие отменено.", reply_markup=None)
    await callback.message.answer("Чем могу помочь?", reply_markup=main_kb)
    await callback.answer()

@dp.message(ReviewState.waiting_for_review_text)
async def process_review_text(message: types.Message, state: FSMContext):
    if not message.text or len(message.text) < 10:
        await message.answer(
            "Пожалуйста, напишите более развернутый отзыв (хотя бы 10 символов).",
            reply_markup=cancel_kb
        )
        return
    await state.update_data(review_text=message.text)
    await state.set_state(ReviewState.waiting_for_rating)
    rating_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐️", callback_data="rating_1"),
                InlineKeyboardButton(text="⭐️⭐️", callback_data="rating_2"),
                InlineKeyboardButton(text="⭐️⭐️⭐️", callback_data="rating_3"),
            ],
            [
                InlineKeyboardButton(text="⭐️⭐️⭐️⭐️", callback_data="rating_4"),
                InlineKeyboardButton(text="⭐️⭐️⭐️⭐️⭐", callback_data="rating_5"),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_review")],
        ]
    )
    await message.answer("✨ Спасибо! Теперь, пожалуйста, оцените нас:", reply_markup=rating_kb)

@dp.callback_query(ReviewState.waiting_for_rating, F.data.startswith("rating_"))
async def process_rating(callback: types.CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[1])
    await state.update_data(rating=rating)
    await state.set_state(ReviewState.waiting_for_anonymity_choice)
    anonymity_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Опубликовать с моим именем", callback_data="anon_no")
            ],
            [
                InlineKeyboardButton(text="🎭 Опубликовать анонимно", callback_data="anon_yes")
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_review")],
        ]
    )
    await callback.message.edit_text("Отлично! Как опубликовать ваш отзыв?", reply_markup=anonymity_kb)
    await callback.answer()

@dp.callback_query(ReviewState.waiting_for_anonymity_choice, F.data.startswith("anon_"))
async def process_anonymity_and_publish(callback: types.CallbackQuery, state: FSMContext):
    is_anonymous = callback.data == "anon_yes"
    user_data = await state.get_data()
    await state.clear()
    rating_stars = "⭐" * user_data["rating"] + "☆" * (5 - user_data["rating"])
    review_text_formatted = (
        f"<b>Новый отзыв!</b> ✨\n\n"
        f"<b>Оценка:</b> {rating_stars}\n\n"
        f"<b>Текст отзыва:</b>\n"
        f"<i>{user_data['review_text']}</i>\n\n"
    )
    if is_anonymous:
        review_text_formatted += "👤 <i>Отзыв оставлен анонимно.</i>"
    else:
        user = callback.from_user
        username = f"@{user.username}" if user.username else "не указан"
        review_text_formatted += (
            f"👤 <b>Автор:</b> {user.full_name} (ID: {user.id}, Username: {username})"
        )
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=review_text_formatted)
        logger.info(f"Отзыв от {callback.from_user.id} успешно отправлен в канал.")
        await callback.message.edit_text(
            "🎉 <b>Спасибо за ваш отзыв!</b>\n\n"
            "Он успешно отправлен. Мы ценим ваше мнение!",
            reply_markup=None,
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке отзыва в канал: {e}")
        await callback.message.edit_text(
            "😔 <b>Произошла ошибка.</b>\n\n"
            "К сожалению, не удалось отправить ваш отзыв. Пожалуйста, свяжитесь с администрацией.",
            reply_markup=None,
        )
    await callback.message.answer("Чем еще могу помочь?", reply_markup=main_kb)
    await callback.answer()

# --- Новая логика запуска ---

### ИЗМЕНЕНИЕ: Функция, которая выполняется при старте приложения
async def on_startup(bot: Bot):
    # Устанавливаем вебхук
    await bot.set_webhook(WEBHOOK_URL, secret_token=BOT_TOKEN)
    logger.info(f"Вебхук установлен на URL: {WEBHOOK_URL}")


### ИЗМЕНЕНИЕ: Функция, которая выполняется при выключении приложения
async def on_shutdown(bot: Bot):
    # Удаляем вебхук
    await bot.delete_webhook()
    logger.info("Вебхук удален.")


### ИЗМЕНЕНИЕ: Главная функция main
def main():
    # Регистрируем функции startup и shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Создаем веб-приложение
    app = web.Application()
    # Создаем обработчик вебхуков
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=BOT_TOKEN,
    )
    # Регистрируем обработчик по нашему пути
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    # Настраиваем и запускаем приложение
    setup_application(app, dp, bot=bot)
    
    # Render предоставляет порт в переменной PORT, по умолчанию 8080
    port = int(os.environ.get('PORT', 8080))
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()