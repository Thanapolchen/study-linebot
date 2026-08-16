import sqlite3

DB_NAME = "study_assistant.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. ตารางผู้ใช้
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            line_user_id TEXT PRIMARY KEY,
            active_semester_id INTEGER
        )
    """)
    
    # 2. ตารางเทอม
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS semesters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_user_id TEXT,
            name TEXT
        )
    """)
    
    # 3. ตารางวิชา
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            semester_id INTEGER,
            name TEXT,
            code TEXT,
            room TEXT,
            max_absent INTEGER DEFAULT 3
        )
    """)
    
    # 4. ตารางงาน/การบ้าน
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER,
            title TEXT,
            due_datetime TEXT,
            is_done INTEGER DEFAULT 0
        )
    """)
    
    # 5. ตารางแจ้งเตือน
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_user_id TEXT,
            message TEXT,
            remind_datetime TEXT,
            is_sent INTEGER DEFAULT 0
        )
    """)
    
    # 6. ตารางการลา
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER,
            leave_date TEXT,
            reason TEXT
        )
    """)

    # 7. ตารางยกคลาส
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS canceled_classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER,
            cancel_date TEXT,
            note TEXT
        )
    """)

    # 8. ตารางอีเวนต์/กิจกรรมพิเศษ
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS special_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_user_id TEXT,
            title TEXT,
            event_datetime TEXT
        )
    """)
    
    conn.commit()
    conn.close()