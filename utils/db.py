import sqlite3

DB_NAME = "database.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        start_code TEXT NOT NULL,
        invite_link TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        full_name TEXT,
        username TEXT,
        group_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        group_id INTEGER NOT NULL,
        question_text TEXT,
        file_id TEXT,
        file_type TEXT,
        status TEXT DEFAULT 'pending',
        answer_text TEXT,
        answer_file_id TEXT,
        answer_file_type TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        answered_at TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        start_hour INTEGER DEFAULT 10,
        end_hour INTEGER DEFAULT 20,
        daily_limit INTEGER DEFAULT 3,
        welcome_text TEXT DEFAULT 'Xush kelibsiz!'
    )
    """)

    # default settings
    existing = cur.execute("SELECT * FROM settings LIMIT 1").fetchone()
    if not existing:
        cur.execute("""
        INSERT INTO settings (start_hour, end_hour, daily_limit, welcome_text)
        VALUES (10, 20, 3, 'Xush kelibsiz! Savolingizni yuboring.')
        """)

    conn.commit()
    conn.close()