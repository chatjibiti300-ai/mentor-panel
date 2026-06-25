import os
import sqlite3
import threading
import asyncio

from flask import Flask, render_template, request, redirect, url_for
from bot import main as bot_main

app = Flask(__name__)
DB_PATH = "database.db"


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

    # groups
    cur.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    )
    """)

    # students
    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        name TEXT,
        username TEXT,
        user_id INTEGER
    )
    """)

    # questions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        question TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


# =========================
# BOT THREAD
# =========================
def run_bot():
    asyncio.run(bot_main())


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
            "SELECT COUNT(*) as cnt FROM students WHERE group_id=?",
            (group["id"],)
        ).fetchone()["cnt"]

        questions_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM questions WHERE group_id=?",
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
        return "Group not found", 404

    students = conn.execute(
        "SELECT * FROM students WHERE group_id=? ORDER BY id DESC",
        (group_id,)
    ).fetchall()

    questions = conn.execute(
        "SELECT * FROM questions WHERE group_id=? ORDER BY id DESC",
        (group_id,)
    ).fetchall()

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
            "INSERT INTO questions (group_id, question) VALUES (?, ?)",
            (group_id, question)
        )
        conn.commit()
        conn.close()

    return redirect(f"/group/{group_id}")


@app.route("/reply", methods=["GET", "POST"])
def reply_page():
    if request.method == "POST":
        # hozircha bo'sh qoldirdim
        return redirect("/")
    return render_template("reply.html")


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
    return redirect("/")


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
    return redirect("/")


# =========================
# START
# =========================
if __name__ == "__main__":
    init_db()

    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    app.run(host="0.0.0.0", port=10000)