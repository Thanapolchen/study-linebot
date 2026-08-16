import os
import re
import sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL")

class DictCursorWrapper:
    def __init__(self, cursor, conn):
        self.cursor = cursor
        self.conn = conn

    def execute(self, query, params=None):
        # 1. แปลง syntax INSERT OR IGNORE ของ SQLite ให้เป็น PostgreSQL
        if re.search(r"INSERT\s+OR\s+IGNORE\s+INTO", query, re.IGNORECASE):
            query = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", query, flags=re.IGNORECASE)
            if "ON CONFLICT" not in query.upper():
                query = f"{query.rstrip(';')} ON CONFLICT DO NOTHING;"

        # 2. แปลง ? เป็น %s สำหรับ psycopg2
        if params is not None:
            query = query.replace("?", "%s")
            self.cursor.execute(query, params)
        else:
            self.cursor.execute(query)
        return self

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    @property
    def lastrowid(self):
        return getattr(self.cursor, "lastrowid", None)

    def close(self):
        self.cursor.close()

class DBConnectionWrapper:
    def __init__(self, conn, is_postgres=False):
        self.conn = conn
        self.is_postgres = is_postgres

    def cursor(self):
        if self.is_postgres:
            import psycopg2.extras
            return DictCursorWrapper(self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor), self.conn)
        return self.conn.cursor()

    def execute(self, query, params=None):
        cur = self.cursor()
        return cur.execute(query, params)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

def get_connection():
    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        return DBConnectionWrapper(conn, is_postgres=True)
    else:
        conn = sqlite3.connect("study_assistant.db")
        conn.row_factory = sqlite3.Row
        return DBConnectionWrapper(conn, is_postgres=False)

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    auto_inc = "SERIAL PRIMARY KEY" if DATABASE_URL else "INTEGER PRIMARY KEY AUTOINCREMENT"

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            line_user_id TEXT PRIMARY KEY,
            active_semester_id INTEGER
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS semesters (
            id {auto_inc},
            line_user_id TEXT,
            name TEXT
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS subjects (
            id {auto_inc},
            semester_id INTEGER,
            name TEXT,
            code TEXT,
            room TEXT,
            max_absent INTEGER DEFAULT 3
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS assignments (
            id {auto_inc},
            subject_id INTEGER,
            title TEXT,
            due_datetime TEXT,
            is_done INTEGER DEFAULT 0
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS reminders (
            id {auto_inc},
            line_user_id TEXT,
            message TEXT,
            remind_datetime TEXT,
            is_sent INTEGER DEFAULT 0
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS leaves (
            id {auto_inc},
            subject_id INTEGER,
            leave_date TEXT,
            reason TEXT
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS canceled_classes (
            id {auto_inc},
            subject_id INTEGER,
            cancel_date TEXT,
            note TEXT
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS special_events (
            id {auto_inc},
            line_user_id TEXT,
            title TEXT,
            event_datetime TEXT
        )
    """)

    conn.commit()
    conn.close()