import logging
import json
import os
import re
import hashlib
import secrets
import tempfile
import io
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.constants import ParseMode
from flask import Flask, request

# ----------------------------- OPTIONAL OCR -----------------------------
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    print("WARNING: pytesseract or PIL not installed. Automatic screenshot verification disabled.")

# ----------------------------- CONFIGURATION -----------------------------
BOT_TOKEN = "8707499860:AAGDLyFZTwj2ezQCdnjKS6me4QFKqFSQ22Y"
ADMIN_IDS = [1726879904]
ADMIN_PASSWORD = "NBook_@Abraham-2Tesfaye#T"

ADMIN_CONTACT = """
📞 **Admin Contact**  
Phone (SMS only): `0717071136`  
Telegram: @Betre_Aron1  
For any issues, please contact the admin.
"""

MAX_DEVICES_PER_USER = 1
MAX_LOGIN_ATTEMPTS = 3
BLOCK_DURATION_MINUTES = 30
MAX_DAILY_SECONDS = 4 * 3600          # 4 hours
CONTINUOUS_LIMIT_SECONDS = 1.5 * 3600  # 1.5 hours
BREAK_SECONDS = 20 * 60                # 20 minutes
EXAM_QUESTION_TIME = 80                # seconds per question

PAYMENT_METHODS = """
💳 **PAYMENT METHODS**
Send payment to:
📱 **Telebirr:** `0930831292`
🏦 **CBE:** `1000259231497`
🏦 **Dashen:** `5078002112012`
🏦 **BoA:** `239082009`
✅ **AFTER PAYMENT:**
1. Take a SCREENSHOT (JPG/PNG/PDF)
2. Send screenshot + Transaction ID
3. Wait for verification (auto or admin)
⚠️ **SECURITY NOTICE:** One Access ID = One device. Sharing = permanent ban.
"""

# ----------------------------- PRICE LISTS WITH TIERS (Basic / VIP / VVIP) -----------------------------
def build_prices():
    prices = {}
    # Grades 1-4 (only Basic)
    for g in range(1, 5):
        prices[str(g)] = {"name": f"Grade {g}", "tiers": {"Basic": {"1M": 150, "3M": 250, "6M": 400, "1Y": 700}}}
    # Grades 5-6
    base56 = {"1M": 250, "3M": 400, "6M": 700, "1Y": 1000}
    for g in range(5, 7):
        prices[str(g)] = {"name": f"Grade {g}", "tiers": {
            "Basic": base56,
            "VIP": {k: v+150 for k, v in base56.items()},
            "VVIP": {k: v+250 for k, v in base56.items()}
        }}
    # Grades 7-8
    base78 = {"1M": 200, "3M": 300, "6M": 450, "1Y": 600}
    for g in range(7, 9):
        prices[str(g)] = {"name": f"Grade {g}", "tiers": {
            "Basic": base78,
            "VIP": {k: v+150 for k, v in base78.items()},
            "VVIP": {k: v+250 for k, v in base78.items()}
        }}
    # Grades 9-10
    base910 = {"1M": 250, "3M": 350, "6M": 500, "1Y": 800}
    for g in range(9, 11):
        prices[str(g)] = {"name": f"Grade {g}", "tiers": {
            "Basic": base910,
            "VIP": {k: v+150 for k, v in base910.items()},
            "VVIP": {k: v+250 for k, v in base910.items()}
        }}
    # Grades 11-12
    base1112 = {"1M": 300, "3M": 400, "6M": 600, "1Y": 900}
    for g in range(11, 13):
        prices[str(g)] = {"name": f"Grade {g}", "tiers": {
            "Basic": base1112,
            "VIP": {k: v+150 for k, v in base1112.items()},
            "VVIP": {k: v+250 for k, v in base1112.items()}
        }}
    # Special grades (no tiers)
    special = {
        "7": {"name": "Grade 6 Ministry", "tiers": {"Basic": {"FULL": 500}}},
        "10": {"name": "Grade 8 Ministry", "tiers": {"Basic": {"FULL": 800}}},
        "17": {"name": "Uni Entrance Social", "tiers": {"Basic": {"FULL": 800}}},
        "18": {"name": "Uni Entrance Natural", "tiers": {"Basic": {"FULL": 800}}},
        "19": {"name": "Freshman", "tiers": {"Basic": {"1M": 250, "3M": 350, "6M": 600, "1Y": 800}}},
        "20": {"name": "Electrical Engineering", "tiers": {"Basic": {"1M": 250, "3M": 350, "6M": 500, "1Y": 800}}},
        "21": {"name": "Health Related", "tiers": {"Basic": {"1M": 250, "3M": 350, "6M": 500, "1Y": 800}}},
    }
    prices.update(special)
    return prices

PRICES = build_prices()

# ----------------------------- COMPLETE SUBJECTS -----------------------------
SUBJECTS = {
    "1": ["አማርኛ", "English", "አካባቢ ሳይንስ", "ክወናና እይታ ጥበባት", "ስነ-ምግባር", "ሒሳብ"],
    "2": ["አማርኛ", "English", "አካባቢ ሳይንስ", "ክወናና እይታ ጥበባት", "ስነ-ምግባር", "ሒሳብ"],
    "3": ["አማርኛ", "English", "አካባቢ ሳይንስ", "ክወናና እይታ ጥበባት", "ስነ-ምግባር", "ሒሳብ"],
    "4": ["አማርኛ", "English", "አካባቢ ሳይንስ", "ክወናና እይታ ጥበባት", "ስነ-ምግባር", "ሒሳብ"],
    "5": ["አማርኛ", "English", "አካባቢ ሳይንስ", "ክወናና እይታ ጥበባት", "ስነ-ምግባር", "ሒሳብ"],
    "6": ["አማርኛ", "English", "አካባቢ ሳይንስ", "ክወናና እይታ ጥበባት", "ስነ-ምግባር", "ሒሳብ"],
    "7": ["አማርኛ", "English", "አካባቢ ሳይንስ", "ሒሳብ"],
    "8": ["Mathematics", "General Science", "IT", "English", "Citizenship", "Amharic", "Social Studies"],
    "9": ["Mathematics", "General Science", "IT", "English", "Citizenship", "Amharic", "Social Studies"],
    "10": ["Mathematics", "English", "General Science", "Amharic"],
    "11": ["History", "Economics", "Geography", "ICT", "Mathematics", "Biology", "Chemistry", "Physics", "Citizenship", "English"],
    "12": ["History", "Economics", "Geography", "ICT", "Mathematics", "Biology", "Chemistry", "Physics", "Citizenship", "English"],
    "13": ["SAT", "Mathematics", "English", "History", "Geography", "Economics"],
    "14": ["SAT", "English", "Mathematics", "Physics", "Chemistry", "Biology"],
    "15": ["SAT", "Mathematics", "English", "History", "Geography", "Economics"],
    "16": ["SAT", "English", "Mathematics", "Physics", "Chemistry", "Biology"],
    "17": ["SAT", "Mathematics", "English", "History", "Geography", "Economics"],
    "18": ["SAT", "Mathematics", "English", "Physics", "Chemistry", "Biology"],
    "19": ["Communicative English I", "Communicative English II", "Logic & Critical Thinking", "Geography of Ethiopia", "History of Ethiopian Peoples", "Emerging Technologies", "General Psychology", "Moral & Civic Education", "Entrepreneurship", "Social Anthropology", "Mathematics for Natural Science", "General Physics", "General Chemistry", "General Biology", "Mathematics for Social Science", "Introduction to Economics"],
    "20": ["Fundamental of Electrical Circuit", "Applied Electronics", "Signal & System Analysis", "Network Analysis & Synthesis", "C++", "DLD", "Java", "Introduction to Communication Systems"],
    "21": ["Anatomy", "Physiology", "Surgery", "Internal Medicine", "Microbiology", "Pharmacology", "Pathology", "Immunology"],
}

# ----------------------------- DATA STORAGE (extended) -----------------------------
DATA_FILE = "secure_bot_data.json"
FILE_IDS_FILE = "file_ids.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {
        "users": {},
        "pending_payments": {},
        "blocked_users": {},
        "device_tracking": {},
        "login_attempts": {},
        "free_trials": {},
        "next_ra_number": 1,
        "user_activity": {},
        "user_sessions": {},
        "admin_logged_in": False,
        "leaderboard_weekly": [],
        "exam_sessions": {},
        "exam_attempts": []
    }

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_file_ids():
    if os.path.exists(FILE_IDS_FILE):
        try:
            with open(FILE_IDS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"pdf": {}, "video": {}, "ppt": {}, "ministry_exercise": {}, "matric_exercise": {}}

def save_file_ids(data):
    with open(FILE_IDS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

bot_data = load_data()
file_ids = load_file_ids()
# ----------------------------- SECURITY HELPERS -----------------------------
def get_device_fingerprint(update):
    user = update.effective_user
    fingerprint_data = f"{user.id}_{user.username}_{user.language_code}"
    return hashlib.sha256(fingerprint_data.encode()).hexdigest()

def check_device_access(user_id, device_fingerprint):
    user_id = str(user_id)
    if user_id in [str(uid) for uid in ADMIN_IDS]:
        return True
    if user_id not in bot_data["users"]:
        return True
    if user_id not in bot_data["device_tracking"]:
        bot_data["device_tracking"][user_id] = device_fingerprint
        save_data(bot_data)
        return True
    return bot_data["device_tracking"][user_id] == device_fingerprint

def register_device(user_id, device_fingerprint):
    user_id = str(user_id)
    bot_data["device_tracking"][user_id] = device_fingerprint
    save_data(bot_data)

def report_sharing_attempt(user_id):
    user_id = str(user_id)
    bot_data["blocked_users"][user_id] = {
        "reason": "Access ID sharing detected",
        "blocked_at": datetime.now().isoformat(),
        "permanent": True
    }
    if user_id in bot_data["users"]:
        del bot_data["users"][user_id]
    save_data(bot_data)

def check_login_attempts(user_id):
    user_id = str(user_id)
    if user_id in bot_data["blocked_users"]:
        block_info = bot_data["blocked_users"][user_id]
        if not block_info.get("permanent", False):
            blocked_at = datetime.fromisoformat(block_info["blocked_at"])
            if (datetime.now() - blocked_at).seconds > BLOCK_DURATION_MINUTES * 60:
                del bot_data["blocked_users"][user_id]
                save_data(bot_data)
                return True
        return False
    return True

def record_failed_attempt(user_id):
    user_id = str(user_id)
    if user_id not in bot_data["login_attempts"]:
        bot_data["login_attempts"][user_id] = 0
    bot_data["login_attempts"][user_id] += 1
    if bot_data["login_attempts"][user_id] >= MAX_LOGIN_ATTEMPTS:
        bot_data["blocked_users"][user_id] = {
            "reason": f"Too many failed attempts ({MAX_LOGIN_ATTEMPTS})",
            "blocked_at": datetime.now().isoformat(),
            "permanent": False
        }
        del bot_data["login_attempts"][user_id]
    save_data(bot_data)

def reset_login_attempts(user_id):
    user_id = str(user_id)
    if user_id in bot_data["login_attempts"]:
        del bot_data["login_attempts"][user_id]
        save_data(bot_data)

class RateLimiter:
    def __init__(self):
        self.requests = {}
    def check(self, user_id, limit=10, period=60):
        user_id = str(user_id)
        if user_id in [str(uid) for uid in ADMIN_IDS]:
            return True
        now = datetime.now()
        if user_id not in self.requests:
            self.requests[user_id] = []
        self.requests[user_id] = [t for t in self.requests[user_id] if (now - t).seconds < period]
        if len(self.requests[user_id]) >= limit:
            return False
        self.requests[user_id].append(now)
        return True

rate_limiter = RateLimiter()

# ----------------------------- HELPER FUNCTIONS -----------------------------
def get_expiry_date(package_type, tier):
    now = datetime.now()
    days_map = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "FULL": 365}
    days = days_map.get(package_type, 365)
    return (now + timedelta(days=days)).isoformat()

def generate_ti():
    num = bot_data.get("next_ra_number", 1)
    if num > 5000:
        num = 1
    ti = f"RA{num:04d}"
    bot_data["next_ra_number"] = num + 1
    save_data(bot_data)
    return ti

def check_user_limits(user_id):
    uid = str(user_id)
    now = datetime.now()
    sess = bot_data["user_sessions"].get(uid, {})
    # reset daily
    last_reset = sess.get("last_reset_date")
    if not last_reset or datetime.fromisoformat(last_reset).date() < now.date():
        sess = {"daily_used_seconds": 0, "last_reset_date": now.isoformat(), "session_start": None, "break_until": None}
    # break check
    break_until = sess.get("break_until")
    if break_until and datetime.fromisoformat(break_until) > now:
        return False, f"⏸️ Forced break until {break_until[:16]}. Please rest."
    # daily limit
    if sess.get("daily_used_seconds", 0) >= MAX_DAILY_SECONDS:
        return False, "Daily limit of 4 hours reached. Come back tomorrow."
    # continuous usage
    session_start = sess.get("session_start")
    if session_start:
        elapsed = (now - datetime.fromisoformat(session_start)).seconds
        if elapsed >= CONTINUOUS_LIMIT_SECONDS:
            break_until = now + timedelta(seconds=BREAK_SECONDS)
            sess["break_until"] = break_until.isoformat()
            sess["session_start"] = None
            bot_data["user_sessions"][uid] = sess
            save_data(bot_data)
            return False, f"⚠️ 1.5 hours of continuous study. Take a 20‑min break. Resume at {break_until.strftime('%H:%M')}."
    return True, ""

def update_usage(user_id, duration_seconds):
    uid = str(user_id)
    now = datetime.now()
    sess = bot_data["user_sessions"].get(uid, {})
    if not sess.get("last_reset_date") or datetime.fromisoformat(sess["last_reset_date"]).date() < now.date():
        sess = {"daily_used_seconds": 0, "last_reset_date": now.isoformat(), "session_start": None, "break_until": None}
    sess["daily_used_seconds"] = sess.get("daily_used_seconds", 0) + duration_seconds
    sess["session_start"] = now.isoformat()
    bot_data["user_sessions"][uid] = sess
    save_data(bot_data)

def log_activity(user_id, grade_id, subject, chapter, action, duration_seconds=0, score=None, total=None):
    uid = str(user_id)
    if uid not in bot_data["user_activity"]:
        bot_data["user_activity"][uid] = []
    entry = {
        "timestamp": datetime.now().isoformat(),
        "grade": grade_id,
        "subject": subject,
        "chapter": chapter,
        "action": action,
        "duration": duration_seconds,
        "score": score,
        "total": total
    }
    bot_data["user_activity"][uid].append(entry)
    if len(bot_data["user_activity"][uid]) > 1000:
        bot_data["user_activity"][uid] = bot_data["user_activity"][uid][-1000:]
    save_data(bot_data)

def can_access_content(user_id, content_category):
    uid = str(user_id)
    # trial gives full access
    if uid in bot_data["free_trials"] and datetime.now() - datetime.fromisoformat(bot_data["free_trials"][uid]) <= timedelta(minutes=10):
        return True
    if uid not in bot_data["users"]:
        return False
    tier = bot_data["users"][uid].get("tier", "Basic")
    allowed = {
        "Basic": ["shortnote", "problems", "exam", "ppt", "pdf"],
        "VIP": ["shortnote", "problems", "exam", "ppt", "pdf", "ministry_exercise", "matric_exercise", "other_grade"],
        "VVIP": ["shortnote", "problems", "exam", "ppt", "pdf", "ministry_exercise", "matric_exercise", "other_grade", "competition", "online_tutor", "video_tutorial"]
    }
    return content_category in allowed.get(tier, [])

def can_access_other_grades(user_id):
    uid = str(user_id)
    if uid in bot_data["free_trials"] and datetime.now() - datetime.fromisoformat(bot_data["free_trials"][uid]) <= timedelta(minutes=10):
        return True
    if uid not in bot_data["users"]:
        return False
    tier = bot_data["users"][uid].get("tier", "Basic")
    return tier in ["VIP", "VVIP"]

def user_has_access(user_id, grade_id):
    uid = str(user_id)
    if uid in bot_data["users"]:
        user = bot_data["users"][uid]
        if user["grade"] == grade_id:
            expiry = datetime.fromisoformat(user["expiry"])
            if expiry >= datetime.now():
                return True
    if uid in bot_data["free_trials"]:
        start = datetime.fromisoformat(bot_data["free_trials"][uid])
        if datetime.now() - start <= timedelta(minutes=10):
            return True
        else:
            del bot_data["free_trials"][uid]
            save_data(bot_data)
    return False

# ----------------------------- FILE READING -----------------------------
async def read_file_content(grade_name, subject_name, chapter_num, file_type):
    try:
        base_path = "/home/yourusername/learning_bot_files"  # Change to your PythonAnywhere path
        grade_clean = re.sub(r'[^\w\s-]', '', grade_name)
        subject_clean = re.sub(r'[^\w\s-]', '', subject_name)
        chapter_clean = f"Chapter {chapter_num}"
        file_path = f"{base_path}/{grade_clean}/{subject_clean}/{chapter_clean}/{file_type}.txt"
        if not os.path.exists(file_path):
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return None

# ----------------------------- OCR & PAYMENT VERIFICATION -----------------------------
async def extract_text_from_media(file_id, context):
    if not TESSERACT_AVAILABLE:
        return None
    try:
        file = await context.bot.get_file(file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name
        img = Image.open(tmp_path)
        text = pytesseract.image_to_string(img)
        os.unlink(tmp_path)
        return text
    except Exception as e:
        print(f"OCR error: {e}")
        return None

def parse_transaction_details(text):
    details = {"date": None, "name_found": False, "accounts_found": []}
    date_patterns = [r'\d{4}-\d{2}-\d{2}', r'\d{2}/\d{2}/\d{4}', r'\d{2}\.\d{2}\.\d{4}']
    for pat in date_patterns:
        m = re.search(pat, text)
        if m:
            details["date"] = m.group()
            break
    name_variants = ["Muluye", "Tazeze", "Kasie", "Kassie", "Muluye Tazeze"]
    for name in name_variants:
        if name.lower() in text.lower():
            details["name_found"] = True
            break
    accounts = ["0930831292", "1000259231497", "5078002112012", "239082009"]
    for acc in accounts:
        if acc in text:
            details["accounts_found"].append(acc)
    return details

def is_transaction_valid(details, current_time):
    if details["date"]:
        try:
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d.%m.%Y'):
                try:
                    trans_date = datetime.strptime(details["date"], fmt)
                    if (current_time - trans_date).days > 3:
                        return False, "transaction_date_expired"
                    break
                except:
                    continue
        except:
            pass
    score = 0
    if details["name_found"]:
        score += 1
    score += min(len(details["accounts_found"]), 2)
    if score >= 2:
        return True, "auto_verified"
    else:
        return False, "manual_review"
        # ----------------------------- BOT COMMANDS -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    device_fp = get_device_fingerprint(update)
    register_device(user_id, device_fp)

    uid = str(user_id)
    if uid not in bot_data["users"] and "temp_ti" in context.user_data:
        await update.message.reply_text("Please enter your Tracking ID (TI) to restore access:")
        context.user_data["awaiting_ti"] = True
        return

    keyboard = [
        [InlineKeyboardButton("📚 Choose Grade/Course", callback_data="show_grades")],
        [InlineKeyboardButton("👤 My Account", callback_data="my_account")],
        [InlineKeyboardButton("🎁 Free Trial (10 min)", callback_data="free_trial")],
        [InlineKeyboardButton("📘 User Guide", callback_data="user_guide")],
        [InlineKeyboardButton("📞 Support", callback_data="support")],
        [InlineKeyboardButton("🔒 Security Info", callback_data="security_info")],
        [InlineKeyboardButton("🏠 Home", callback_data="restart")]
    ]
    if str(user_id) in [str(uid) for uid in ADMIN_IDS]:
        keyboard.insert(0, [InlineKeyboardButton("🔐 Admin Login", callback_data="admin_login")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🎓 **Welcome to Learning Bot!**\n\n"
        "🔒 **SECURE ACCESS SYSTEM**\n"
        "• One Access ID = One Device\n"
        "• Sharing = Permanent Ban\n"
        "• All actions are monitored\n\n"
        "Choose an option below:\n\n"
        f"{ADMIN_CONTACT}",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def user_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    guide = """
📘 **User Guide**

**1. Start** – Send /start to see the menu.

**2. Free Trial** – Click 🎁 Free Trial (10 min) to try all content for free (once per user).

**3. Purchase** – Click 📚 Choose Grade/Course → select your grade → choose Basic/VIP/VVIP (for grades 5‑12). Follow payment instructions. After payment, you will be asked for your Full Name, School, and Contact. You will receive a Tracking ID (TI) like `RA0001-xxxxx`.

**4. Access Materials** – After purchase or trial, you can:
   - Short notes, solved problems, exams, PDFs, PPTs.
   - VIP/VVIP users get extra: ministry exercises, matric exercises, access to all grades.
   - VVIP users also get competition (timed quizzes), online tutor, video tutorials.

**5. Exam Rules** – Each question: 1 min 20 sec. No back button during first run. You can **flag** difficult questions. After last question, you can review flagged ones. Final score and rank message shown.

**6. Limits** – Max 4 hours per day. After 1.5 hours continuous use, a 20‑min break is forced.

**7. Support** – Use 📞 Support to contact admin.

**8. Security** – Do NOT share your TI or Access ID. Sharing = permanent ban.

**Enjoy learning!** 🎓
"""
    await query.edit_message_text(guide, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")
    ]]))

async def free_trial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    if uid in bot_data["users"]:
        await query.edit_message_text("❌ You already have a paid subscription. Free trial not available.", parse_mode="Markdown")
        return
    if uid in bot_data["free_trials"]:
        start_t = datetime.fromisoformat(bot_data["free_trials"][uid])
        if datetime.now() - start_t <= timedelta(minutes=10):
            rem = 10 - (datetime.now() - start_t).seconds // 60
            await query.edit_message_text(f"⏳ Active free trial! {rem} minutes left.\nUse 📚 Choose Grade/Course.", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ Free trial expired. Please purchase a subscription.", parse_mode="Markdown")
        return
    bot_data["free_trials"][uid] = datetime.now().isoformat()
    save_data(bot_data)
    await query.edit_message_text(
        "✅ **Free trial activated!**\n\nYou have **10 minutes** of full access to **all grades and content**.\n"
        "Click **📚 Choose Grade/Course** to explore.\n\n⏰ After 10 minutes, purchase a subscription.\n\nEnjoy! 🎉",
        parse_mode="Markdown"
    )

async def security_info(query):
    await query.edit_message_text(
        f"🔒 **SECURITY INFORMATION**\n\n"
        "**Device Lock:** One Access ID per device.\n"
        "**Anti-Sharing:** Sharing = permanent ban.\n"
        "**Rate Limiting:** 10 requests/minute.\n"
        "**Login Attempts:** 3 failures = 30 min block.\n\n"
        f"{ADMIN_CONTACT}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")
        ]]),
        parse_mode="Markdown"
    )

async def show_grade_categories(query):
    keyboard = [
        [InlineKeyboardButton("📚 Lower Grades (1-4)", callback_data="category_lower")],
        [InlineKeyboardButton("📚 Middle Grades (5-8)", callback_data="category_middle")],
        [InlineKeyboardButton("📚 High School (9-12)", callback_data="category_high")],
        [InlineKeyboardButton("🎓 Exams & Higher", callback_data="category_exams")],
        [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
    ]
    await query.edit_message_text("📚 **Choose a Category**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_grades_by_range(query, category):
    if category == "lower":
        grades = [["Grade 1", "grade_1"], ["Grade 2", "grade_2"], ["Grade 3", "grade_3"], ["Grade 4", "grade_4"]]
    elif category == "middle":
        grades = [["Grade 5", "grade_5"], ["Grade 6", "grade_6"], ["Grade 6 Ministry", "grade_7"],
                  ["Grade 7", "grade_8"], ["Grade 8", "grade_9"], ["Grade 8 Ministry", "grade_10"]]
    elif category == "high":
        grades = [["Grade 9", "grade_11"], ["Grade 10", "grade_12"],
                  ["Grade 11 Social", "grade_13"], ["Grade 11 Natural", "grade_14"],
                  ["Grade 12 Social", "grade_15"], ["Grade 12 Natural", "grade_16"]]
    else:
        grades = [["Uni Entrance Social", "grade_17"], ["Uni Entrance Natural", "grade_18"],
                  ["Freshman", "grade_19"], ["Electrical Engineering", "grade_20"],
                  ["Health Related", "grade_21"]]
    keyboard = []
    for i in range(0, len(grades), 2):
        row = [InlineKeyboardButton(grades[i][0], callback_data=grades[i][1])]
        if i+1 < len(grades):
            row.append(InlineKeyboardButton(grades[i+1][0], callback_data=grades[i+1][1]))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="back_to_categories")])
    await query.edit_message_text("📚 **Select Grade**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_account(query):
    uid = str(query.from_user.id)
    if uid in bot_data["users"]:
        u = bot_data["users"][uid]
        expiry = datetime.fromisoformat(u["expiry"])
        days_left = (expiry - datetime.now()).days
        total_sec = sum(a.get("duration", 0) for a in bot_data["user_activity"].get(uid, []))
        total_hours = total_sec // 3600
        total_min = (total_sec % 3600) // 60
        text = (
            f"👤 **Your Account**\n\n"
            f"TI: `{u['ti']}`\n"
            f"Name: {u['full_name']}\n"
            f"School: {u['school']}\n"
            f"Grade: {u['grade_name']}\n"
            f"Package: {u['package']} ({u['tier']})\n"
            f"Expires: {expiry.strftime('%Y-%m-%d')}\n"
            f"Days left: {days_left}\n"
            f"Total study time: {total_hours}h {total_min}m\n\n{ADMIN_CONTACT}"
        )
    elif uid in bot_data["free_trials"]:
        start_t = datetime.fromisoformat(bot_data["free_trials"][uid])
        elapsed = (datetime.now() - start_t).seconds // 60
        remaining = max(0, 10 - elapsed)
        text = f"🎁 **Free Trial**\nTime remaining: {remaining} minutes\n\n{ADMIN_CONTACT}"
    else:
        text = f"No subscription.\nClick 🎁 Free Trial or purchase.\n\n{ADMIN_CONTACT}"
    keyboard = [[InlineKeyboardButton("📚 Browse Grades", callback_data="show_grades")],
                [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_package_tiers(query, grade_id):
    grade_info = PRICES[grade_id]
    tiers = grade_info["tiers"]
    text = f"**{grade_info['name']}**\n\n"
    if len(tiers) > 1:
        text += "```\n"
        text += "Feature                     | Basic | VIP | VVIP\n"
        text += "----------------------------|-------|-----|------\n"
        text += "Short notes                 | ✅    | ✅  | ✅\n"
        text += "Solved problems             | ✅    | ✅  | ✅\n"
        text += "Exam                        | ✅    | ✅  | ✅\n"
        text += "PPT                         | ✅    | ✅  | ✅\n"
        text += "PDF                         | ✅    | ✅  | ✅\n"
        text += "Exercise to ministry        | ❌    | ✅  | ✅\n"
        text += "Access to other grades      | ❌    | ✅  | ✅\n"
        text += "Exercise to matric          | ❌    | ✅  | ✅\n"
        text += "Access to competition       | ❌    | ❌  | ✅\n"
        text += "Online tutor                | ❌    | ❌  | ✅\n"
        text += "Video tutorial              | ❌    | ❌  | ✅\n"
        text += "```\n\n"
    text += "Choose your package:\n"
    keyboard = []
    for tier_name, prices in tiers.items():
        for pkg, price in prices.items():
            display = {"1M":"1 Month","3M":"3 Months","6M":"6 Months","1Y":"1 Year","FULL":"Full Access"}.get(pkg, pkg)
            keyboard.append([InlineKeyboardButton(f"{tier_name} - {display} ({price} birr)", callback_data=f"pkg_{grade_id}_{tier_name}_{pkg}")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Grades", callback_data="back_to_categories")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def confirm_payment(query, grade_id, tier, package_type):
    user_id = str(query.from_user.id)
    amount = PRICES[grade_id]["tiers"][tier][package_type]
    bot_data["pending_payments"][user_id] = {
        "grade_id": grade_id,
        "tier": tier,
        "package": package_type,
        "amount": amount,
        "transaction_id": None,
        "screenshot_file_id": None,
        "screenshot_text": None,
        "verified": False,
        "sent_to_admin": False
    }
    save_data(bot_data)
    await query.edit_message_text(
        f"💳 **PAYMENT REQUIRED**\n\n"
        f"**Grade:** {PRICES[grade_id]['name']}\n"
        f"**Tier:** {tier}\n"
        f"**Package:** {package_type}\n"
        f"**Amount:** {amount} birr\n\n"
        f"{PAYMENT_METHODS}\n\n"
        f"**NEXT STEP:**\n"
        f"1. Send a screenshot of your payment (image or PDF)\n"
        f"2. Type your Transaction ID in a separate message.\n\n"
        f"⚠️ You must send both. Wait up to 10 minutes for verification.\n\n{ADMIN_CONTACT}",
        parse_mode="Markdown"
    )

# ----------------------------- USER REGISTRATION -----------------------------
async def register_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, grade_id, tier, package_type, transaction_id):
    uid = str(user_id)
    context.user_data["pending_registration"] = {
        "grade_id": grade_id,
        "tier": tier,
        "package": package_type,
        "transaction_id": transaction_id
    }
    await update.message.reply_text(
        "📝 **Registration required**\n\n"
        "Please provide the following information (one per message):\n"
        "1. Your **Full Name**\n"
        "2. Your **School Name**\n"
        "3. Your **Contact Phone Number**\n\n"
        "Type /cancel to abort.",
        parse_mode="Markdown"
    )
    context.user_data["reg_step"] = 1

async def process_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "/cancel":
        context.user_data.pop("pending_registration", None)
        context.user_data.pop("reg_step", None)
        await update.message.reply_text("Registration cancelled.")
        return
    step = context.user_data.get("reg_step", 1)
    reg = context.user_data.get("pending_registration")
    if not reg:
        return
    if step == 1:
        context.user_data["reg_name"] = text
        context.user_data["reg_step"] = 2
        await update.message.reply_text("✅ Name saved. Now send your **School Name**:")
    elif step == 2:
        context.user_data["reg_school"] = text
        context.user_data["reg_step"] = 3
        await update.message.reply_text("✅ School saved. Now send your **Contact Phone Number**:")
    elif step == 3:
        context.user_data["reg_contact"] = text
        uid = str(update.effective_user.id)
        ti = generate_ti()
        grade_id = reg["grade_id"]
        tier = reg["tier"]
        package_type = reg["package"]
        expiry = get_expiry_date(package_type, tier)
        bot_data["users"][uid] = {
            "ti": ti,
            "full_name": context.user_data["reg_name"],
            "school": context.user_data["reg_school"],
            "contact": context.user_data["reg_contact"],
            "grade": grade_id,
            "grade_name": PRICES[grade_id]["name"],
            "tier": tier,
            "package": package_type,
            "expiry": expiry,
            "original_transaction": reg["transaction_id"]
        }
        if uid in bot_data["free_trials"]:
            del bot_data["free_trials"][uid]
        save_data(bot_data)
        context.user_data.pop("pending_registration", None)
        context.user_data.pop("reg_step", None)
        context.user_data.pop("reg_name", None)
        context.user_data.pop("reg_school", None)
        context.user_data.pop("reg_contact", None)
        await update.message.reply_text(
            f"✅ **Registration complete!**\n\n"
            f"Your Tracking ID (TI): `{ti}`\n"
            f"Keep it safe. Use /start to access materials.\n\n{ADMIN_CONTACT}",
            parse_mode="Markdown"
        )
        # ----------------------------- ENHANCED EXAM SYSTEM -----------------------------
def parse_exam_content(content):
    questions = []
    blocks = content.strip().split("\n\n")
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if len(lines) < 6:
            continue
        first = lines[0]
        if '.' not in first:
            continue
        q_text = first.split('.', 1)[1].strip()
        options = {}
        for line in lines[1:5]:
            if line[0] in "ABCD" and line[1] == ')':
                options[line[0]] = line[2:].strip()
        correct_line = lines[5]
        if not correct_line.lower().startswith("correct:"):
            continue
        correct = correct_line.split(':')[1].strip().upper()
        if correct not in options:
            continue
        questions.append({"text": q_text, "options": options, "correct": correct})
    return questions

async def start_exam(update: Update, context: ContextTypes.DEFAULT_TYPE, grade_id, subject, chapter):
    query = update.callback_query
    user_id = query.from_user.id
    uid = str(user_id)
    grade_name = PRICES[grade_id]["name"]
    content = await read_file_content(grade_name, subject, chapter, "exam")
    if not content:
        await query.edit_message_text(f"📝 No exam questions for {subject} Chapter {chapter}.", parse_mode="Markdown")
        return
    questions = parse_exam_content(content)
    if not questions:
        await query.edit_message_text("❌ Exam file format error.", parse_mode="Markdown")
        return
    total = len(questions)
    total_time = total * EXAM_QUESTION_TIME
    exam_id = f"{uid}_{grade_id}_{subject}_{chapter}_{datetime.now().timestamp()}"
    bot_data["exam_sessions"][exam_id] = {
        "user_id": uid,
        "grade_id": grade_id,
        "subject": subject,
        "chapter": chapter,
        "questions": questions,
        "answers": [None] * total,
        "flagged": [False] * total,
        "current_index": 0,
        "total": total,
        "start_time": datetime.now().isoformat(),
        "time_limit": total_time,
        "status": "running",
        "timer_tasks": []
    }
    save_data(bot_data)
    context.user_data["current_exam"] = exam_id
    await send_exam_question(query, context, exam_id, 0)

async def send_exam_question(query, context, exam_id, idx):
    exam = bot_data["exam_sessions"].get(exam_id)
    if not exam or exam["status"] not in ["running", "reviewing"]:
        if query:
            await query.edit_message_text("Exam session expired.")
        return
    q = exam["questions"][idx]
    total = exam["total"]
    flagged = "🚩 " if exam["flagged"][idx] else ""
    text = f"**{flagged}Question {idx+1}/{total}**\n\n{q['text']}\n\nTime per question: 1 min 20 sec"
    keyboard = []
    for letter, opt in q["options"].items():
        keyboard.append([InlineKeyboardButton(f"{letter}. {opt}", callback_data=f"exam_answer_{exam_id}_{idx}_{letter}")])
    keyboard.append([InlineKeyboardButton("🚩 Flag", callback_data=f"exam_flag_{exam_id}_{idx}")])
    if exam["status"] == "reviewing":
        keyboard.append([InlineKeyboardButton("🔙 Back to Flagged List", callback_data=f"exam_back_to_flags_{exam_id}")])
    else:
        keyboard.append([InlineKeyboardButton("❌ Cancel Exam", callback_data="exam_cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await context.bot.send_message(int(exam["user_id"]), text, reply_markup=reply_markup, parse_mode="Markdown")
    # schedule timer
    async def timer_func():
        await asyncio.sleep(EXAM_QUESTION_TIME)
        exam_now = bot_data["exam_sessions"].get(exam_id)
        if exam_now and exam_now["current_index"] == idx and exam_now["status"] == "running":
            exam_now["answers"][idx] = None
            exam_now["current_index"] += 1
            save_data(bot_data)
            if exam_now["current_index"] >= exam_now["total"]:
                exam_now["status"] = "reviewing"
                save_data(bot_data)
                await show_flagged_review(context.bot, int(exam_now["user_id"]), exam_id)
            else:
                await send_exam_question(None, context, exam_id, exam_now["current_index"])
    task = asyncio.create_task(timer_func())
    if "timer_tasks" not in exam:
        exam["timer_tasks"] = []
    exam["timer_tasks"].append(task)
    save_data(bot_data)

async def exam_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, exam_id, idx, letter):
    query = update.callback_query
    exam = bot_data["exam_sessions"].get(exam_id)
    if not exam or exam["status"] != "running" or exam["current_index"] != idx:
        await query.answer("Invalid or expired.")
        return
    if exam.get("timer_tasks"):
        for t in exam["timer_tasks"]:
            t.cancel()
        exam["timer_tasks"] = []
    exam["answers"][idx] = letter
    exam["current_index"] += 1
    save_data(bot_data)
    if exam["current_index"] >= exam["total"]:
        exam["status"] = "reviewing"
        save_data(bot_data)
        await show_flagged_review(context.bot, query.message.chat_id, exam_id)
    else:
        await send_exam_question(query, context, exam_id, exam["current_index"])

async def exam_flag_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, exam_id, idx):
    query = update.callback_query
    exam = bot_data["exam_sessions"].get(exam_id)
    if not exam or exam["status"] != "running" or exam["current_index"] != idx:
        await query.answer("Invalid.")
        return
    exam["flagged"][idx] = True
    save_data(bot_data)
    await query.answer("Question flagged for review.")
    if exam.get("timer_tasks"):
        for t in exam["timer_tasks"]:
            t.cancel()
        exam["timer_tasks"] = []
    exam["current_index"] += 1
    save_data(bot_data)
    if exam["current_index"] >= exam["total"]:
        exam["status"] = "reviewing"
        save_data(bot_data)
        await show_flagged_review(context.bot, query.message.chat_id, exam_id)
    else:
        await send_exam_question(query, context, exam_id, exam["current_index"])

async def show_flagged_review(bot, chat_id, exam_id):
    exam = bot_data["exam_sessions"].get(exam_id)
    if not exam:
        return
    flagged_indices = [i+1 for i, f in enumerate(exam["flagged"]) if f]
    if not flagged_indices:
        await finish_exam(bot, chat_id, exam_id)
        return
    text = "🚩 **Flagged Questions**\n\nClick a number to review that question:\n"
    keyboard = []
    row = []
    for num in flagged_indices:
        row.append(InlineKeyboardButton(str(num), callback_data=f"exam_review_{exam_id}_{num-1}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("✅ Submit Exam", callback_data=f"exam_submit_{exam_id}")])
    await bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def exam_review_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, exam_id, idx):
    query = update.callback_query
    exam = bot_data["exam_sessions"].get(exam_id)
    if not exam or exam["status"] != "reviewing":
        await query.answer("Expired.")
        return
    q = exam["questions"][idx]
    text = f"**Question {idx+1}** (flagged)\n\n{q['text']}\n\nChoose your answer:"
    keyboard = []
    for letter, opt in q["options"].items():
        keyboard.append([InlineKeyboardButton(f"{letter}. {opt}", callback_data=f"exam_review_answer_{exam_id}_{idx}_{letter}")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Flagged List", callback_data=f"exam_back_to_flags_{exam_id}")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def exam_review_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, exam_id, idx, letter):
    query = update.callback_query
    exam = bot_data["exam_sessions"].get(exam_id)
    if not exam or exam["status"] != "reviewing":
        await query.answer("Expired.")
        return
    exam["answers"][idx] = letter
    save_data(bot_data)
    await query.answer("Answer saved.")
    await show_flagged_review(context.bot, query.message.chat_id, exam_id)

async def finish_exam(bot, chat_id, exam_id):
    exam = bot_data["exam_sessions"].pop(exam_id, None)
    if not exam:
        return
    total = exam["total"]
    correct = 0
    for i, ans in enumerate(exam["answers"]):
        if ans is not None and ans == exam["questions"][i]["correct"]:
            correct += 1
    wrong = total - correct
    wrong_percent = (wrong / total) * 100
    # compute rank among all exam attempts
    all_attempts = bot_data.get("exam_attempts", [])
    all_attempts.append({
        "user_id": exam["user_id"],
        "grade": exam["grade_id"],
        "subject": exam["subject"],
        "chapter": exam["chapter"],
        "score": correct,
        "total": total,
        "date": datetime.now().isoformat()
    })
    bot_data["exam_attempts"] = all_attempts[-1000:]
    save_data(bot_data)
    similar_attempts = [a for a in all_attempts if a["grade"] == exam["grade_id"] and a["subject"] == exam["subject"]]
    better = sum(1 for a in similar_attempts if a["score"] > correct)
    rank_out_of = len(similar_attempts)
    if rank_out_of == 0:
        rank_msg = "You are the first to take this exam!"
    else:
        percentile = (1 - better/rank_out_of) * 100
        if percentile >= 98:
            rank_msg = f"Top 2%! You are among the best."
        elif percentile >= 85:
            rank_msg = f"Excellent! You scored higher than {percentile:.0f}% of students."
        elif percentile >= 70:
            rank_msg = f"Very good! Better than {percentile:.0f}%."
        elif percentile >= 50:
            rank_msg = f"Good, but you can improve. Better than {percentile:.0f}%."
        else:
            rank_msg = f"Need improvement. You scored lower than {100-percentile:.0f}% of students."
    if wrong_percent <= 2:
        message = "Excellent!"
    elif wrong_percent <= 5:
        message = "Very Good!"
    elif wrong_percent <= 10:
        message = "Need Improvement."
    else:
        message = "Not using materials wisely. Improve yourself!"
    result = f"✅ **Exam finished!**\n\nScore: {correct}/{total}\n{message}\n\n{rank_msg}"
    await bot.send_message(chat_id, result, parse_mode="Markdown")
    log_activity(int(exam["user_id"]), exam["grade_id"], exam["subject"], exam["chapter"], "exam", 0, correct, total)
    # ----------------------------- ADMIN PANEL -----------------------------
async def admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    if uid not in [str(uid) for uid in ADMIN_IDS]:
        await query.edit_message_text("❌ Unauthorized.", parse_mode="Markdown")
        return
    context.user_data["awaiting_admin_password"] = True
    await query.edit_message_text("🔐 **Admin Login**\n\nPlease enter the password:", parse_mode="Markdown")

async def show_admin_menu(query):
    keyboard = [
        [InlineKeyboardButton("👥 Users List", callback_data="admin_users")],
        [InlineKeyboardButton("📤 Upload File", callback_data="admin_upload")],
        [InlineKeyboardButton("🔍 Search User", callback_data="admin_search")],
        [InlineKeyboardButton("➕ Add User", callback_data="admin_add")],
        [InlineKeyboardButton("❌ Remove User", callback_data="admin_remove")],
        [InlineKeyboardButton("📢 Announcement", callback_data="admin_announce")],
        [InlineKeyboardButton("🏆 Weekly Leaderboard", callback_data="admin_leaderboard")],
        [InlineKeyboardButton("🚪 Logout", callback_data="admin_logout")]
    ]
    await query.edit_message_text("🔧 **Admin Panel**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_users_list(query):
    users = []
    for uid, u in bot_data["users"].items():
        total_time = sum(a.get("duration", 0) for a in bot_data["user_activity"].get(uid, []))
        users.append((uid, u["ti"], u["full_name"], u["school"], u["grade_name"], total_time))
    users.sort(key=lambda x: x[5])  # least progress first
    text = "👥 **Users (least progress first)**\n\n"
    for uid, ti, name, school, grade, ttime in users[:20]:
        text += f"`{ti}` | {name[:15]} | {school[:15]} | {grade} | {ttime//60} min\n"
    text += f"\nTotal users: {len(users)}\n\nClick a TI to see details:"
    keyboard = []
    for uid, ti, name, school, grade, ttime in users[:20]:
        keyboard.append([InlineKeyboardButton(ti, callback_data=f"admin_user_detail_{uid}")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_user_detail(query, user_id):
    uid = str(user_id)
    if uid not in bot_data["users"]:
        await query.edit_message_text("User not found.")
        return
    u = bot_data["users"][uid]
    activities = bot_data["user_activity"].get(uid, [])
    text = f"**User Details: {u['ti']}**\n\n"
    text += f"Name: {u['full_name']}\nSchool: {u['school']}\nContact: {u['contact']}\nGrade: {u['grade_name']}\nTier: {u['tier']}\nPackage: {u['package']}\nExpiry: {u['expiry'][:10]}\n\n"
    text += "**Activity Log (last 10):**\n"
    for act in activities[-10:]:
        text += f"- {act['timestamp'][:16]} | {act['subject']} Ch{act['chapter']} | {act['action']} | {act.get('duration',0)//60} min"
        if act.get('score') is not None:
            text += f" | Score: {act['score']}/{act['total']}"
        text += "\n"
    await query.edit_message_text(text, parse_mode="Markdown")

async def admin_upload_start(query, context):
    context.user_data["admin_upload_step"] = 1
    await query.edit_message_text("📤 **Upload File**\n\nSend the **grade name** (e.g., 'Grade 1'):", parse_mode="Markdown")

async def admin_search_start(query, context):
    context.user_data["admin_search"] = True
    await query.edit_message_text("🔍 **Search User**\n\nSend TI, name, school, or contact:", parse_mode="Markdown")

async def admin_add_start(query, context):
    context.user_data["admin_add_step"] = 1
    await query.edit_message_text("➕ **Add User**\n\nSend TI (or type 'auto' to generate):", parse_mode="Markdown")

async def admin_remove_start(query, context):
    context.user_data["admin_remove"] = True
    await query.edit_message_text("❌ **Remove User**\n\nSend the TI of the user to remove:", parse_mode="Markdown")

async def admin_announce_start(query, context):
    context.user_data["admin_announce"] = True
    await query.edit_message_text("📢 **Announcement**\n\nSend the message to broadcast to all users:", parse_mode="Markdown")

async def admin_leaderboard(query):
    week_ago = datetime.now() - timedelta(days=7)
    points = {}
    for uid, acts in bot_data["user_activity"].items():
        total = 0
        for act in acts:
            if datetime.fromisoformat(act["timestamp"]) > week_ago:
                if act["action"] == "exam" and act.get("score"):
                    total += act["score"] * 10
                elif act["action"] == "problems" and act.get("score"):
                    total += act["score"] * 5
        if total > 0:
            points[uid] = total
    sorted_points = sorted(points.items(), key=lambda x: x[1], reverse=True)[:100]
    text = "🏆 **Weekly Leaderboard (Top 100)**\n\n"
    for i, (uid, pts) in enumerate(sorted_points, 1):
        u = bot_data["users"].get(uid, {})
        ti = u.get("ti", uid)
        text += f"{i}. `{ti}` - {pts} pts\n"
    await query.edit_message_text(text, parse_mode="Markdown")

# ----------------------------- BUTTON HANDLER (main dispatcher) -----------------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    uid = str(user_id)

    # Security checks
    if uid in bot_data["blocked_users"]:
        await query.edit_message_text(f"🚫 Account blocked.\n{ADMIN_CONTACT}", parse_mode="Markdown")
        return
    if not rate_limiter.check(user_id):
        await query.edit_message_text("⏳ Too many requests. Please wait.", parse_mode="Markdown")
        return
    device_fp = get_device_fingerprint(update)
    if not check_device_access(user_id, device_fp):
        report_sharing_attempt(user_id)
        await query.edit_message_text(f"🚫 Security alert: Access ID shared. Access revoked.\n{ADMIN_CONTACT}", parse_mode="Markdown")
        return

    # Admin panel handling
    if data == "admin_login":
        await admin_login(update, context)
        return
    if data == "admin_logout":
        bot_data["admin_logged_in"] = False
        save_data(bot_data)
        await query.edit_message_text("Logged out.", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")
        ]]))
        return
    if data.startswith("admin_"):
        if not bot_data.get("admin_logged_in", False):
            await query.edit_message_text("❌ Not logged in as admin.", parse_mode="Markdown")
            return
        if data == "admin_menu":
            await show_admin_menu(query)
        elif data == "admin_users":
            await admin_users_list(query)
        elif data == "admin_upload":
            await admin_upload_start(query, context)
        elif data == "admin_search":
            await admin_search_start(query, context)
        elif data == "admin_add":
            await admin_add_start(query, context)
        elif data == "admin_remove":
            await admin_remove_start(query, context)
        elif data == "admin_announce":
            await admin_announce_start(query, context)
        elif data == "admin_leaderboard":
            await admin_leaderboard(query)
        elif data.startswith("admin_user_detail_"):
            target_uid = data.split("_")[3]
            await admin_user_detail(query, target_uid)
        return

    # Main navigation
    if data == "show_grades":
        await show_grade_categories(query)
    elif data == "my_account":
        await show_account(query)
    elif data == "free_trial":
        await free_trial(update, context)
    elif data == "user_guide":
        await user_guide(update, context)
    elif data == "support":
        await query.edit_message_text(f"📞 **Support**\n{ADMIN_CONTACT}", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")
        ]]), parse_mode="Markdown")
    elif data == "security_info":
        await security_info(query)
    elif data == "restart" or data == "back_to_main":
        await start(update, context)
    elif data == "back_to_categories":
        await show_grade_categories(query)
    elif data.startswith("category_"):
        cat = data.split("_")[1]
        await show_grades_by_range(query, cat)
    elif data.startswith("grade_"):
        grade_id = data.split("_")[1]
        context.user_data["selected_grade"] = grade_id
        if not can_access_other_grades(user_id) and grade_id != bot_data["users"].get(uid, {}).get("grade"):
            await query.edit_message_text("❌ You can only access the grade you purchased. Upgrade to VIP/VVIP for all grades.", parse_mode="Markdown")
            return
        await show_package_tiers(query, grade_id)
    elif data.startswith("pkg_"):
        parts = data.split("_")
        grade_id = parts[1]
        tier = parts[2]
        pkg = parts[3]
        await confirm_payment(query, grade_id, tier, pkg)
    elif data.startswith("subjects_"):
        grade_id = data.replace("subjects_", "")
        if not user_has_access(user_id, grade_id):
            await query.edit_message_text("Access denied. Please purchase a subscription or start a free trial.")
            return
        subjects = SUBJECTS.get(grade_id, [])
        grade_name = PRICES[grade_id]["name"]
        keyboard = []
        for subject in subjects:
            keyboard.append([InlineKeyboardButton(subject, callback_data=f"subject_{grade_id}_{subject}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")])
        await query.edit_message_text(f"📖 **{grade_name} - Subjects**\n\nChoose a subject:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data.startswith("subject_"):
        parts = data.split("_")
        grade_id = parts[1]
        subject = parts[2]
        if not can_access_content(user_id, "shortnote"):
            await query.edit_message_text("❌ Your tier does not allow accessing this content.", parse_mode="Markdown")
            return
        keyboard = []
        for i in range(1, 6):
            keyboard.append([InlineKeyboardButton(f"Chapter {i}", callback_data=f"chapter_{grade_id}_{subject}_{i}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Subjects", callback_data=f"subjects_{grade_id}")])
        await query.edit_message_text(f"📖 **{subject}**\n\nSelect chapter:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("chapter_"):
        parts = data.split("_")
        grade_id = parts[1]
        subject = parts[2]
        chapter = parts[3]
        if not user_has_access(user_id, grade_id):
            await query.edit_message_text("Access denied. Please purchase a subscription or start a free trial.")
            return
        keyboard = []
        if can_access_content(user_id, "shortnote"):
            keyboard.append([InlineKeyboardButton("📘 Short Note", callback_data=f"note_{grade_id}_{subject}_{chapter}")])
        if can_access_content(user_id, "problems"):
            keyboard.append([InlineKeyboardButton("✏️ Solved Problems", callback_data=f"problems_{grade_id}_{subject}_{chapter}")])
        if can_access_content(user_id, "exam"):
            keyboard.append([InlineKeyboardButton("📝 Exam Questions", callback_data=f"exam_{grade_id}_{subject}_{chapter}")])
        if can_access_content(user_id, "pdf"):
            keyboard.append([InlineKeyboardButton("📄 PDF", callback_data=f"pdf_{grade_id}_{subject}_{chapter}")])
        if can_access_content(user_id, "video_tutorial"):
            keyboard.append([InlineKeyboardButton("▶️ Video", callback_data=f"video_{grade_id}_{subject}_{chapter}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Chapters", callback_data=f"subject_{grade_id}_{subject}")])
        await query.edit_message_text(f"**{subject} - Chapter {chapter}**\n\nWhat would you like?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data.startswith("note_"):
        parts = data.split("_")
        grade_id = parts[1]
        subject = parts[2]
        chapter = parts[3]
        grade_name = PRICES[grade_id]["name"]
        content = await read_file_content(grade_name, subject, chapter, "shortnote")
        if content:
            if len(content) > 4000:
                await query.edit_message_text(content[:4000])
                for i in range(4000, len(content), 4000):
                    await query.message.reply_text(content[i:i+4000])
            else:
                await query.edit_message_text(content)
        else:
            await query.edit_message_text(f"📘 No notes for {subject} Chapter {chapter}.", parse_mode="Markdown")
        log_activity(user_id, grade_id, subject, chapter, "note", 30)
        ok, msg = check_user_limits(user_id)
        if not ok:
            await query.message.reply_text(msg)
        update_usage(user_id, 30)
    elif data.startswith("problems_"):
        parts = data.split("_")
        grade_id = parts[1]
        subject = parts[2]
        chapter = parts[3]
        grade_name = PRICES[grade_id]["name"]
        content = await read_file_content(grade_name, subject, chapter, "problems")
        if content:
            if len(content) > 4000:
                await query.edit_message_text(content[:4000])
                for i in range(4000, len(content), 4000):
                    await query.message.reply_text(content[i:i+4000])
            else:
                await query.edit_message_text(content)
        else:
            await query.edit_message_text(f"✏️ No problems for {subject} Chapter {chapter}.", parse_mode="Markdown")
        log_activity(user_id, grade_id, subject, chapter, "problems", 60)
        update_usage(user_id, 60)
    elif data.startswith("exam_"):
        parts = data.split("_")
        grade_id = parts[1]
        subject = parts[2]
        chapter = parts[3]
        await start_exam(update, context, grade_id, subject, chapter)
    elif data.startswith("pdf_"):
        parts = data.split("_")
        grade_id = parts[1]
        subject = parts[2]
        chapter = parts[3]
        grade_name = PRICES[grade_id]["name"]
        try:
            file_id = file_ids["pdf"][grade_name][subject][f"Chapter {chapter}"]
            await query.message.reply_document(file_id)
        except:
            await query.edit_message_text("📄 No PDF available.", parse_mode="Markdown")
        log_activity(user_id, grade_id, subject, chapter, "pdf", 30)
        update_usage(user_id, 30)
    elif data.startswith("video_"):
        parts = data.split("_")
        grade_id = parts[1]
        subject = parts[2]
        chapter = parts[3]
        grade_name = PRICES[grade_id]["name"]
        try:
            url = file_ids["video"][grade_name][subject][f"Chapter {chapter}"]
            keyboard = [[InlineKeyboardButton("▶️ Watch Video", url=url)]]
            await query.edit_message_text("Click the button to watch:", reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await query.edit_message_text("🎥 No video available.", parse_mode="Markdown")
        log_activity(user_id, grade_id, subject, chapter, "video", 60)
        update_usage(user_id, 60)
    elif data.startswith("exam_answer_"):
        parts = data.split("_")
        exam_id = parts[1]
        idx = int(parts[2])
        letter = parts[3]
        await exam_answer_handler(update, context, exam_id, idx, letter)
    elif data.startswith("exam_flag_"):
        parts = data.split("_")
        exam_id = parts[1]
        idx = int(parts[2])
        await exam_flag_handler(update, context, exam_id, idx)
    elif data.startswith("exam_review_"):
        parts = data.split("_")
        exam_id = parts[1]
        idx = int(parts[2])
        await exam_review_handler(update, context, exam_id, idx)
    elif data.startswith("exam_review_answer_"):
        parts = data.split("_")
        exam_id = parts[1]
        idx = int(parts[2])
        letter = parts[3]
        await exam_review_answer_handler(update, context, exam_id, idx, letter)
    elif data.startswith("exam_back_to_flags_"):
        exam_id = data.split("_")[3]
        await show_flagged_review(context.bot, query.message.chat_id, exam_id)
    elif data == "exam_cancel":
        exam_id = context.user_data.get("current_exam")
        if exam_id and exam_id in bot_data["exam_sessions"]:
            del bot_data["exam_sessions"][exam_id]
            save_data(bot_data)
        await query.edit_message_text("Exam cancelled.", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to Chapter", callback_data=f"chapter_{context.user_data.get('current_grade', '1')}_{context.user_data.get('current_subject', '')}_{context.user_data.get('current_chapter', '1')}")
        ]]))
    elif data.startswith("exam_submit_"):
        exam_id = data.split("_")[2]
        await finish_exam(context.bot, query.message.chat_id, exam_id)
    else:
        await query.edit_message_text(f"❌ Unknown command.\n{ADMIN_CONTACT}", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")
        ]]))
        # ----------------------------- MESSAGE HANDLER (for text and media) -----------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    uid = str(user_id)
    text = update.message.text

    # Admin password login
    if context.user_data.get("awaiting_admin_password"):
        if text == ADMIN_PASSWORD:
            bot_data["admin_logged_in"] = True
            save_data(bot_data)
            context.user_data.pop("awaiting_admin_password")
            await update.message.reply_text("✅ Admin login successful.", reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔧 Admin Panel", callback_data="admin_menu")
            ]]))
        else:
            record_failed_attempt(user_id)
            await update.message.reply_text("❌ Wrong password.")
        return

    # Admin upload step-by-step
    if context.user_data.get("admin_upload_step"):
        step = context.user_data["admin_upload_step"]
        if step == 1:
            context.user_data["upload_grade"] = text
            context.user_data["admin_upload_step"] = 2
            await update.message.reply_text("Send **subject name**:")
        elif step == 2:
            context.user_data["upload_subject"] = text
            context.user_data["admin_upload_step"] = 3
            await update.message.reply_text("Send **chapter number** (e.g., 1):")
        elif step == 3:
            context.user_data["upload_chapter"] = text
            context.user_data["admin_upload_step"] = 4
            await update.message.reply_text("Send **file type** (pdf / video / ppt / ministry_exercise / matric_exercise):")
        elif step == 4:
            context.user_data["upload_type"] = text.lower()
            context.user_data["admin_upload_step"] = 5
            if text.lower() == "video":
                await update.message.reply_text("Send the **YouTube URL**:")
            else:
                await update.message.reply_text("Send the **file** (document or photo):")
        elif step == 5:
            if context.user_data["upload_type"] == "video":
                url = text
                grade = context.user_data["upload_grade"]
                subject = context.user_data["upload_subject"]
                chapter = context.user_data["upload_chapter"]
                file_ids["video"].setdefault(grade, {}).setdefault(subject, {})[f"Chapter {chapter}"] = url
                save_file_ids(file_ids)
                await update.message.reply_text("✅ Video URL stored.")
            else:
                if not update.message.document:
                    await update.message.reply_text("Please send a document.")
                    return
                file_id = update.message.document.file_id
                grade = context.user_data["upload_grade"]
                subject = context.user_data["upload_subject"]
                chapter = context.user_data["upload_chapter"]
                ftype = context.user_data["upload_type"]
                file_ids.setdefault(ftype, {}).setdefault(grade, {}).setdefault(subject, {})[f"Chapter {chapter}"] = file_id
                save_file_ids(file_ids)
                await update.message.reply_text("✅ File stored.")
            context.user_data.pop("admin_upload_step", None)
            context.user_data.pop("upload_grade", None)
            context.user_data.pop("upload_subject", None)
            context.user_data.pop("upload_chapter", None)
            context.user_data.pop("upload_type", None)
        return

    # Admin search
    if context.user_data.get("admin_search"):
        query = text.lower()
        results = []
        for uid, u in bot_data["users"].items():
            if (query in u["ti"].lower() or query in u["full_name"].lower() or
                query in u["school"].lower() or query in u["contact"].lower()):
                results.append((u["ti"], u["full_name"], u["school"], u["contact"]))
        if results:
            msg = "🔍 **Search results:**\n\n"
            for ti, name, school, contact in results[:10]:
                msg += f"`{ti}` - {name} ({school})\n"
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text("No users found.")
        context.user_data.pop("admin_search")
        return

    # Admin remove
    if context.user_data.get("admin_remove"):
        ti = text.strip()
        found = None
        for uid, u in bot_data["users"].items():
            if u["ti"] == ti:
                found = uid
                break
        if found:
            del bot_data["users"][found]
            save_data(bot_data)
            await update.message.reply_text(f"✅ User {ti} removed.")
        else:
            await update.message.reply_text("❌ User not found.")
        context.user_data.pop("admin_remove")
        return

    # Admin add
    if context.user_data.get("admin_add_step"):
        step = context.user_data["admin_add_step"]
        if step == 1:
            ti = text.strip()
            if ti.lower() == "auto":
                ti = generate_ti()
            context.user_data["add_ti"] = ti
            context.user_data["admin_add_step"] = 2
            await update.message.reply_text("Send **full name**:")
        elif step == 2:
            context.user_data["add_name"] = text
            context.user_data["admin_add_step"] = 3
            await update.message.reply_text("Send **school name**:")
        elif step == 3:
            context.user_data["add_school"] = text
            context.user_data["admin_add_step"] = 4
            await update.message.reply_text("Send **contact number**:")
        elif step == 4:
            context.user_data["add_contact"] = text
            context.user_data["admin_add_step"] = 5
            await update.message.reply_text("Send **grade ID** (e.g., 1, 5, 11):")
        elif step == 5:
            grade_id = text.strip()
            if grade_id not in PRICES:
                await update.message.reply_text("Invalid grade ID.")
                return
            context.user_data["add_grade"] = grade_id
            context.user_data["admin_add_step"] = 6
            await update.message.reply_text("Send **tier** (Basic/VIP/VVIP):")
        elif step == 6:
            tier = text.strip().capitalize()
            if tier not in ["Basic", "VIP", "VVIP"]:
                await update.message.reply_text("Invalid tier.")
                return
            context.user_data["add_tier"] = tier
            context.user_data["admin_add_step"] = 7
            await update.message.reply_text("Send **package** (1M/3M/6M/1Y/FULL):")
        elif step == 7:
            pkg = text.strip()
            if pkg not in PRICES[context.user_data["add_grade"]]["tiers"][context.user_data["add_tier"]]:
                await update.message.reply_text("Invalid package.")
                return
            expiry = get_expiry_date(pkg, context.user_data["add_tier"])
            bot_data["users"][str(update.effective_user.id)] = {
                "ti": context.user_data["add_ti"],
                "full_name": context.user_data["add_name"],
                "school": context.user_data["add_school"],
                "contact": context.user_data["add_contact"],
                "grade": context.user_data["add_grade"],
                "grade_name": PRICES[context.user_data["add_grade"]]["name"],
                "tier": context.user_data["add_tier"],
                "package": pkg,
                "expiry": expiry,
                "original_transaction": "admin_add"
            }
            save_data(bot_data)
            await update.message.reply_text(f"✅ User {context.user_data['add_ti']} added.")
            context.user_data.pop("admin_add_step", None)
            context.user_data.pop("add_ti", None)
            context.user_data.pop("add_name", None)
            context.user_data.pop("add_school", None)
            context.user_data.pop("add_contact", None)
            context.user_data.pop("add_grade", None)
            context.user_data.pop("add_tier", None)
        return

    # Admin announcement
    if context.user_data.get("admin_announce"):
        for uid in bot_data["users"].keys():
            try:
                await context.bot.send_message(int(uid), f"📢 **Announcement**\n\n{text}", parse_mode="Markdown")
            except:
                pass
        await update.message.reply_text("✅ Announcement sent to all users.")
        context.user_data.pop("admin_announce")
        return

    # User registration flow
    if context.user_data.get("pending_registration") and context.user_data.get("reg_step"):
        await process_registration(update, context)
        return

    # Payment pending (screenshot or transaction ID)
    if uid in bot_data["pending_payments"]:
        pending = bot_data["pending_payments"][uid]
        if not pending["sent_to_admin"] and (update.message.photo or update.message.document):
            media = update.message.photo[-1] if update.message.photo else update.message.document
            file_id = media.file_id
            ocr_text = await extract_text_from_media(file_id, context) if TESSERACT_AVAILABLE else None
            details = parse_transaction_details(ocr_text) if ocr_text else {}
            pending["screenshot_file_id"] = file_id
            pending["screenshot_text"] = ocr_text
            save_data(bot_data)
            auto_valid, reason = is_transaction_valid(details, datetime.now()) if ocr_text else (False, "no_ocr")
            if auto_valid:
                await update.message.reply_text("✅ Payment auto-verified! Please complete registration.")
                await register_user(update, context, user_id, pending["grade_id"], pending["tier"], pending["package"], pending.get("transaction_id", "auto"))
                del bot_data["pending_payments"][uid]
                save_data(bot_data)
            else:
                try:
                    if update.message.photo:
                        await context.bot.send_photo(ADMIN_IDS[0], file_id, caption=f"Payment from {uid}\nGrade: {pending['grade_id']}\nTier: {pending['tier']}\nPackage: {pending['package']}")
                    else:
                        await context.bot.send_document(ADMIN_IDS[0], file_id, caption=f"Payment from {uid}\nGrade: {pending['grade_id']}\nTier: {pending['tier']}\nPackage: {pending['package']}")
                except:
                    pass
                pending["sent_to_admin"] = True
                save_data(bot_data)
                await update.message.reply_text(f"📸 Screenshot received. Admin will verify soon.\n{ADMIN_CONTACT}", parse_mode="Markdown")
            return
        elif not pending["transaction_id"] and text:
            pending["transaction_id"] = text
            save_data(bot_data)
            await update.message.reply_text("✅ Transaction ID saved. Please also send a screenshot if not already sent.", parse_mode="Markdown")
            return
        else:
            await update.message.reply_text(f"⏳ Your payment is being verified. Please wait.\n{ADMIN_CONTACT}", parse_mode="Markdown")
            return

    # Returning user identification
    if context.user_data.get("awaiting_ti"):
        ti_input = text.strip()
        found = None
        for uid, u in bot_data["users"].items():
            if u["ti"] == ti_input:
                found = uid
                break
        if found:
            device_fp = get_device_fingerprint(update)
            register_device(int(found), device_fp)
            await update.message.reply_text(f"✅ Welcome back! Your TI `{ti_input}` is recognized. Use /start to access materials.", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ TI not found. Please check or contact admin.")
        context.user_data.pop("awaiting_ti")
        return

    # No pending payment, no registration, no admin
    await update.message.reply_text(f"I don't understand. Type /start to begin.\n{ADMIN_CONTACT}", reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("🏠 Start Over", callback_data="restart")
    ]]))

# ----------------------------- FLASK WEBHOOK SERVER -----------------------------
flask_app = Flask(__name__)
telegram_app = None

@flask_app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if telegram_app is None:
        return 'Bot not ready', 500
    try:
        json_data = request.get_json(force=True)
        update = Update.de_json(json_data, telegram_app.bot)
        telegram_app.process_update(update)
        return 'OK', 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return 'Error', 500

@flask_app.route('/health', methods=['GET'])
def health():
    return 'OK', 200

async def setup_webhook():
    webhook_url = os.environ.get('WEBHOOK_URL', '')
    if not webhook_url:
        print("⚠️ WEBHOOK_URL not set.")
        return
    full_url = f"{webhook_url}/{BOT_TOKEN}"
    await telegram_app.bot.set_webhook(full_url)
    print(f"✅ Webhook set to {full_url}")

async def main():
    global telegram_app
    print("🚀 Starting bot in webhook mode...")
    telegram_app = Application.builder().token(BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CallbackQueryHandler(button_handler))
    telegram_app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.TEXT & ~filters.COMMAND, handle_message))
    await telegram_app.initialize()
    await setup_webhook()
    port = int(os.environ.get('PORT', 5000))
    flask_app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())