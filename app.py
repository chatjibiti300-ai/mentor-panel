from flask import Flask, render_template, request, redirect
from utils.db import init_db, get_connection
from config import BOT_USERNAME, BOT_TOKEN
import random
import string
from datetime import datetime
import requests
import os
from werkzeug.utils import secure_filename

from utils.telegram_sender import (
    send_text,
    send_photo,
    send_document,
    send_local_photo,
    send_local_document
)

app = Flask(__name__)

# Upload papka
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def generate_code(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def get_file_url(file_id):
    if not file_id:
        return None

    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
            params={"file_id": file_id},
            timeout=15
        ).json()

        if not resp.get("ok"):
            print("TELEGRAM getFile ERROR:", resp)
            return None

        file_path = resp["result"]["file_path"]
        return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    except Exception as e:
        print("GET_FILE_URL ERROR:", e)
        return None


@app.route("/")
def dashboard():
    conn = get_connection()

    groups = conn.execute("SELECT * FROM groups ORDER BY id DESC").fetchall()

    pending_count = conn.execute(
        "SELECT COUNT(*) as c FROM questions WHERE status='pending'"
    ).fetchone()["c"]

    answered_count = conn.execute(
        "SELECT COUNT(*) as c FROM questions WHERE status='answered'"
    ).fetchone()["c"]

    total_students = conn.execute(
        "SELECT COUNT(*) as c FROM students"
    ).fetchone()["c"]

    recent_questions = conn.execute("""
        SELECT questions.*, students.full_name, groups.name as group_name
        FROM questions
        JOIN students ON questions.student_id = students.id
        JOIN groups ON questions.group_id = groups.id
        ORDER BY questions.id DESC
        LIMIT 8
    """).fetchall()

    conn.close()
    return render_template(
        "dashboard.html",
        groups=groups,
        pending_count=pending_count,
        answered_count=answered_count,
        total_students=total_students,
        recent_questions=recent_questions
    )


@app.route("/create-group", methods=["GET", "POST"])
def create_group():
    if request.method == "POST":
        group_name = request.form.get("group_name", "").strip()

        if group_name:
            code = "grp_" + generate_code()
            invite_link = f"https://t.me/{BOT_USERNAME}?start={code}"

            conn = get_connection()
            conn.execute(
                "INSERT INTO groups (name, start_code, invite_link) VALUES (?, ?, ?)",
                (group_name, code, invite_link)
            )
            conn.commit()
            conn.close()
            return redirect("/")

    return render_template("create_group.html")


@app.route("/group/<int:group_id>")
def group_detail(group_id):
    conn = get_connection()

    group = conn.execute(
        "SELECT * FROM groups WHERE id=?",
        (group_id,)
    ).fetchone()

    if not group:
        conn.close()
        return redirect("/")

    pending_questions = conn.execute("""
        SELECT questions.*, students.full_name
        FROM questions
        JOIN students ON questions.student_id = students.id
        WHERE questions.group_id=? AND questions.status='pending'
        ORDER BY questions.id DESC
    """, (group_id,)).fetchall()

    answered_questions = conn.execute("""
        SELECT questions.*, students.full_name
        FROM questions
        JOIN students ON questions.student_id = students.id
        WHERE questions.group_id=? AND questions.status='answered'
        ORDER BY questions.id DESC
    """, (group_id,)).fetchall()

    conn.close()
    return render_template(
        "group_detail.html",
        group=group,
        pending_questions=pending_questions,
        answered_questions=answered_questions,
        get_file_url=get_file_url
    )


@app.route("/reply/<int:question_id>", methods=["GET", "POST"])
def reply_question(question_id):
    conn = get_connection()

    question = conn.execute("""
        SELECT questions.*, students.telegram_id, students.full_name
        FROM questions
        JOIN students ON questions.student_id = students.id
        WHERE questions.id=?
    """, (question_id,)).fetchone()

    if not question:
        conn.close()
        return redirect("/")

    if request.method == "POST":
        import asyncio

        answer = request.form.get("answer", "").strip()
        answer_file_id = request.form.get("answer_file_id", "").strip()
        answer_file_type = request.form.get("answer_file_type", "").strip()
        uploaded_file = request.files.get("answer_file")

        saved_answer_file_id = None
        saved_answer_file_type = None

        print("===== REPLY DEBUG START =====")
        print("QUESTION ID:", question_id)
        print("STUDENT NAME:", question["full_name"])
        print("TELEGRAM ID:", question["telegram_id"])
        print("ANSWER:", answer)
        print("ANSWER FILE ID:", answer_file_id)
        print("ANSWER FILE TYPE:", answer_file_type)
        print("UPLOADED FILE:", uploaded_file.filename if uploaded_file and uploaded_file.filename else "NO FILE")

        try:
            # 1) Kompyuterdan upload qilingan rasm/fayl bo'lsa
            if uploaded_file and uploaded_file.filename:
                filename = secure_filename(uploaded_file.filename)
                save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                uploaded_file.save(save_path)

                ext = filename.lower().split(".")[-1]
                image_exts = {"jpg", "jpeg", "png", "webp"}

                print("LOCAL FILE SAVED:", save_path)

                if ext in image_exts:
                    asyncio.run(
                        send_local_photo(
                            question["telegram_id"],
                            save_path,
                            answer if answer else None
                        )
                    )
                    saved_answer_file_type = "photo"
                    print("PHOTO SENT SUCCESS")
                else:
                    asyncio.run(
                        send_local_document(
                            question["telegram_id"],
                            save_path,
                            answer if answer else None
                        )
                    )
                    saved_answer_file_type = "document"
                    print("DOCUMENT SENT SUCCESS")

            # 2) Telegram file_id orqali yuborish
            elif answer_file_id and answer_file_type == "photo":
                asyncio.run(
                    send_photo(
                        question["telegram_id"],
                        answer_file_id,
                        answer if answer else None
                    )
                )
                saved_answer_file_id = answer_file_id
                saved_answer_file_type = "photo"
                print("PHOTO BY FILE_ID SENT SUCCESS")

            elif answer_file_id and answer_file_type == "document":
                asyncio.run(
                    send_document(
                        question["telegram_id"],
                        answer_file_id,
                        answer if answer else None
                    )
                )
                saved_answer_file_id = answer_file_id
                saved_answer_file_type = "document"
                print("DOCUMENT BY FILE_ID SENT SUCCESS")

            # 3) Faqat text
            elif answer:
                asyncio.run(send_text(question["telegram_id"], answer))
                print("TEXT SENT SUCCESS")

            else:
                print("HECH NIMA YUBORILMADI: text ham yo'q, file ham yo'q")

        except Exception as e:
            print("===== SEND ERROR =====")
            print("ERROR:", str(e))
            print("======================")

        # Javobni tarixga yozish
        conn.execute("""
            UPDATE questions
            SET status='answered',
                answer_text=?,
                answer_file_id=?,
                answer_file_type=?,
                answered_at=?
            WHERE id=?
        """, (
            answer if answer else None,
            saved_answer_file_id,
            saved_answer_file_type,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            question_id
        ))
        conn.commit()

        print("QUESTION STATUS UPDATED TO ANSWERED")
        print("===== REPLY DEBUG END =====")

        group_id = question["group_id"]
        conn.close()
        return redirect(f"/group/{group_id}")

    conn.close()
    return render_template(
        "reply.html",
        question=question,
        get_file_url=get_file_url
    )


@app.route("/settings", methods=["GET", "POST"])
def settings():
    conn = get_connection()

    if request.method == "POST":
        start_hour = request.form.get("start_hour")
        end_hour = request.form.get("end_hour")
        welcome_text = request.form.get("welcome_text")

        conn.execute("""
            UPDATE settings
            SET start_hour=?, end_hour=?, welcome_text=?
            WHERE id=1
        """, (start_hour, end_hour, welcome_text))
        conn.commit()
        conn.close()
        return redirect("/settings")

    settings_data = conn.execute("SELECT * FROM settings LIMIT 1").fetchone()
    conn.close()
    return render_template("settings.html", settings=settings_data)


@app.route("/delete-group/<int:group_id>")
def delete_group(group_id):
    conn = get_connection()
    conn.execute("DELETE FROM groups WHERE id=?", (group_id,))
    conn.execute("DELETE FROM questions WHERE group_id=?", (group_id,))
    conn.execute("DELETE FROM students WHERE group_id=?", (group_id,))
    conn.commit()
    conn.close()
    return redirect("/")


@app.route("/rename-group/<int:group_id>", methods=["POST"])
def rename_group(group_id):
    new_name = request.form.get("new_name", "").strip()
    if new_name:
        conn = get_connection()
        conn.execute("UPDATE groups SET name=? WHERE id=?", (new_name, group_id))
        conn.commit()
        conn.close()
    return redirect("/")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)