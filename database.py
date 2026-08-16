import os
import sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL")

# Wrapper class เพื่อให้ psycopg2 เข้าถึงข้อมูลแบบ dict / row_factory เหมือน SQLite
class DictCursorWrapper:
    def __init__(self, cursor, conn):
        self.cursor = cursor
        self.conn = conn

    def execute(self, query, params=None):
        if params is not None:
            # แปลง parameter ? ของ SQLite เป็น %s ของ PostgreSQL
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

    # เลือก Syntax AUTO INCREMENT ตามประเภท Database
    auto_inc = "SERIAL PRIMARY KEY" if DATABASE_URL else "INTEGER PRIMARY KEY AUTOINCREMENT"

    # 1. ตารางผู้ใช้
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            line_user_id TEXT PRIMARY KEY,
            active_semester_id INTEGER
        )
    """)

    # 2. ตารางเทอม
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS semesters (
            id {auto_inc},
            line_user_id TEXT,
            name TEXT
        )
    """)

    # 3. ตารางวิชา
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

    # 4. ตารางงาน/การบ้าน
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS assignments (
            id {auto_inc},
            subject_id INTEGER,
            title TEXT,
            due_datetime TEXT,
            is_done INTEGER DEFAULT 0
        )
    """)

    # 5. ตารางแจ้งเตือน
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS reminders (
            id {auto_inc},
            line_user_id TEXT,
            message TEXT,
            remind_datetime TEXT,
            is_sent INTEGER DEFAULT 0
        )
    """)

    # 6. ตารางการลา
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS leaves (
            id {auto_inc},
            subject_id INTEGER,
            leave_date TEXT,
            reason TEXT
        )
    """)

    # 7. ตารางยกคลาส
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS canceled_classes (
            id {auto_inc},
            subject_id INTEGER,
            cancel_date TEXT,
            note TEXT
        )
    """)

    # 8. ตารางอีเวนต์/กิจกรรมพิเศษ
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