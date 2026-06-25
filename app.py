import os
import sqlite3
import threading
import asyncio

from flask import Flask, render_template, request, redirect, url_for
from bot import main as bot_main

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")


# =========================
# DATABASE
# =========================
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        name TEXT,
        username TEXT,
        user_id INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        student_id INTEGER,
        question TEXT NOT NULL,
        answer TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


# =========================
# BOT THREAD
# =========================
def run_bot():
    asyncio.run(bot_main())


bot_started = False

def start_bot_once():
    global bot_started
    if not bot_started:
        t = threading.Thread(target=run_bot, daemon=True)
        t.start()
        bot_started = True


# =========================
# APP STARTUP
# =========================
init_db()
start_bot_once()


# =========================
# ROUTES
# =========================
@app.route("/")
def dashboard():
    conn = get_connection()
    groups = conn.execute("SELECT * FROM groups ORDER BY id DESC").fetchall()

    groups_data = []
    for group in groups:
        students_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM students WHERE group_id=?",
            (group["id"],)
        ).fetchone()["cnt"]

        questions_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM questions WHERE group_id=?",
            (group["id"],)
        ).fetchone()["cnt"]

        groups_data.append({
            "id": group["id"],
            "name": group["name"],
            "students_count": students_count,
            "questions_count": questions_count
        })

    conn.close()
    return render_template("dashboard.html", groups=groups_data)


@app.route("/create-group", methods=["GET", "POST"])
def create_group():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            conn = get_connection()
            conn.execute("INSERT INTO groups (name) VALUES (?)", (name,))
            conn.commit()
            conn.close()
        return redirect(url_for("dashboard"))

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
        return "Group not found", 404

    students = conn.execute(
        "SELECT * FROM students WHERE group_id=? ORDER BY id DESC",
        (group_id,)
    ).fetchall()

    questions = conn.execute("""
        SELECT q.*, s.name AS student_name, s.username AS student_username
        FROM questions q
        LEFT JOIN students s ON q.student_id = s.id
        WHERE q.group_id=?
        ORDER BY q.id DESC
    """, (group_id,)).fetchall()

    conn.close()

    return render_template(
        "group_detail.html",
        group=group,
        students=students,
        questions=questions
    )


@app.route("/group/<int:group_id>/add-question", methods=["POST"])
def add_question(group_id):
    question = request.form.get("question", "").strip()
    if question:
        conn = get_connection()
        conn.execute(
            "INSERT INTO questions (group_id, student_id, question) VALUES (?, ?, ?)",
            (group_id, None, question)
        )
        conn.commit()
        conn.close()

    return redirect(url_for("group_detail", group_id=group_id))


@app.route("/reply/<int:question_id>", methods=["POST"])
def reply_question(question_id):
    answer = request.form.get("answer", "").strip()

    conn = get_connection()
    q = conn.execute(
        "SELECT * FROM questions WHERE id=?",
        (question_id,)
    ).fetchone()

    if q and answer:
        conn.execute(
            "UPDATE questions SET answer=? WHERE id=?",
            (answer, question_id)
        )
        conn.commit()

    group_id = q["group_id"] if q else 0
    conn.close()

    if group_id:
        return redirect(url_for("group_detail", group_id=group_id))
    return redirect(url_for("dashboard"))


@app.route("/settings")
def settings():
    settings_data = {
        "bot_username": os.getenv("BOT_USERNAME", ""),
        "has_token": bool(os.getenv("BOT_TOKEN"))
    }
    return render_template("settings.html", settings=settings_data)


@app.route("/delete-group/<int:group_id>")
def delete_group(group_id):
    conn = get_connection()
    conn.execute("DELETE FROM groups WHERE id=?", (group_id,))
    conn.execute("DELETE FROM questions WHERE group_id=?", (group_id,))
    conn.execute("DELETE FROM students WHERE group_id=?", (group_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/rename-group/<int:group_id>", methods=["POST"])
def rename_group(group_id):
    new_name = request.form.get("new_name", "").strip()
    if new_name:
        conn = get_connection()
        conn.execute(
            "UPDATE groups SET name=? WHERE id=?",
            (new_name, group_id)
        )
        conn.commit()
        conn.close()
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)