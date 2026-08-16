import os
import re
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from apscheduler.schedulers.background import BackgroundScheduler
import database

CHANNEL_ACCESS_TOKEN = "I3ZF6aCSNn/2UTPAU5Cr6Q73zM8SDmI4v2GWDMTOjhflrCNLHMWZH3YDY5GfRSaXBXEkYob3rx9/SamMZBAProrrpVTQc3ITFFZUOpxi6GnZ91wPsspssTcDnoi5zmnvc/sXoQUpUThkW9923EF+SAdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "d1c733d4d8b4537d678e80d10e0faa25"

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

app = FastAPI()
database.init_db()

# --- ระบบเช็กการแจ้งเตือนอัตโนมัติ (Scheduler) ---
def check_reminders():
    conn = database.get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    cursor.execute("""
        SELECT id, line_user_id, message FROM reminders 
        WHERE remind_datetime <= ? AND is_sent = 0
    """, (now_str,))
    rows = cursor.fetchall()
    
    for row in rows:
        try:
            line_bot_api.push_message(row["line_user_id"], TextSendMessage(text=f"🔔 แจ้งเตือน: {row['message']}"))
            cursor.execute("UPDATE reminders SET is_sent = 1 WHERE id = ?", (row["id"],))
            conn.commit()
        except Exception as e:
            print("Push error:", e)
    conn.close()

scheduler = BackgroundScheduler(timezone="Asia/Bangkok")
scheduler.add_job(check_reminders, "interval", seconds=30)
scheduler.start()

# --- Root & Webhook Endpoint ---
@app.get("/")
def root():
    return {"status": "ok", "message": "Study Assistant Bot is running!"}
@app.api_route("/callback", methods=["GET", "POST"])
async def callback(request: Request):
    if request.method == "GET":
        return {"status": "ok", "message": "Callback endpoint is ready!"}
    
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_str = body.decode("utf-8")

    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        print(f"Error handling callback: {e}")
        return "OK"
    return "OK"

HELP_TEXT = """🤖 เมนูคำสั่ง Study Assistant:

🗂️ เทอม
• +เทอม [ชื่อเทอม] (เช่น +เทอม 1/2569)
• เลือกเทอม [ชื่อเทอม]
• ดูเทอม

📚 วิชา
• +วิชา [ชื่อ] [รหัส] [ห้อง] [โควตาลา]
• ดูวิชา (แสดงรายชื่อวิชาทั้งหมด)

📝 การบ้าน & แจ้งเตือน
• +งาน [วิชา] [ชื่องาน] [วัน เวลาส่ง]
• เช็คงาน (ดูงานทั้งหมด)
• ส่งแล้ว [ชื่องาน]
• +เตือน [ข้อความ] [วัน เวลา]

🎉 กิจกรรม & ยกคลาส
• +ยกคลาส [วิชา] [วันที่] [เหตุผล]
• +อีเวนต์ [ชื่องาน] [วัน เวลา]
• เช็คกิจกรรม

🚫 การลา
• ลา [วิชา] [เหตุผล]
• เช็กลา

📊 สรุป
• สรุป (ดูงานค้างและสิ่งที่ต้องทำวันนี้)
• เมนู (ดูคำสั่งทั้งหมด)"""

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    
    conn = database.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("INSERT OR IGNORE INTO users (line_user_id) VALUES (?)", (user_id,))
    conn.commit()
    
    # 1. เมนูคำสั่ง
    if user_text in ["เมนู", "คำสั่ง", "help", "วิธีใช้"]:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=HELP_TEXT))
        conn.close()
        return

    # 2. เพิ่มเทอม
    if user_text.startswith("+เทอม"):
        term_name = user_text.replace("+เทอม", "").strip()
        if term_name:
            cursor.execute("INSERT INTO semesters (line_user_id, name) VALUES (?, ?)", (user_id, term_name))
            term_id = cursor.lastrowid
            cursor.execute("UPDATE users SET active_semester_id = ? WHERE line_user_id = ?", (term_id, user_id))
            conn.commit()
            reply = f"✅ เพิ่มและเปิดใช้งานภาคเรียน: {term_name} เรียบร้อยแล้ว!"
        else:
            reply = "⚠️ รูปแบบไม่ถูกต้อง เช่น: +เทอม 1/2569"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        conn.close()
        return

    # 3. เลือกเทอม
    if user_text.startswith("เลือกเทอม"):
        term_name = user_text.replace("เลือกเทอม", "").strip()
        cursor.execute("SELECT id FROM semesters WHERE line_user_id = ? AND name = ?", (user_id, term_name))
        t = cursor.fetchone()
        if t:
            cursor.execute("UPDATE users SET active_semester_id = ? WHERE line_user_id = ?", (t["id"], user_id))
            conn.commit()
            reply = f"✅ เปลี่ยนภาคเรียนปัจจุบันเป็น: {term_name}"
        else:
            reply = f"❌ ไม่พบภาคเรียน '{term_name}' กรุณาใช้คำสั่ง 'ดูเทอม'"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        conn.close()
        return

    # 4. ดูเทอม
    if user_text == "ดูเทอม":
        cursor.execute("SELECT active_semester_id FROM users WHERE line_user_id = ?", (user_id,))
        u = cursor.fetchone()
        active_id = u["active_semester_id"] if u else None
        
        cursor.execute("SELECT id, name FROM semesters WHERE line_user_id = ?", (user_id,))
        terms = cursor.fetchall()
        if not terms:
            reply = "ยังไม่มีข้อมูลภาคเรียน พิมพ์ +เทอม [ชื่อเทอม] เพื่อเริ่มต้น"
        else:
            reply = "📚 รายการภาคเรียน:\n"
            for t in terms:
                tag = " (กำลังใช้งาน)" if t["id"] == active_id else ""
                reply += f"• {t['name']}{tag}\n"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply.strip()))
        conn.close()
        return

    # ดึงเทอมปัจจุบัน
    cursor.execute("SELECT active_semester_id FROM users WHERE line_user_id = ?", (user_id,))
    u = cursor.fetchone()
    active_semester_id = u["active_semester_id"] if u else None

    # 5. เพิ่มวิชา
    if user_text.startswith("+วิชา"):
        if not active_semester_id:
            reply = "⚠️ กรุณาเพิ่มเทอมก่อน เช่น: +เทอม 1/2569"
        else:
            parts = user_text.split()
            if len(parts) >= 5:
                sub_name = parts[1]
                sub_code = parts[2]
                room = parts[3]
                try:
                    quota = int(parts[4])
                    cursor.execute("""
                        INSERT INTO subjects (semester_id, name, code, room, max_absent)
                        VALUES (?, ?, ?, ?, ?)
                    """, (active_semester_id, sub_name, sub_code, room, quota))
                    conn.commit()
                    reply = f"✅ เพิ่มวิชา {sub_name} ({sub_code}) ห้อง {room} โควตาลา {quota} ครั้ง สำเร็จ!"
                except ValueError:
                    reply = "⚠️ โควตาลาต้องเป็นตัวเลขจำนวนเต็มครับ"
            else:
                reply = "⚠️ รูปแบบไม่ถูกต้อง เช่น: +วิชา PLC 101 LAB1 3"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        conn.close()
        return

    # 6. ดูวิชาทั้งหมด
    if user_text in ["ดูวิชา", "เช็ควิชา", "รายวิชา"]:
        if not active_semester_id:
            reply = "⚠️ ยังไม่ได้เลือกเทอม"
        else:
            cursor.execute("""
                SELECT name, code, room, max_absent 
                FROM subjects 
                WHERE semester_id = ?
            """, (active_semester_id,))
            subs = cursor.fetchall()
            if not subs:
                reply = "📚 ยังไม่มีรายวิชาในเทอมนี้\nพิมพ์: +วิชา [ชื่อ] [รหัส] [ห้อง] [โควตาลา]"
            else:
                reply = "📚 รายชื่อวิชาในเทอมนี้:\n\n"
                for s in subs:
                    reply += f"• {s['name']} ({s['code']})\n  ห้องเรียน: {s['room']} | ลาได้: {s['max_absent']} ครั้ง\n\n"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply.strip()))
        conn.close()
        return

    # 7. เพิ่มงาน
    if user_text.startswith("+งาน"):
        if not active_semester_id:
            reply = "⚠️ กรุณาเพิ่มเทอมก่อน เช่น: +เทอม 1/2569"
        else:
            parts = user_text.split()
            if len(parts) >= 5:
                sub_name = parts[1]
                task_title = parts[2]
                due_date = f"{parts[3]} {parts[4]}"
                
                cursor.execute("SELECT id FROM subjects WHERE semester_id = ? AND name = ?", (active_semester_id, sub_name))
                sub = cursor.fetchone()
                if sub:
                    cursor.execute("""
                        INSERT INTO assignments (subject_id, title, due_datetime)
                        VALUES (?, ?, ?)
                    """, (sub["id"], task_title, due_date))
                    conn.commit()
                    reply = f"✅ เพิ่มงาน '{task_title}' วิชา {sub_name}\n⏰ กำหนดส่ง: {due_date}"
                else:
                    reply = f"❌ ไม่พบวิชา '{sub_name}' กรุณาเพิ่มวิชาก่อนครับ"
            else:
                reply = "⚠️ รูปแบบไม่ถูกต้อง เช่น: +งาน PLC รายงานLab1 2026-08-20 23:59"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        conn.close()
        return

    # 8. เช็คงาน
    if user_text in ["เช็คงาน", "ดูงาน", "การบ้าน"]:
        if not active_semester_id:
            reply = "⚠️ ยังไม่ได้เลือกเทอม"
        else:
            cursor.execute("""
                SELECT a.title, a.due_datetime, a.is_done, s.name as subject_name 
                FROM assignments a 
                JOIN subjects s ON a.subject_id = s.id 
                WHERE s.semester_id = ?
                ORDER BY a.is_done ASC, a.due_datetime ASC
            """, (active_semester_id,))
            tasks = cursor.fetchall()
            if not tasks:
                reply = "📝 ยังไม่มีรายการงานในเทอมนี้"
            else:
                reply = "📋 รายการงานทั้งหมด:\n\n"
                for t in tasks:
                    status = "✅ ส่งแล้ว" if t["is_done"] == 1 else "⏳ ยังไม่ส่ง"
                    reply += f"• [{t['subject_name']}] {t['title']}\n  กำหนดส่ง: {t['due_datetime']}\n  สถานะ: {status}\n\n"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply.strip()))
        conn.close()
        return

    # 9. ส่งงานแล้ว
    if user_text.startswith("ส่งแล้ว"):
        task_name = user_text.replace("ส่งแล้ว", "").strip()
        if not task_name:
            reply = "⚠️ กรุณาระบุชื่องาน เช่น: ส่งแล้ว รายงานLab1"
        else:
            cursor.execute("""
                UPDATE assignments 
                SET is_done = 1 
                WHERE title = ? AND subject_id IN (SELECT id FROM subjects WHERE semester_id = ?)
            """, (task_name, active_semester_id))
            conn.commit()
            if cursor.rowcount > 0:
                reply = f"🎉 เยี่ยมมาก! อัปเดตงาน '{task_name}' เป็นส่งแล้วเรียบร้อย"
            else:
                reply = f"❌ ไม่พบงานชื่อ '{task_name}' ในเทอมนี้"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        conn.close()
        return

    # 10. เพิ่มการยกคลาส
    if user_text.startswith("+ยกคลาส"):
        if not active_semester_id:
            reply = "⚠️ กรุณาเพิ่มเทอมก่อน"
        else:
            parts = user_text.split(maxsplit=3)
            if len(parts) >= 4:
                sub_name = parts[1]
                cancel_date = parts[2]
                note = parts[3]
                cursor.execute("SELECT id FROM subjects WHERE semester_id = ? AND name = ?", (active_semester_id, sub_name))
                sub = cursor.fetchone()
                if sub:
                    cursor.execute("""
                        INSERT INTO canceled_classes (subject_id, cancel_date, note)
                        VALUES (?, ?, ?)
                    """, (sub["id"], cancel_date, note))
                    conn.commit()
                    reply = f"📢 บันทึกยกคลาสวิชา {sub_name}\n📅 วันที่: {cancel_date}\n📌 หมายเหตุ: {note}"
                else:
                    reply = f"❌ ไม่พบวิชา '{sub_name}'"
            else:
                reply = "⚠️ รูปแบบไม่ถูกต้อง เช่น: +ยกคลาส PLC 2026-08-25 อาจารย์ติดประชุม"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        conn.close()
        return

    # 11. เพิ่มอีเวนต์/กิจกรรม
    if user_text.startswith("+อีเวนต์") or user_text.startswith("+กิจกรรม"):
        parts = user_text.split()
        if len(parts) >= 4:
            event_title = parts[1]
            event_time = f"{parts[2]} {parts[3]}"
            cursor.execute("""
                INSERT INTO special_events (line_user_id, title, event_datetime)
                VALUES (?, ?, ?)
            """, (user_id, event_title, event_time))
            conn.commit()
            reply = f"🎉 บันทึกกิจกรรม: '{event_title}'\n⏰ วันเวลา: {event_time} สำเร็จแล้ว!"
        else:
            reply = "⚠️ รูปแบบไม่ถูกต้อง เช่น: +อีเวนต์ สัมมนาคณะ 2026-08-28 09:00"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        conn.close()
        return

    # 12. เช็คกิจกรรม/ยกคลาส
    if user_text in ["เช็คกิจกรรม", "ดูกิจกรรม", "ดูกิจกรรมพิเศษ", "ดูยกคลาส"]:
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        cursor.execute("""
            SELECT s.name as sub_name, c.cancel_date, c.note 
            FROM canceled_classes c
            JOIN subjects s ON c.subject_id = s.id
            WHERE s.semester_id = ? AND c.cancel_date >= ?
            ORDER BY c.cancel_date ASC
        """, (active_semester_id, today_str))
        cancels = cursor.fetchall()

        cursor.execute("""
            SELECT title, event_datetime FROM special_events
            WHERE line_user_id = ? AND event_datetime >= ?
            ORDER BY event_datetime ASC
        """, (user_id, today_str))
        events = cursor.fetchall()

        reply = "🗓️ รายการยกคลาสและกิจกรรมที่กำลังจะมาถึง:\n\n"
        reply += "🚫 ยกคลาส:\n"
        if cancels:
            for c in cancels:
                reply += f"• [{c['sub_name']}] วันที่ {c['cancel_date']} ({c['note']})\n"
        else:
            reply += "• ไม่มีคลาสที่ยกเลิก\n"

        reply += "\n🎉 กิจกรรม/อีเวนต์:\n"
        if events:
            for e in events:
                reply += f"• {e['title']} (เวลา {e['event_datetime']})\n"
        else:
            reply += "• ไม่มีกิจกรรมพิเศษ\n"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply.strip()))
        conn.close()
        return

    # 13. เพิ่มการแจ้งเตือน
    if user_text.startswith("+เตือน"):
        parts = user_text.split()
        if len(parts) >= 4:
            remind_msg = parts[1]
            remind_time = f"{parts[2]} {parts[3]}"
            cursor.execute("""
                INSERT INTO reminders (line_user_id, message, remind_datetime)
                VALUES (?, ?, ?)
            """, (user_id, remind_msg, remind_time))
            conn.commit()
            reply = f"⏰ ตั้งแจ้งเตือน: '{remind_msg}' เวลา: {remind_time} เรียบร้อยแล้ว!"
        else:
            reply = "⚠️ รูปแบบไม่ถูกต้อง เช่น: +เตือน ส่งงานLab1 2026-08-20 09:00"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        conn.close()
        return

    # 14. บันทึกการลา
    if user_text.startswith("ลา"):
        if not active_semester_id:
            reply = "⚠️ กรุณาเพิ่มเทอมก่อน"
        else:
            parts = user_text.split(maxsplit=2)
            if len(parts) >= 3:
                sub_name = parts[1]
                reason = parts[2]
                cursor.execute("SELECT id, max_absent FROM subjects WHERE semester_id = ? AND name = ?", (active_semester_id, sub_name))
                sub = cursor.fetchone()
                if sub:
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    cursor.execute("INSERT INTO leaves (subject_id, leave_date, reason) VALUES (?, ?, ?)", (sub["id"], today_str, reason))
                    conn.commit()
                    
                    cursor.execute("SELECT COUNT(*) as count FROM leaves WHERE subject_id = ?", (sub["id"],))
                    used = cursor.fetchone()["count"]
                    remain = sub["max_absent"] - used
                    reply = f"✅ บันทึกการลาวิชา {sub_name}\n📌 เหตุผล: {reason}\n📊 ลาไปแล้ว: {used}/{sub['max_absent']} ครั้ง (เหลือ {remain} ครั้ง)"
                else:
                    reply = f"❌ ไม่พบวิชา '{sub_name}'"
            else:
                reply = "⚠️ รูปแบบไม่ถูกต้อง เช่น: ลา PLC ป่วยเป็นไข้"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        conn.close()
        return

    # 15. เช็กลา
    if user_text == "เช็กลา":
        if not active_semester_id:
            reply = "ยังไม่มีข้อมูลภาคเรียน"
        else:
            cursor.execute("SELECT id, name, max_absent FROM subjects WHERE semester_id = ?", (active_semester_id,))
            subs = cursor.fetchall()
            if not subs:
                reply = "ยังไม่มีรายวิชาในเทอมนี้"
            else:
                reply = "📊 สรุปการใช้วันลา:\n"
                for s in subs:
                    cursor.execute("SELECT COUNT(*) as count FROM leaves WHERE subject_id = ?", (s["id"],))
                    used = cursor.fetchone()["count"]
                    remain = s["max_absent"] - used
                    reply += f"• {s['name']}: ลา {used}/{s['max_absent']} ครั้ง (เหลือ {remain})\n"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply.strip()))
        conn.close()
        return

    # 16. สรุปภาพรวม
    if user_text == "สรุป":
        if not active_semester_id:
            reply = "⚠️ ยังไม่ได้เลือกเทอม กรุณาพิมพ์ 'ดูเทอม' หรือ '+เทอม [ชื่อเทอม]'"
        else:
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            cursor.execute("""
                SELECT a.title, a.due_datetime, s.name as subject_name 
                FROM assignments a 
                JOIN subjects s ON a.subject_id = s.id 
                WHERE s.semester_id = ? AND a.is_done = 0
                ORDER BY a.due_datetime ASC
            """, (active_semester_id,))
            tasks = cursor.fetchall()
            
            cursor.execute("""
                SELECT message, remind_datetime FROM reminders 
                WHERE line_user_id = ? AND remind_datetime LIKE ?
            """, (user_id, f"{today_str}%"))
            rems = cursor.fetchall()

            cursor.execute("""
                SELECT s.name as sub_name, c.note 
                FROM canceled_classes c
                JOIN subjects s ON c.subject_id = s.id
                WHERE s.semester_id = ? AND c.cancel_date = ?
            """, (active_semester_id, today_str))
            cancels_today = cursor.fetchall()

            cursor.execute("""
                SELECT title, event_datetime FROM special_events
                WHERE line_user_id = ? AND event_datetime LIKE ?
            """, (user_id, f"{today_str}%"))
            events_today = cursor.fetchall()
            
            reply = "📊 สรุปภาพรวมวันนี้:\n\n"
            
            if cancels_today:
                reply += "🚫 ยกคลาสวันนี้:\n"
                for c in cancels_today:
                    reply += f"• [{c['sub_name']}] หมายเหตุ: {c['note']}\n"
                reply += "\n"

            if events_today:
                reply += "🎉 กิจกรรมวันนี้:\n"
                for e in events_today:
                    reply += f"• {e['title']} ({e['event_datetime'].split()[1]})\n"
                reply += "\n"

            reply += "📝 งานที่ต้องส่ง:\n"
            if tasks:
                for t in tasks:
                    reply += f"• [{t['subject_name']}] {t['title']} (ส่ง: {t['due_datetime']})\n"
            else:
                reply += "✨ ไม่มีงานค้างเลย เยี่ยมมาก!\n"
                
            reply += "\n🔔 แจ้งเตือนวันนี้:\n"
            if rems:
                for r in rems:
                    reply += f"• {r['message']} ({r['remind_datetime'].split()[1]})\n"
            else:
                reply += "✨ ไม่มีแจ้งเตือนสำหรับวันนี้"
                
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply.strip()))
        conn.close()
        return

    # ข้อความเริ่มต้น
    line_bot_api.reply_message(
        event.reply_token, 
        TextSendMessage(text=f"รับข้อความ: {user_text}\n(พิมพ์ 'เมนู' เพื่อดูรายการคำสั่ง)")
    )
    conn.close()