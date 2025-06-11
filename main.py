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
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from dotenv import load_dotenv

load_dotenv()

# --- Настройки ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") 

# Настройки для вебхука
# BASE_WEBHOOK_URL должен быть вашим URL с Render, например "https://my-coffee-bot.onrender.com"
BASE_WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL")
# Путь вебхука НЕ должен содержать токен, если вы используете secret_token.
# Это безопаснее и является лучшей практикой.
WEBHOOK_PATH = "/webhook" 
WEBHOOK_URL = f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}"

# Проверка переменных
if not all([BOT_TOKEN, CHANNEL_ID, WEBHOOK_SECRET, BASE_WEBHOOK_URL]):
    raise ValueError(
        "Необходимо установить переменные окружения: "
        "BOT_TOKEN, CHANNEL_ID, WEBHOOK_SECRET, RENDER_EXTERNAL_URL"
    )

# Настройка логирования
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# --- Клавиатуры ---
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

# --- Состояния ---
class ReviewState(StatesGroup):
    waiting_for_review_text = State()
    waiting_for_rating = State()
    waiting_for_anonymity_choice = State()


# --- Обработчики сообщений и колбэков ---
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


# --- Логика запуска и веб-сервер ---

# <<< ИЗМЕНЕНИЕ 1: Добавляем обработчик для UptimeRobot >>>
async def ping_server(request):
    """Отвечает на 'ping' запросы от сервисов мониторинга."""
    return web.Response(text="ok")


async def on_startup(bot: Bot):
    await bot.set_webhook(url=WEBHOOK_URL, secret_token=WEBHOOK_SECRET)
    logger.info(f"Вебхук установлен на URL: {WEBHOOK_URL}")


async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    logger.info("Вебхук удален.")


def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()

    # <<< ИЗМЕНЕНИЕ 2: Регистрируем новый маршрут для пинга >>>
    app.router.add_get("/ping", ping_server)

    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    )
    # Регистрируем основной обработчик для Telegram
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)
    
    port = int(os.environ.get('PORT', 8080))
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()