import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Получаем токены из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Проверка на наличие токенов
if not BOT_TOKEN or not CHANNEL_ID:
    raise ValueError(
        "Необходимо установить переменные окружения BOT_TOKEN и CHANNEL_ID"
    )

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()


# --- Клавиатуры ---

# Главное меню
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✍️ Оставить отзыв")],
        [KeyboardButton(text="ℹ️ О нас")],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

# Клавиатура для отмены
cancel_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_review")]]
)

# --- Состояния (FSM) ---

# Создаем класс состояний для процесса отзыва
class ReviewState(StatesGroup):
    waiting_for_review_text = State()
    waiting_for_rating = State()
    waiting_for_anonymity_choice = State()


# --- Обработчики команд ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """
    Обработчик команды /start. Приветствует пользователя и показывает главное меню.
    """
    await message.answer(
        "👋 <b>Добро пожаловать в кофейню «Аромагия»!</b>\n\n"
        "Я ваш личный помощник для сбора отзывов. "
        "Ваше мнение очень важно для нас, ведь оно помогает нам становиться лучше! ☕️✨\n\n"
        "Чтобы оставить отзыв, нажмите на кнопку ниже.",
        reply_markup=main_kb,
    )


# --- Обработчики текстовых сообщений и кнопок ---

@dp.message(F.text == "ℹ️ О нас")
async def about_us(message: types.Message):
    """
    Обработчик кнопки 'О нас'.
    """
    await message.answer(
        "<b>Кофейня «Аромагия»</b> — это уютное место, где каждый глоток кофе "
        "наполнен волшебством.\n\n"
        "Мы используем только свежеобжаренные зерна и готовим напитки с любовью. "
        "Спасибо, что вы с нами! ❤️"
    )


@dp.message(F.text == "✍️ Оставить отзыв")
async def start_review(message: types.Message, state: FSMContext):
    """
    Начало процесса сбора отзыва. Запрашивает текст отзыва.
    """
    await state.set_state(ReviewState.waiting_for_review_text)
    await message.answer(
        "📝 Пожалуйста, напишите ваш отзыв. Расскажите, что вам понравилось или что можно улучшить.",
        reply_markup=cancel_kb,
    )


# --- Обработчики колбэков (нажатий на inline-кнопки) ---

@dp.callback_query(F.data == "cancel_review")
async def cancel_review_handler(callback: types.CallbackQuery, state: FSMContext):
    """
    Отмена процесса оставления отзыва.
    """
    current_state = await state.get_state()
    if current_state is None:
        await callback.answer()
        return

    await state.clear()
    await callback.message.edit_text("Действие отменено.", reply_markup=None)
    await callback.message.answer("Чем могу помочь?", reply_markup=main_kb)
    await callback.answer()


# --- Обработчики состояний ---

@dp.message(ReviewState.waiting_for_review_text)
async def process_review_text(message: types.Message, state: FSMContext):
    """
    Получает текст отзыва и запрашивает оценку.
    """
    if not message.text or len(message.text) < 10:
        await message.answer(
            "Пожалуйста, напишите более развернутый отзыв (хотя бы 10 символов).",
            reply_markup=cancel_kb
        )
        return

    await state.update_data(review_text=message.text)
    await state.set_state(ReviewState.waiting_for_rating)

    # Создаем клавиатуру с оценками
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
    """
    Получает оценку и спрашивает про анонимность.
    """
    rating = int(callback.data.split("_")[1])
    await state.update_data(rating=rating)
    await state.set_state(ReviewState.waiting_for_anonymity_choice)

    anonymity_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 Опубликовать с моим именем", callback_data="anon_no"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎭 Опубликовать анонимно", callback_data="anon_yes"
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_review")],
        ]
    )
    await callback.message.edit_text(
        "Отлично! Как опубликовать ваш отзыв?", reply_markup=anonymity_kb
    )
    await callback.answer()


@dp.callback_query(
    ReviewState.waiting_for_anonymity_choice, F.data.startswith("anon_")
)
async def process_anonymity_and_publish(
    callback: types.CallbackQuery, state: FSMContext
):
    """
    Получает выбор анонимности, формирует и публикует отзыв.
    """
    is_anonymous = callback.data == "anon_yes"
    user_data = await state.get_data()
    await state.clear()

    # Формирование текста отзыва
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

    # Отправка отзыва в канал
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
            "К сожалению, не удалось отправить ваш отзыв. "
            "Возможно, я не добавлен в канал для отзывов или у меня нет прав. "
            "Пожалуйста, свяжитесь с администрацией.",
            reply_markup=None,
        )

    await callback.message.answer("Чем еще могу помочь?", reply_markup=main_kb)
    await callback.answer()


# --- Запуск бота ---
async def main():
    """
    Основная функция для запуска бота.
    """
    # Удаляем вебхук, если он был установлен ранее
    await bot.delete_webhook(drop_pending_updates=True)
    # Запускаем поллинг
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")