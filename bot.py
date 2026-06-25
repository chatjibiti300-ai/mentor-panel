import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from config import BOT_TOKEN, ADMIN_ID
from utils.db import get_connection
from utils.telegram_sender import send_text

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Admin reply rejimi
admin_reply_mode = {}

# =========================
# KEYBOARDS
# =========================

admin_menu = ReplyKeyboardMarkup(
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
        [KeyboardButton(text="✍️ Savol berish")]
    ],
    resize_keyboard=True
)

# =========================
# HELPERS
# =========================

def is_admin(user_id):
    return int(user_id) == int(ADMIN_ID)


def can_send_question():
    conn = get_connection()
    settings = conn.execute("SELECT * FROM settings LIMIT 1").fetchone()
    conn.close()

    if not settings:
        return True

    now_hour = datetime.now().hour
    return settings["start_hour"] <= now_hour < settings["end_hour"]


def get_stats():
    conn = get_connection()
    pending = conn.execute("SELECT COUNT(*) as c FROM questions WHERE status='pending'").fetchone()["c"]
    answered = conn.execute("SELECT COUNT(*) as c FROM questions WHERE status='answered'").fetchone()["c"]
    students = conn.execute("SELECT COUNT(*) as c FROM students").fetchone()["c"]
    groups = conn.execute("SELECT COUNT(*) as c FROM groups").fetchone()["c"]
    conn.close()
    return pending, answered, students, groups


# =========================
# START
# =========================

@dp.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id

    # ADMIN bo'lsa
    if is_admin(user_id):
        await message.answer(
            "👑 Siz admin sifatida kirdingiz.\n\nKerakli bo‘limni tanlang:",
            reply_markup=admin_menu
        )
        return

    # STUDENT uchun start-code bilan kirish
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer("Sizga maxsus guruh linki orqali kirish kerak.")
        return

    start_code = args[1].strip()

    conn = get_connection()
    group = conn.execute(
        "SELECT * FROM groups WHERE start_code=?",
        (start_code,)
    ).fetchone()

    if not group:
        conn.close()
        await message.answer("Noto‘g‘ri yoki eskirgan link.")
        return

    user = message.from_user
    existing = conn.execute(
        "SELECT * FROM students WHERE telegram_id=?",
        (user.id,)
    ).fetchone()

    if not existing:
        conn.execute(
            "INSERT INTO students (telegram_id, full_name, username, group_id) VALUES (?, ?, ?, ?)",
            (user.id, user.full_name, user.username, group["id"])
        )
        conn.commit()

    settings = conn.execute("SELECT * FROM settings LIMIT 1").fetchone()
    conn.close()

    welcome_text = settings["welcome_text"] if settings else "Xush kelibsiz!"
    await message.answer(
        f"{welcome_text}\n\n"
        f"Siz {group['name']} guruhiga biriktirildingiz ✅\n\n"
        "Savolingizni yozing yoki rasm/fayl yuboring.",
        reply_markup=student_menu
    )


# =========================
# ADMIN MENU
# =========================

@dp.message(F.text == "🌐 Admin panelni ochish")
async def open_admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "🌐 Admin panel linki:\n\nhttp://127.0.0.1:5000\n\n"
        "Agar siz shu kompyuterdagi Telegram Desktopdan bossangiz, panel browserda ochiladi."
    )


@dp.message(F.text == "🏠 Bosh menu")
async def admin_home(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🏠 Admin bosh menu", reply_markup=admin_menu)


@dp.message(F.text == "📊 Statistika")
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    pending, answered, students, groups = get_stats()

    text = (
        "📊 <b>Statistika</b>\n\n"
        f"📩 Pending savollar: <b>{pending}</b>\n"
        f"✅ Answered savollar: <b>{answered}</b>\n"
        f"👥 Studentlar: <b>{students}</b>\n"
        f"📦 Guruhlar: <b>{groups}</b>"
    )
    await message.answer(text, parse_mode="HTML")


@dp.message(F.text == "👥 Guruhlar")
async def admin_groups(message: Message):
    if not is_admin(message.from_user.id):
        return

    conn = get_connection()
    groups = conn.execute("SELECT * FROM groups ORDER BY id DESC").fetchall()
    conn.close()

    if not groups:
        await message.answer("Hali guruhlar yo‘q.")
        return

    text = "👥 <b>Guruhlar ro‘yxati</b>\n\n"
    for g in groups:
        text += f"• <b>{g['name']}</b>\n{g['invite_link']}\n\n"

    await message.answer(text, parse_mode="HTML")


@dp.message(F.text == "⚙️ Sozlamalar")
async def admin_settings(message: Message):
    if not is_admin(message.from_user.id):
        return

    conn = get_connection()
    settings = conn.execute("SELECT * FROM settings LIMIT 1").fetchone()
    conn.close()

    if not settings:
        await message.answer("Sozlamalar topilmadi.")
        return

    text = (
        "⚙️ <b>Hozirgi sozlamalar</b>\n\n"
        f"🕒 Savol vaqti: <b>{settings['start_hour']}:00 - {settings['end_hour']}:00</b>\n"
        f"💬 Welcome text:\n<code>{settings['welcome_text']}</code>"
    )
    await message.answer(text, parse_mode="HTML")


@dp.message(F.text == "📩 Savollar")
async def admin_questions(message: Message):
    if not is_admin(message.from_user.id):
        return

    conn = get_connection()
    questions = conn.execute("""
        SELECT questions.*, students.full_name, students.telegram_id, groups.name as group_name
        FROM questions
        JOIN students ON questions.student_id = students.id
        JOIN groups ON questions.group_id = groups.id
        WHERE questions.status='pending'
        ORDER BY questions.id DESC
        LIMIT 15
    """).fetchall()
    conn.close()

    if not questions:
        await message.answer("Hozir pending savollar yo‘q.")
        return

    text = "📩 <b>Pending savollar</b>\n\n"
    for q in questions:
        q_text = q["question_text"] if q["question_text"] else "Matnsiz savol"
        text += (
            f"🆔 <b>{q['id']}</b>\n"
            f"👤 {q['full_name']}\n"
            f"👥 {q['group_name']}\n"
            f"❓ {q_text}\n"
            f"🕒 {q['created_at']}\n\n"
        )

    text += "Javob berish uchun savol ID sini yuboring.\nMasalan: <code>12</code>"
    await message.answer(text, parse_mode="HTML")


# =========================
# ADMIN REPLY FLOW
# =========================

@dp.message(F.text.regexp(r"^\d+$"))
async def admin_select_question(message: Message):
    if not is_admin(message.from_user.id):
        return

    qid = int(message.text.strip())

    conn = get_connection()
    question = conn.execute("""
        SELECT questions.*, students.full_name, students.telegram_id, groups.name as group_name
        FROM questions
        JOIN students ON questions.student_id = students.id
        JOIN groups ON questions.group_id = groups.id
        WHERE questions.id=? AND questions.status='pending'
    """, (qid,)).fetchone()
    conn.close()

    if not question:
        await message.answer("Bunday pending savol topilmadi.")
        return

    admin_reply_mode[message.from_user.id] = qid

    q_text = question["question_text"] if question["question_text"] else "Matnsiz savol"

    text = (
        f"✍️ <b>Javob berish rejimi yoqildi</b>\n\n"
        f"🆔 {question['id']}\n"
        f"👤 {question['full_name']}\n"
        f"👥 {question['group_name']}\n"
        f"❓ {q_text}\n\n"
        f"Endi shu chatga javob matnini yozing."
    )
    await message.answer(text, parse_mode="HTML")


# =========================
# UNIVERSAL HANDLER
# =========================

@dp.message()
async def universal_handler(message: Message):
    user_id = message.from_user.id

    # =========================
    # ADMIN reply mode
    # =========================
    if is_admin(user_id) and user_id in admin_reply_mode:
        qid = admin_reply_mode[user_id]
        answer_text = message.text if message.text else None

        if not answer_text:
            await message.answer("Javob matnini yozing.")
            return

        conn = get_connection()
        question = conn.execute("""
            SELECT questions.*, students.telegram_id
            FROM questions
            JOIN students ON questions.student_id = students.id
            WHERE questions.id=?
        """, (qid,)).fetchone()

        if not question:
            conn.close()
            await message.answer("Savol topilmadi.")
            admin_reply_mode.pop(user_id, None)
            return

        await send_text(question["telegram_id"], answer_text)

        conn.execute("""
            UPDATE questions
            SET status='answered',
                answer_text=?,
                answered_at=?
            WHERE id=?
        """, (
            answer_text,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            qid
        ))
        conn.commit()
        conn.close()

        admin_reply_mode.pop(user_id, None)
        await message.answer("✅ Javob studentga yuborildi.", reply_markup=admin_menu)
        return

    # =========================
    # ADMIN oddiy xabar yuborsa
    # =========================
    if is_admin(user_id):
        await message.answer("Admin menyudan kerakli bo‘limni tanlang.", reply_markup=admin_menu)
        return

    # =========================
    # STUDENT savol yuborishi
    # =========================
    conn = get_connection()
    student = conn.execute(
        "SELECT * FROM students WHERE telegram_id=?",
        (user_id,)
    ).fetchone()

    if not student:
        conn.close()
        return

    if not can_send_question():
        conn.close()
        await message.answer("Savol berish vaqti hozir yopiq. Belgilangan vaqtda qayta urinib ko‘ring.")
        return

    # MUHIM FIX: matn / caption olish
    text = None
    file_id = None
    file_type = None

    # oddiy matn
    if message.text:
        text = message.text

    # rasm + caption
    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
        if message.caption:
            text = message.caption

    # fayl + caption
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"
        if message.caption:
            text = message.caption

    # video + caption
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
        if message.caption:
            text = message.caption

    conn.execute(
        "INSERT INTO questions (student_id, group_id, question_text, file_id, file_type) VALUES (?, ?, ?, ?, ?)",
        (student["id"], student["group_id"], text, file_id, file_type)
    )
    conn.commit()
    conn.close()

    await message.answer("Savolingiz qabul qilindi ✅", reply_markup=student_menu)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
   async def main():
    print("Bot ishga tushdi")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())