import asyncio
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from config import BOT_TOKEN, DB_PATH

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================
# DB
# =========================
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_first_group():
    conn = get_connection()
    group = conn.execute("SELECT * FROM groups ORDER BY id ASC LIMIT 1").fetchone()
    conn.close()
    return group


def get_student(user_id: int):
    conn = get_connection()
    student = conn.execute(
        "SELECT * FROM students WHERE user_id=?",
        (user_id,)
    ).fetchone()
    conn.close()
    return student


def save_student(user_id: int, full_name: str, username: str | None):
    existing = get_student(user_id)
    if existing:
        return existing

    group = get_first_group()
    if not group:
        return None

    conn = get_connection()
    conn.execute(
        "INSERT INTO students (group_id, name, username, user_id) VALUES (?, ?, ?, ?)",
        (group["id"], full_name, username or "", user_id)
    )
    conn.commit()

    student = conn.execute(
        "SELECT * FROM students WHERE user_id=?",
        (user_id,)
    ).fetchone()
    conn.close()
    return student


def save_question(group_id: int, question_text: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO questions (group_id, question) VALUES (?, ?)",
        (group_id, question_text)
    )
    conn.commit()
    conn.close()


# =========================
# KEYBOARD
# =========================
student_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Savol yuborish")]
    ],
    resize_keyboard=True
)


# =========================
# HANDLERS
# =========================
@dp.message(CommandStart())
async def start_handler(message: Message):
    student = save_student(
        user_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username
    )

    if not student:
        await message.answer(
            "Hozircha guruh yaratilmagan. Avval paneldan guruh yarating."
        )
        return

    await message.answer(
        "Assalomu alaykum! Mentor botga xush kelibsiz.\n\nSavolingizni yuborishingiz mumkin.",
        reply_markup=student_menu
    )


@dp.message(F.text == "Savol yuborish")
async def ask_button_handler(message: Message):
    student = get_student(message.from_user.id)
    if not student:
        student = save_student(
            user_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username
        )

    if not student:
        await message.answer("Avval paneldan kamida 1 ta guruh yarating.")
        return

    await message.answer("Savolingizni bitta xabar qilib yuboring.")


@dp.message(F.text)
async def text_handler(message: Message):
    text = (message.text or "").strip()

    if text == "Savol yuborish":
        return

    student = get_student(message.from_user.id)
    if not student:
        student = save_student(
            user_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username
        )

    if not student:
        await message.answer("Avval paneldan guruh yarating.")
        return

    save_question(student["group_id"], text)

    await message.answer("Savolingiz qabul qilindi ✅", reply_markup=student_menu)


# =========================
# MAIN
# =========================
async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

