import os
import json
import logging
from datetime import datetime
import pytz
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    PushMessageRequest, ReplyMessageRequest, TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from supabase import create_client
import anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', '')
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')
LINE_USER_ID = os.environ.get('LINE_USER_ID', '')
CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', '')
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')

BANGKOK_TZ = pytz.timezone('Asia/Bangkok')
THAI_DAYS = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]
PARSE_MODEL = "claude-haiku-4-5-20251001"

handler = WebhookHandler(LINE_CHANNEL_SECRET)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
claude = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ---------------------------------------------------------------------------
# Helpers — date formatting (Thai, plain text only — no markdown in LINE)
# ---------------------------------------------------------------------------
def thai_date(iso_str):
    """'2026-06-01' -> 'จ. 1 มิ.ย.' ; None -> '' """
    if not iso_str:
        return ''
    try:
        d = datetime.strptime(iso_str, '%Y-%m-%d')
        months = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
                  'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
        wd = THAI_DAYS[d.weekday()][:1]
        return f"{wd}. {d.day} {months[d.month - 1]}"
    except Exception:
        return iso_str


# ---------------------------------------------------------------------------
# Parse free text -> task (Haiku, JSON only)
# ---------------------------------------------------------------------------
def _upcoming_calendar(now, days=16):
    from datetime import timedelta
    labels = {0: " (วันนี้)", 1: " (พรุ่งนี้)", 2: " (มะรืน)"}
    lines = []
    for i in range(days + 1):
        d = now + timedelta(days=i)
        lines.append(f"{d.strftime('%Y-%m-%d')} = วัน{THAI_DAYS[d.weekday()]}{labels.get(i, '')}")
    return "\n".join(lines)


def parse_task(text):
    now = datetime.now(BANGKOK_TZ)
    calendar = _upcoming_calendar(now)
    system = f"""คุณคือตัวช่วยแยกข้อความภาษาพูดของเจมส์ให้เป็น "งาน" คืนค่าเป็น JSON อย่างเดียวเท่านั้น ห้ามมีข้อความอื่น

รูปแบบ:
{{"is_task": true/false, "title": "ชื่องานสั้นกระชับ", "due_date": "YYYY-MM-DD หรือ null", "related_order": "เลขออเดอร์ หรือ null", "note": "รายละเอียดเพิ่ม หรือ null"}}

กฎ:
- is_task=false ถ้าเป็นการทักทาย คำถามทั่วไป หรือไม่ใช่การสั่งให้จดงาน
- ถ้าไม่ระบุวัน ให้ due_date=null
- title ให้กระชับเป็นกริยา เช่น "ตามออเดอร์ 42", "โทรหาแป้งเรื่องคลิป"
- related_order ใส่เฉพาะตัวเลข ถ้าพูดถึงเลขออเดอร์/คิว

เรื่องวันที่ — ห้ามนับวันเอง ให้ใช้ปฏิทินจริงด้านล่างนี้เทียบหาวันที่เสมอ
- ชื่อวันพูดลอยๆ เช่น "วันจันทร์" "ศุกร์นี้" = วันนั้นที่ใกล้ที่สุดซึ่งยังมาไม่ถึง (ตัวแรกในปฏิทิน)
- ถ้ามีคำว่า "หน้า" เช่น "จันทร์หน้า" = วันจันทร์ของสัปดาห์ถัดไป (ตัวที่สองในปฏิทิน)
{calendar}"""
    try:
        resp = claude.messages.create(
            model=PARSE_MODEL,
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": text}],
        )
        raw = resp.content[0].text.strip()
        # strip code fences if any
        if raw.startswith('```'):
            raw = raw.split('```')[1].lstrip('json').strip()
        return json.loads(raw)
    except Exception as e:
        logger.error(f"parse_task error: {e}")
        # fallback: treat whole text as a task title
        return {"is_task": True, "title": text, "due_date": None,
                "related_order": None, "note": None}


# ---------------------------------------------------------------------------
# Supabase operations
# ---------------------------------------------------------------------------
def insert_task(parsed, source='line'):
    row = {
        "title": parsed.get("title") or "(ไม่มีชื่องาน)",
        "due_date": parsed.get("due_date"),
        "related_order": parsed.get("related_order"),
        "note": parsed.get("note"),
        "source": source,
    }
    supabase.table("tasks").insert(row).execute()
    return row


def list_open():
    """งานค้างทั้งหมด เรียงตาม id (ลำดับคงที่ ใช้ติ๊กด้วยเลขได้)"""
    res = (supabase.table("tasks")
           .select("id, title, due_date, related_order")
           .eq("status", "open")
           .order("id")
           .execute())
    return res.data or []


def mark_done_by_index(index):
    """ติ๊กงานค้างลำดับที่ index (เริ่มที่ 1) -> คืน title หรือ None"""
    tasks = list_open()
    if index < 1 or index > len(tasks):
        return None
    task = tasks[index - 1]
    now = datetime.now(BANGKOK_TZ).isoformat()
    (supabase.table("tasks")
     .update({"status": "done", "done_at": now})
     .eq("id", task["id"])
     .execute())
    return task["title"]


# ---------------------------------------------------------------------------
# Message formatting
# ---------------------------------------------------------------------------
def format_task_line(i, t):
    line = f"{i}. {t['title']}"
    extras = []
    if t.get("related_order"):
        extras.append(f"ออเดอร์ {t['related_order']}")
    if t.get("due_date"):
        extras.append(thai_date(t["due_date"]))
    if extras:
        line += " (" + " - ".join(extras) + ")"
    return line


def format_open_list(tasks, header="งานที่ค้างอยู่"):
    if not tasks:
        return "ไม่มีงานค้างแล้ว เคลียร์หมดทุกงาน"
    lines = [header, ""]
    for i, t in enumerate(tasks, 1):
        lines.append(format_task_line(i, t))
    lines.append("")
    lines.append("ติ๊กเสร็จพิมพ์: เสร็จ 1")
    return "\n".join(lines)


HELP_TEXT = """เลขา Prowderia พร้อมช่วยแล้ว

จดงาน - พิมพ์เป็นภาษาพูดได้เลย
ตย. ตามออเดอร์ 42 พรุ่งนี้
ตย. โทรหาแป้งเรื่องคลิปวันจันทร์

ดูงานค้าง - พิมพ์
งาน (หรือ มีงานอะไรบ้าง)

ติ๊กเสร็จ - พิมพ์
เสร็จ 1 (เลขตามในลิสต์)"""


# ---------------------------------------------------------------------------
# Scheduled push — สรุปงานทุกเช้า
# ---------------------------------------------------------------------------
def send_push(message):
    if not LINE_USER_ID:
        logger.warning("LINE_USER_ID not set")
        return
    try:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).push_message(
                PushMessageRequest(to=LINE_USER_ID, messages=[TextMessage(text=message)])
            )
    except Exception as e:
        logger.error(f"Push error: {e}")


def morning_brief():
    now = datetime.now(BANGKOK_TZ)
    thai_day = THAI_DAYS[now.weekday()]
    date_str = now.strftime('%d/%m')
    tasks = list_open()
    header = f"อรุณสวัสดิ์ เจมส์ - วัน{thai_day} {date_str}"
    send_push(format_open_list(tasks, header=header))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


@app.route("/health", methods=['GET'])
def health():
    return 'OK'


def _parse_done_index(text):
    """'เสร็จ 2' / 'done 2' / 'ติ๊ก 2' -> 2 ; else None"""
    for kw in ["เสร็จแล้ว", "เสร็จ", "ติ๊ก", "done", "ติ๊กเสร็จ"]:
        if text.startswith(kw):
            rest = text[len(kw):].strip()
            if rest.isdigit():
                return int(rest)
    return None


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        if text in ["/help", "help", "ช่วยเหลือ", "คำสั่ง", "เริ่ม"]:
            reply = HELP_TEXT
        elif text == "/id":
            reply = f"User ID:\n{user_id}"
        elif text in ["งาน", "งานค้าง", "ดูงาน", "มีงานอะไรบ้าง", "list", "งานวันนี้"]:
            reply = format_open_list(list_open())
        elif _parse_done_index(text) is not None:
            idx = _parse_done_index(text)
            title = mark_done_by_index(idx)
            if title:
                remaining = list_open()
                reply = f"ติ๊กเสร็จแล้ว: {title}"
                if remaining:
                    reply += f"\n\nเหลืออีก {len(remaining)} งาน (พิมพ์ งาน เพื่อดู)"
                else:
                    reply += "\n\nเคลียร์งานหมดแล้ว"
            else:
                reply = "ไม่เจองานข้อนั้น พิมพ์ งาน เพื่อดูลิสต์ล่าสุดก่อนนะ"
        else:
            parsed = parse_task(text)
            if parsed.get("is_task") and parsed.get("title"):
                insert_task(parsed)
                reply = f"จดงานแล้ว: {parsed['title']}"
                tail = []
                if parsed.get("related_order"):
                    tail.append(f"ออเดอร์ {parsed['related_order']}")
                if parsed.get("due_date"):
                    tail.append("กำหนด " + thai_date(parsed["due_date"]))
                if tail:
                    reply += "\n(" + " - ".join(tail) + ")"
            else:
                reply = "รับทราบครับ\n\n" + HELP_TEXT

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)],
            )
        )


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
scheduler = BackgroundScheduler(timezone=BANGKOK_TZ)
scheduler.add_job(morning_brief, CronTrigger(hour=8, minute=0, timezone=BANGKOK_TZ))
scheduler.start()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
