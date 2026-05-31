# 📌 RESUME — LINE เลขา Bot (เปิดครั้งหน้าอ่านไฟล์นี้ก่อน)

> อัปเดตล่าสุด: 2026-05-31 ~02:30
> สถานะ: **🎉 ใช้งานได้จริงแล้ว! ด่าน 1-3 + 5 ✅ — เจมส์พิมพ์ LINE → AI แยกงาน → เข้า Supabase → JAVIS เห็น (verified งาน id 2 "ตามออเดอร์ 42")**
> เหลือ: ด่าน 4 (cron กันบอทหลับ) + ปรับเรื่อง multi-task (ดู "สิ่งที่ต้องปรับ" ล่างสุด)

## ⚠️ สิ่งที่ต้องปรับ (เจอตอนเทสต์จริง 2026-05-31)
- **เจมส์ชอบส่งงานเป็นลิสต์หลายอันทีเดียว** เช่น "งาน\n- คอนเท่นสร้อย\n- คลิปหมูหวาน\n- tier list ลูกค้า" — ตอนนี้บอทรับทีละ 1 งาน/ข้อความ → ลิสต์แบบนี้ไม่เข้า ต้องปรับให้ parse หลายงานจากข้อความเดียว
- **คำว่า "งาน" ขึ้นต้นข้อความชนกับคำสั่ง "ดูงานค้าง"** (exact match) → ถ้าเจมส์เริ่มประโยคจดงานด้วย "งาน" จะถูกตีความเป็นคำสั่งดูลิสต์ ต้องปรับ logic แยกแยะ
- งานเดี่ยว 1 ข้อความทำงานสมบูรณ์แล้ว ✅

---

## 🎯 เป้าหมายโปรเจกต์
ระบบ "เลขา" ผ่าน LINE แทน Notion:
- เจมส์ทักบอทใน LINE จากมือถือ (ภาษาพูด) → บอทใช้ AI (Haiku) แยกเป็นงาน → เก็บลง **Supabase** (ตาราง `tasks`)
- JAVIS บน Mac อ่าน/เขียน Supabase เล่มเดียวกัน → ตามงานต่อได้
- ความสามารถ: จดงาน / ดูงานค้าง / ติ๊กเสร็จ / เด้งเตือนสรุปงานทุกเช้า 8 โมง
- **ไม่ใช้ emoji** ในข้อความบอท (เจมส์สั่ง) — ใช้เลขข้อ + วงเล็บ + ขีดคั่นแทน

---

## ✅ ทำเสร็จแล้ว
1. ตาราง `tasks` ใน Supabase (RLS เปิด, no anon policy) — เทสต์ insert/list/done ผ่าน
2. โค้ดบอทครบ (`app.py`) — parse(AI) + insert/list/mark_done + LINE webhook handler + scheduler เตือนเช้า — เทสต์ local ผ่านหมด (แยกวันที่แม่น, ไม่มี emoji)
3. โค้ดขึ้น GitHub: **github.com/jamesbondny/prowderia-secretary-bot** (public)
4. สร้าง Render web service แล้ว ใส่ env ครบ 6 ตัว

## 🔧 ปัญหาที่เจอ + แก้แล้ว (กันพลาดซ้ำ)
- **Supabase key**: ต้องใช้ `sb_secret_...` (ตัวใหม่) + ต้องใช้ `supabase==2.30.1` (2.7.4 ไม่รองรับ key ใหม่)
- **Deploy fail ครั้งแรก** = `TypeError: proxies` → httpx ใหม่ตัด proxies ทำ anthropic 0.39 พัง
  - แก้: pin `httpx==0.27.2` ใน requirements + `.python-version = 3.12.8` (กัน Render ใช้ Python 3.14)
  - แก้แล้ว push เป็น commit **5fd26ff** (อยู่บน GitHub แล้ว แต่ Render ยังไม่ได้ deploy ใหม่)

---

## ▶️ ขั้นต่อไป — เริ่มตรงนี้ครั้งหน้า

### ด่าน 2 (ให้จบ) — เจมส์กด Manual Deploy
1. เปิด Render → service **prowderia-secretar** → ปุ่ม **Manual Deploy** (บนขวา) → **Deploy latest commit**
2. รอ build เสร็จ (2-5 นาที)
3. JAVIS เช็ค: `curl -m 90 https://prowderia-secretar.onrender.com/health` → ต้องได้ **OK**
   - ถ้าได้ OK = บอททำงานแล้ว ✅ ไปด่าน 3
   - ถ้า fail = เปิด Render Logs ดู error ใหม่

### ด่าน 3 — สลับสาย LINE (webhook)
- LINE Developers Console → channel OA เดิม → แท็บ **Messaging API**
- **Webhook URL** = `https://prowderia-secretar.onrender.com/webhook`
- กด Verify → เปิด **Use webhook**
- (บอทสุขภาพเก่าจะหยุด — เจมส์ยืนยัน OK แล้ว)
- เทสต์: ทักบอทใน LINE ว่า "เริ่ม" → ควรตอบเมนูช่วยเหลือ / ลองพิมพ์ "ตามออเดอร์ 42 พรุ่งนี้" → ควรจดงาน

### ด่าน 4 — กันบอทหลับ (free tier หลับเมื่อ idle)
- cron-job.org → สร้าง job ping `https://prowderia-secretar.onrender.com/health` ทุก 10 นาที

### ด่าน 5 — เชื่อม JAVIS
- JAVIS อ่าน/เขียน Supabase ตาราง `tasks` ผ่าน MCP — verify เห็นงานเดียวกับที่จดจาก LINE

---

## 📋 ข้อมูลอ้างอิง
- **Repo**: github.com/jamesbondny/prowderia-secretary-bot (public)
- **Render URL**: https://prowderia-secretar.onrender.com
- **Webhook URL (ด่าน 3)**: https://prowderia-secretar.onrender.com/webhook
- **Supabase project**: `mgcqidjsmtddhxqvfjwr` (Prowderia) — ตาราง `tasks` พร้อม
- **LINE OA**: ตัวเดิม (credentials ใน `.env`)
- **ไฟล์ env**: `~/Desktop/RENDER-ค่าที่ต้องใส่.txt` (6 ค่า — ใส่ Render ครบแล้ว)
- โฟลเดอร์โปรเจกต์: `~/Desktop/business-reminder-bot/` (มี venv สำหรับเทสต์ local)

## 🔒 ความปลอดภัย / สิ่งที่ต้องเก็บกวาด
- **GitHub PAT** (ghp_...) ที่เจมส์สร้าง: หมดอายุเอง 7 วัน — ลบได้หลัง deploy เสร็จ ที่ github.com/settings/tokens
- `.env` + `RENDER-ค่าที่ต้องใส่.txt` มี secret จริง — อยู่ local, ห้าม push (gitignore แล้ว)
- ⚠️ แยกเรื่อง (ค่อยทำ): ตาราง `lms_order_cache` ใน Supabase เปิด RLS disabled — security risk เล็กน้อย
