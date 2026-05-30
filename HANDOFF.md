# 📦 HANDOFF — ส่งต่อ LINE Bot จากโปรเจกต์เก่า มาทำ "เตือนธุรกิจ"

> ไฟล์นี้เขียนให้ **Claude Code โปรเจกต์ใหม่** อ่านแล้วทำงานต่อได้ทันที
> อ่านให้จบก่อนเริ่มแก้โค้ดหรือ deploy อะไรทั้งหมด

---

## 0. สรุปภารกิจ

รีไซเคิล **LINE OA ตัวเดิม** (ตัวที่เจมส์แอดในมือถืออยู่แล้ว) เปลี่ยนหน้าที่:
- **เดิม:** เตือนออกกำลังกาย / IF / บันทึกน้ำหนัก / การเงิน
- **ใหม่:** เตือนเรื่อง **ธุรกิจ**

**กฎเหล็ก:**
- ❌ ห้ามสร้าง LINE channel / OA ใหม่ — ใช้ตัวเดิมเท่านั้น (credentials อยู่ใน `.env` แล้ว)
- ✅ เขียนโค้ดใหม่ในโฟลเดอร์นี้ + deploy server ใหม่ แล้วค่อยสลับ Webhook มาที่ server ใหม่

---

## 1. ⚠️ ธุรกิจที่จะให้เตือน — รอเจมส์ระบุ

> **[ TODO — เจมส์ยังไม่ได้ระบุรายละเอียด ]**
> ต้องเติมก่อนเริ่มเขียน logic เตือน:
> - ธุรกิจคืออะไร (เช่น ขายแซลมอน / รับทำคอนเทนต์ลูกค้า ฯลฯ)
> - อยากเตือนอะไรบ้าง + เวลาไหน (เช่น ติดตามลูกค้า, ลงคอนเทนต์, เช็คออเดอร์, สรุปยอด)
> - เก็บข้อมูลลง Notion เดิม หรือทำ DB/หน้าใหม่

ถ้ายังไม่ระบุ — **ถามเจมส์ก่อน** อย่าเดาเนื้อหาเตือนเอง

---

## 2. 🔑 Credentials (อยู่ใน `.env` แล้ว — ก๊อปมาจากโปรเจกต์เก่าให้เรียบร้อย)

ไฟล์ `.env` มี 7 ตัว (ถูก gitignore แล้ว — **ห้าม commit**):

| Key | ใช้ต่อ? | หมายเหตุ |
|-----|--------|----------|
| `LINE_CHANNEL_SECRET` | ✅ ใช้เดิม | = OA ตัวเดิม |
| `LINE_CHANNEL_ACCESS_TOKEN` | ✅ ใช้เดิม | = OA ตัวเดิม |
| `LINE_USER_ID` | ✅ ใช้เดิม | User ID ของเจมส์ (ปลายทาง push) |
| `NOTION_TOKEN` | ✅/🔁 | ใช้เดิมได้ หรือต่อ integration ใหม่ |
| `NOTION_PAGE_ID` | 🔁 | หน้า Notion เดิม — ทำหน้าใหม่ได้ |
| `NOTION_FINANCE_DB_ID` | 🔁 | DB การเงินเดิม — เปลี่ยนตามงานธุรกิจได้ |
| `CLAUDE_API_KEY` | ✅ ใช้เดิม | สำหรับให้ Claude ช่วยสรุป/เขียนข้อความ |

---

## 3. 🔀 กลไกส่งต่อ Webhook (จุดพลาดบ่อยที่สุด — อ่านให้ดี)

**OA 1 ตัว ชี้ Webhook URL ได้ที่เดียว** ดังนั้นห้ามสลับมั่ว ทำตามลำดับนี้:

1. เขียนโค้ดใหม่ในโฟลเดอร์นี้ให้เสร็จ
2. Deploy server ใหม่ขึ้น (ดูข้อ 5) → ได้ URL เช่น `https://xxx.onrender.com`
3. เช็คว่า `https://xxx.onrender.com/health` ตอบ `OK`
4. เข้า **LINE Developers Console** → เลือก channel ของ OA เดิม → แท็บ **Messaging API**
5. แก้ **Webhook URL** เป็น `https://xxx.onrender.com/webhook` → กด **Verify** → เปิด **Use webhook**
6. ทดสอบส่งข้อความหา OA ดูว่าตอบจาก server ใหม่
7. ✅ ใช้งานได้แล้ว → **ค่อยปิด server เก่า** (โปรเจกต์ `james-brain-bot` บน Render)

> ทำ server ใหม่ให้พร้อม **ก่อน** สลับ URL เสมอ — กันบอทล่มช่วงเปลี่ยนผ่าน

---

## 4. 🏗️ โครงสร้างโค้ดเดิม (reuse skeleton ได้ ไม่ต้องเขียนใหม่หมด)

โค้ดอ้างอิงเต็มอยู่ที่:
`/Users/jamesbondny/Desktop/James Personal/projects/james-brain-bot/app.py`

**Stack:** Flask + Gunicorn + APScheduler + line-bot-sdk v3 + notion-client + anthropic
**Timezone:** `Asia/Bangkok` ทั้งหมด

**Pattern หลัก:**
- `POST /webhook` → รับข้อความจาก LINE → ตอบกลับ (reply)
- `send_push(message)` → ยิงข้อความเตือนถึงเจมส์ตามเวลา (ใช้ `LINE_USER_ID`)
- `BackgroundScheduler` + `CronTrigger` → ตั้งเวลาเตือน
- `GET /health` → ให้ ping กันเซิร์ฟเวอร์หลับ

**✅ เก็บไว้ใช้ต่อ (โครงพร้อมแล้ว):**
- ระบบ webhook + signature validation
- `send_push()` / reply plumbing
- scheduler skeleton
- helper เขียน/อ่าน Notion (`log_finance_to_notion`, `get_notion_section`, ฯลฯ)

**❌ ลบทิ้งทั้งหมด (ของสุขภาพเดิม):**
- `WORKOUTS`, `exercise_reminder_weights`, `exercise_reminder_cardio`
- `if_start`, `if_warning` (IF)
- ระบบบันทึกน้ำหนัก, `log_workout_to_notion`
- คำสั่ง LINE: เล่นเสร็จ/วิ่งเสร็จ/น้ำหนัก
- job ใน scheduler ที่ผูกกับของพวกนี้

---

## 5. 🚀 Deploy (Render — free tier)

- ใช้ `render.yaml` + `requirements.txt` จากโปรเจกต์เก่าเป็นต้นแบบได้
- start command: `gunicorn app:app --workers 1 --bind 0.0.0.0:$PORT`
- env vars 7 ตัว (ข้อ 2) ตั้งใน Render dashboard แบบ `sync: false`
- **แนะนำ:** สร้าง **repo ใหม่ + Render service ใหม่** (อย่าทับของเก่า จะได้มี fallback)
- repo เก่า: `github.com/jamesbondny/james-brain-bot`

**⚠️ Free tier หลับเมื่อไม่มีทราฟฟิก** → ต้องตั้ง **cron-job.org** ให้ ping
`https://<server-ใหม่>/health` ทุก 10 นาที (ตั้งใหม่ชี้ server ใหม่ ของเดิม ping URL เก่า)

---

## 6. ⚠️ Gotchas

- **ห้ามใช้ Markdown ในข้อความ LINE** — `*`, `#`, `-`, `**` จะโชว์เป็นตัวอักษรดิบ ใช้ emoji + plain text แทน
- ข้อความ push ยาวมีลิมิต — เตือนยาวๆ ให้ย่อ
- บัญชี/แดชบอร์ดที่ต้องให้เจมส์ login เอง (Claude Code เข้าแทนไม่ได้):
  - LINE Developers Console
  - Render
  - Notion (ต่อ integration)
  - cron-job.org

---

## 7. ✅ Cutover Checklist (ลำดับสลับ ทำตามนี้)

- [ ] เติมรายละเอียดธุรกิจ (ข้อ 1) — ถามเจมส์ถ้ายังไม่มี
- [ ] เขียนโค้ด `app.py` ใหม่ (เก็บ skeleton, ลบของสุขภาพ, ใส่ logic ธุรกิจ)
- [ ] ทดสอบ local ว่ารันได้
- [ ] สร้าง repo ใหม่ + push
- [ ] สร้าง Render service ใหม่ + ตั้ง env vars
- [ ] เช็ค `/health` ตอบ OK
- [ ] สลับ Webhook URL ใน LINE Console → Verify → เปิด Use webhook
- [ ] ตั้ง cron-job.org ping `/health` server ใหม่ ทุก 10 นาที
- [ ] ทดสอบส่งข้อความ + รอ job เตือนตามเวลา
- [ ] ปิด server เก่า (Render: james-brain-bot)

---

*สร้างโดยโปรเจกต์ Second Brain — ส่งต่อให้โปรเจกต์ business-reminder-bot*
