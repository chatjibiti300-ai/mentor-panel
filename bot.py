import asyncio
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from config import BOT_TOKEN, DB_PATH

# =========================
# SETTINGS
# =========================
PANEL_URL = "https://mentor-panel-web.onrender.com"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================
# DB
# =========================
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_groups():
    conn = get_connection()
    groups = conn.execute("SELECT * FROM groups ORDER BY id DESC").fetchall()
    conn.close()
    return groups


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


def get_stats():
    conn = get_connection()

    groups_count = conn.execute("SELECT COUNT(*) AS cnt FROM groups").fetchone()["cnt"]
    students_count = conn.execute("SELECT COUNT(*) AS cnt FROM students").fetchone()["cnt"]
    questions_count = conn.execute("SELECT COUNT(*) AS cnt FROM questions").fetchone()["cnt"]

    conn.close()
    return groups_count, students_count, questions_count


# =========================
# KEYBOARDS
# =========================
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🌐 Admin panelni ochish")],
        [KeyboardButton(text="📩 Savollar"), KeyboardButton(text="👥 Guruhlar")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="⚙️ Sozlamalar")],
        [KeyboardButton(text="🏠 Bosh menu")]
    ],
    resize_keyboard=True
)

student_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Savol yuborish")],
        [KeyboardButton(text="🏠 Bosh menu")]
    ],
    resize_keyboard=True
)


# =========================
# HANDLERS
# =========================
@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Kerakli bo‘limni tanlang:",
        reply_markup=main_menu
    )


@dp.message(F.text == "🏠 Bosh menu")
async def home_handler(message: Message):
    await message.answer(
        "Bosh menu:",
        reply_markup=main_menu
    )


@dp.message(F.text == "🌐 Admin panelni ochish")
async def admin_panel_handler(message: Message):
    await message.answer(
        f"🌐 Admin panel linki:\n\n{PANEL_URL}\n\n"
        f"Agar bossangiz panel brauzerda ochiladi."
    )


@dp.message(F.text == "👥 Guruhlar")
async def groups_handler(message: Message):
    groups = get_groups()

    if not groups:
        await message.answer("Hozircha guruhlar yo‘q.")
        return

    text = "👥 Guruhlar ro‘yxati:\n\n"
    for i, group in enumerate(groups, start=1):
        text += f"{i}. {group['name']}\n"

    await message.answer(text)


@dp.message(F.text == "📊 Statistika")
async def stats_handler(message: Message):
    groups_count, students_count, questions_count = get_stats()

    text = (
        "📊 Statistika:\n\n"
        f"👥 Guruhlar soni: {groups_count}\n"
        f"🎓 Studentlar soni: {students_count}\n"
        f"📩 Savollar soni: {questions_count}"
    )
    await message.answer(text)


@dp.message(F.text == "⚙️ Sozlamalar")
async def settings_handler(message: Message):
    await message.answer(
        "⚙️ Sozlamalar bo‘limi.\n\n"
        f"Bot username: @{bot.username if bot.username else 'aniqlanmadi'}\n"
        f"Admin panel: {PANEL_URL}"
    )


@dp.message(F.text == "📩 Savollar")
async def savollar_handler(message: Message):
    student = get_student(message.from_user.id)
    if not student:
        student = save_student(
            user_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username
        )

    if not student:
        await message.answer(
            "Hozircha guruh yaratilmagan. Avval paneldan kamida 1 ta guruh yarating."
        )
        return

    await message.answer(
        "Savolingizni yuborish uchun pastdagi tugmani bosing:",
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

    # menyu textlarini savol deb saqlab yubormaslik uchun
    blocked_texts = {
        "🌐 Admin panelni ochish",
        "📩 Savollar",
        "👥 Guruhlar",
        "📊 Statistika",
        "⚙️ Sozlamalar",
        "🏠 Bosh menu",
        "Savol yuborish"
    }

    if text in blocked_texts:
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

    await message.answer(
        "Savolingiz qabul qilindi ✅",
        reply_markup=main_menu
    )


# =========================
# MAIN
# =========================
async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
