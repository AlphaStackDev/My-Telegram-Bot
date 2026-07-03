import asyncio
import asyncpg
import os
import aiohttp
import re
import shutil
import tempfile

from urllib.parse import urlparse
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile, CallbackQuery, Message, Update
from aiogram.utils.keyboard import InlineKeyboardBuilder


from dotenv import load_dotenv
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from database import db_execute, db_fetch_one # Ensure your db module is imported

# =====================
# CONFIG (EDIT THESE)
# =====================
DB_CONFIG = {
    "host": "localhost",
    "user": "postgres",        # Change this from "root" to "postgres"
    "password": "Alpha.com002",
    "database": "unical_bot",
    "autocommit": True,
}

# ALPHA_TOKEN here...
load_dotenv() # This reads the local .env file
ALPHA_TOKEN = os.environ.get('ALPHA_BOT_TOKEN')

# Telegram user id (admin)
ADMIN_TELEGRAM_ID = 8271633745
# ID here
ADMIN_ID = 8271633745

# Where to store downloads temporarily (secure PDFs created on-the-fly)

TMP_DIR = os.path.join(os.getcwd(), "tmp_secure")
os.makedirs(TMP_DIR, exist_ok=True)

# (Optional helper)
async def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID
# =====================
# BOT INIT
# =====================
# We will not use AiohttpSession for now to avoid the compatibility crash.
# We will use the standard Bot initialization.
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# =====================
# DB helpers
# =====================

async def pg_query(query: str, params: tuple = ()):
    """Small helper around asyncpg that uses DB_CONFIG['database'] (not 'db')."""
    conn = await asyncpg.connect(
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        host=DB_CONFIG["host"],
    )
    try:
        return await conn.execute(query, *params)
    finally:
        await conn.close()

async def db_fetch_one(query: str, params: tuple):
    conn = await asyncpg.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"]
    )
    try:
        row = await conn.fetchrow(query, *params)
        return dict(row) if row else None
    finally:
        await conn.close()

async def db_fetch_all(query: str, params: tuple):
    conn = await asyncpg.connect(
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        host=DB_CONFIG["host"],
    )
    try:
        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def db_execute(query: str, params: tuple):
    conn = await asyncpg.connect(
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        host=DB_CONFIG["host"],
    )
    try:
        await conn.execute(query, *params)
    finally:
        await conn.close()


# =====================
# Registration FSM
# =====================
class RegistrationStates(StatesGroup):
    full_name = State()
    email = State()
    reg_number = State()
    level = State()  # New state

def normalize_reg_number(s: str) -> str:
    s = s.strip().upper()
    s = re.sub(r"\s+", "", s)
    return s


def validate_email(email: str) -> bool:
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()) is not None


# =====================
# Inline keyboard builders
# =====================
LEVELS = [100, 200, 300, 400]


async def send_faculty_menu(message: types.Message):
    faculties = await db_fetch_all("SELECT id, name FROM faculties ORDER BY name", tuple())
    if not faculties:
        await message.answer("No faculties found. Ask admin to upload faculties.")
        return

    kb = InlineKeyboardBuilder()
    for f in faculties:
        kb.button(text=f["name"], callback_data=f"faculty:{f['id']}")
    kb.adjust(2)
    await message.answer("Select your Faculty:", reply_markup=kb.as_markup())


async def send_department_menu(message: types.Message, faculty_id: int):
    departments = await db_fetch_all(
        "SELECT id, name FROM departments WHERE faculty_id = $1 ORDER BY name",
        (faculty_id,),
    )
    if not departments:
        await message.answer("No departments found for this faculty.")
        return

    kb = InlineKeyboardBuilder()
    for d in departments:
        kb.button(text=d["name"], callback_data=f"department:{d['id']}")
    kb.adjust(2)
    await message.answer("Select Department:", reply_markup=kb.as_markup())


async def send_course_menu(message: types.Message, department_id: int):
    courses = await db_fetch_all(
        "SELECT id, course_code, course_title, level FROM courses WHERE department_id = $1 ORDER BY level, course_code",
        (department_id,),
    )
    if not courses:
        await message.answer("No courses found for this department.")
        return

    # Show by course_code + level (since your requirement includes levels)
    kb = InlineKeyboardBuilder()
    for c in courses:
        title = f"{c['course_code']} ({c['level']}L)"
        kb.button(
            text=title,
            callback_data=f"course:{c['id']}",
        )
    kb.adjust(1)
    await message.answer("Select Course:", reply_markup=kb.as_markup())


async def send_level_menu(message: types.Message, course_id: int, available_levels: list[int]):
    kb = InlineKeyboardBuilder()
    for lvl in available_levels:
        kb.button(text=f"{lvl} Level", callback_data=f"level:{course_id}:{lvl}")
    kb.adjust(2)
    await message.answer("Select Level:", reply_markup=kb.as_markup())


# =====================
# PDF security processing
# =====================
async def fetch_pdf_to_file(source: str, dest_path: str) -> None:
    """Fetch a PDF from either a local file path or an HTTP(S) URL."""

    # If source is already a local Windows path, we should never go through urlparse/
    # URL-downloader logic.
    if source.startswith("\\\\") or (len(source) >= 2 and source[1] == ":") or source.lower().startswith("file:"):
        local_path = source
        if local_path.lower().startswith("file:"):
            local_path = local_path[5:]

        # decode common db/url-encoded artifacts (e.g. c:%5C%5C...) 
        local_path = local_path.replace("%5C", "\\").replace("%3A", ":")

        # Normalize relative paths
        if not os.path.isabs(local_path):
            local_path = os.path.abspath(local_path)

        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local PDF not found: {local_path} (from source={source})")

        shutil.copyfile(local_path, dest_path)
        return

    # Otherwise treat as URL
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(source) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(1024 * 1024):
                    f.write(chunk)


def secure_pdf(input_pdf_path: str, output_pdf_path: str, reg_number: str) -> None:
    # 1) watermark PDF -> merge onto each page
    watermark_path = os.path.join(TMP_DIR, f"watermark_{os.getpid()}.pdf")

    c = canvas.Canvas(watermark_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 40)
    c.setFillAlpha(0.2)
    c.rotate(45)
    c.drawString(100, 100, str(reg_number))
    c.save()

    watermark_reader = PdfReader(watermark_path)
    watermark_page = watermark_reader.pages[0]

    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()

    for page in reader.pages:
        page.merge_page(watermark_page)
        writer.add_page(page)

    # 2) encrypt with reg number as password
    # PyPDF supports encrypt(password, algorithm)
    writer.encrypt(str(reg_number), algorithm="AES-256")

    with open(output_pdf_path, "wb") as f:
        writer.write(f)

    try:
        if os.path.exists(watermark_path):
            os.remove(watermark_path)
    except Exception:
        pass


# =====================
# Main user actions
# =====================
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):

    await state.clear()
    print(f"DEBUG: Start command received from {message.from_user.id}")
    # If already registered, go to faculty menu
    existing = await db_fetch_one(
        "SELECT telegram_id FROM students WHERE telegram_id = $1",
        (message.from_user.id,),
    )
    if existing:
        await message.answer("Welcome back! Choose what you want to download.")
        await send_faculty_menu(message)
        return

    await message.answer("Welcome! Let's register.")
    await state.set_state(RegistrationStates.full_name)
    await message.answer("1) Send your full name (as it appears on UNICAL portal).")


@dp.message(Command("logout"))
async def logout_cmd(message: types.Message, state: FSMContext):
    # This deletes the user's data from your database, forcing a fresh start
    await db_execute("DELETE FROM students WHERE telegram_id = $1", (message.from_user.id,))
    await state.clear()
    await message.answer("You have been logged out. Send /start to register a new student.")


@dp.message(RegistrationStates.full_name)
async def reg_full_name(message: types.Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name) < 3:
        await message.answer("Please enter a valid full name.")
        return
    await state.update_data(full_name=full_name)
    await state.set_state(RegistrationStates.email)
    await message.answer("2) Send your UNICAL email address.")


@dp.message(RegistrationStates.email)
async def reg_email(message: types.Message, state: FSMContext):
    email = message.text.strip()
    if not validate_email(email):
        await message.answer("Invalid email format. Example: name@student.unical.edu.ng")
        return

    await state.update_data(email=email)
    await state.set_state(RegistrationStates.reg_number)
    await message.answer("3) Send your UNICAL registration number.")


@dp.message(RegistrationStates.reg_number)
async def reg_reg_number(message: types.Message, state: FSMContext):
    reg_number = normalize_reg_number(message.text)
    if len(reg_number) < 5:
        await message.answer("Registration number seems too short. Try again.")
        return

    data = await state.get_data()
    full_name = data["full_name"]
    email = data["email"]

    # Insert if not exists
    existing = await db_fetch_one(
"SELECT telegram_id FROM students WHERE telegram_id = $1",
        (message.from_user.id,),
    )
    if existing:
        await message.answer("You are already registered.")
        await send_faculty_menu(message)
        await state.clear()
        return

    existing_email = await db_fetch_one(
"SELECT telegram_id FROM students WHERE email = $1",
        (email,),
    )
    if existing_email:
        await message.answer("This email is already registered. If this is you, contact admin.")
        return

    await db_execute(
"INSERT INTO students (telegram_id, full_name, email, reg_number, download_count) VALUES ($1, $2, $3, $4, 0)",
        (message.from_user.id, full_name, email, reg_number),
    )

# Instead of finishing registration immediately, ask the student to select their level
    data = await state.get_data()
    await state.clear()

    # Ask for level selection from `levels` table.
    levels = await db_fetch_all("SELECT id, name FROM levels ORDER BY id", tuple())
    if not levels:
        await message.answer("Registration saved ✅, but levels are not set up. Ask admin to add levels.")
        await send_faculty_menu(message)
        return

    kb = InlineKeyboardBuilder()
    for lvl in levels:
        kb.button(text=lvl["name"], callback_data=f"set_level:{lvl['id']}")

    await message.answer(
        "Registration successful ✅\nSelect your current academic level:",
        reply_markup=kb.as_markup(),
    )
    await state.set_state(RegistrationStates.level)

    return

    if not levels:
        await message.answer("Registration saved ✅, but levels are not set up. Ask admin to add levels.")
        await send_faculty_menu(message)
        return

    kb = InlineKeyboardBuilder()
    for lvl in levels:
        kb.button(text=lvl["name"], callback_data=f"set_level:{lvl['id']}")

    await message.answer(
        "Registration successful ✅\nSelect your current academic level:",
        reply_markup=kb.as_markup(),
    )
    # Store minimal data via DB insert already done; move FSM to level selection state
    await state.set_state(RegistrationStates.level)


@dp.callback_query(F.data.startswith("faculty:"))
async def cb_faculty(call: types.CallbackQuery):
    _, fid = call.data.split(":", 1)
    await call.answer()
    await send_department_menu(call.message, int(fid))


@dp.callback_query(F.data.startswith("department:"))
async def cb_department(call: types.CallbackQuery):
    _, did = call.data.split(":", 1)
    await call.answer()

    kb = await get_level_keyboard(int(did))
    await call.message.edit_text("Select Level:", reply_markup=kb)


@dp.callback_query(F.data.startswith("set_level:"))
async def save_student_level(callback: CallbackQuery, state: FSMContext):
    level_id = int(callback.data.split(":", 1)[1])

    # Update student with selected level
    await db_execute(
        "UPDATE students SET level_id = $1 WHERE telegram_id = $2",
        (level_id, callback.from_user.id),
    )

    await state.clear()
    await callback.message.edit_text("Level saved ✅. Choose your Faculty to continue.")
    await send_faculty_menu(callback.message)

@dp.callback_query(F.data.startswith("course:"))
async def cb_course(call: types.CallbackQuery):
    # Keep backward compatibility with existing callback_data = "course:<course_id>"
    _, cid = call.data.split(":", 1)
    await call.answer()



    # We already store level per course row; so we show levels that exist for that course id.
    # For simplicity: fetch all rows for the same course_id only to get the level.
    # Your schema suggests 1 row per course+level. We'll treat course row itself as the downloadable unit.
    course = await db_fetch_one(
"SELECT id, level FROM courses WHERE id = $1",
        (int(cid),),
    )
    if not course:
        await call.message.answer("Course not found.")
        return

    # present a single level button that triggers download
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=f"Download ({course['level']}L)", callback_data=f"download:{course['id']}")]]
    )
    await call.message.answer("Ready to download:", reply_markup=kb)

async def can_download_and_increment(telegram_id: int) -> tuple[bool, int]:
    # Query now checks both count AND payment status
    student = await db_fetch_one(
        "SELECT download_count, has_paid FROM students WHERE telegram_id = $1",
        (telegram_id,),
    )
    if not student:
        return False, 0

    count = int(student.get("download_count") or 0)
    has_paid = student.get("has_paid")

    # If they have paid, they get unlimited downloads
    if has_paid:
        return True, count

    # If they haven't paid, limit to 2
    if count < 2:
        await db_execute(
            "UPDATE students SET download_count = download_count + 1 WHERE telegram_id = $1",
            (telegram_id,),
        )
        return True, count + 1

    return False, count



async def get_student_reg_number(telegram_id: int) -> str | None:
    student = await db_fetch_one(
        "SELECT reg_number FROM students WHERE telegram_id = $1",
        (telegram_id,),
    )
    if not student:
        return None
    return student.get("reg_number")



PRICES = {
    "sem1": 1,
    "sem2": 1,
    "all": 4,
}

async def can_download(telegram_id: int, course_id: int) -> bool:
    course = await db_fetch_one("SELECT semester FROM courses WHERE id = $1", (course_id,))
    student = await db_fetch_one(
        "SELECT has_paid_sem1, has_paid_sem2, has_paid_all FROM students WHERE telegram_id = $1",
        (telegram_id,),
    )
    
    if not course or not student:
        return False
    
    if student.get("has_paid_all"):
        return True
    
    sem = int(course.get("semester", 0))
    if sem == 1 and student.get("has_paid_sem1"): return True
    if sem == 2 and student.get("has_paid_sem2"): return True
    
    return False




async def show_payment_options(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="Pay Semester (₦1,500 / $1)", callback_data="pay_sem")
    kb.button(text="Pay All Levels (₦6,000 / $4)", callback_data="pay_all")
    kb.button(text="📤 I have paid, send receipt", callback_data="send_receipt")
    kb.adjust(1)

    await message.answer(
        """⚠️ <b>Limit Reached!</b>

You have reached your 2 free download limit. To unlock more content, please pay using the details below:

<b>Bank:</b> Moniepoint
<b>Account Number:</b> 8084577652
<b>Account Name:</b> Elemi Sampson Ele

<b>Pricing:</b>
• <b>Per Semester:</b> ₦1,500 ($1)
• <b>All Levels:</b> ₦6,000 ($4)

<i>Please select your plan below, then click the button below to send your receipt.</i>""",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )






async def generate_ticket(telegram_id: int, level_choice: str):
    import random

    ticket_no = f"TKT-{random.randint(1000, 9999)}"
    amount = PRICES[level_choice]

    await db_execute(
        "INSERT INTO payments (ticket_no, telegram_id, amount_paid, is_approved) VALUES ($1, $2, $3, $4)",
        (ticket_no, telegram_id, amount, False),
    )
    return ticket_no, amount

@dp.callback_query(F.data == "pay_single" or F.data == "pay_all")
async def payment_prompt(callback: CallbackQuery):
    choice = "single" if callback.data == "pay_single" else "all"
    ticket, amount = await generate_ticket(callback.from_user.id, choice)

    await callback.message.answer(
        f"<b>PAYMENT INSTRUCTIONS</b>\n"
        f"Ticket Number: <code>{ticket}</code>\n"
        f"Amount: ${amount}\n"
        f"Bank: Moniepoint\nAcc: 8084577652 | Elemi Sampson Ele\n\n"
        f"Converted to Naira: 1 USD = ₦1,500\n"
        f"Price: ₦1,500 per semester\n" # Updated with Naira sign
        f"Price: ₦6,000 for all levels", # Updated with Naira sign
        f"Please send proof and your Ticket Number to verify.",
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "send_receipt")
async def process_receipt_instruction(call: types.CallbackQuery):
    await call.message.answer(
        "<b>Instructions to unlock your account:</b>\n\n"
        "1. Take a screenshot of your payment receipt.\n"
        "2. Send the image to this chat.\n"
        "3. <b>Important:</b> You MUST include your Student ID in the caption.\n"
        f"<code>ID: {call.from_user.id}</code>",
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("approve_ticket_"))
async def approve_payment(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_TELEGRAM_ID:
        await callback.answer("Admin only", show_alert=True)
        return

    ticket_no = callback.data.split("_", 2)[2]
    await db_execute(
        "UPDATE payments SET is_approved = TRUE WHERE ticket_no = $1",
        (ticket_no,),
    )

    payment = await db_fetch_one(
        "SELECT telegram_id, amount_paid FROM payments WHERE ticket_no = $1",
        (ticket_no,),
    )
    if not payment:
        await callback.answer("Payment not found", show_alert=True)
        return

    if payment.get("amount_paid", 0) >= 4:
        await db_execute(
            "UPDATE students SET has_paid_all = TRUE WHERE telegram_id = $1",
            (payment["telegram_id"],),
        )

    await bot.send_message(
        payment["telegram_id"],
        f"Your payment with Ticket {ticket_no} has been approved! You now have access.",
    )
    await callback.message.edit_text(f"Approved Ticket: {ticket_no}")

@dp.message(F.photo)
async def forward_to_admin(message: types.Message):
    # Forward the receipt to your Admin Bot chat
    await bot.forward_message(
        chat_id=ADMIN_TELEGRAM_ID,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
    )

    contact_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📩 Contact Admin",
                    url="https://t.me/Alpha_Padminbot",
                )
            ]
        ]
    )

    await message.answer(
        "✅ Receipt sent! Please wait for the admin to approve your payment.",
        reply_markup=contact_kb,
    )


@dp.message(Command("approve"))
async def approve_student(message: types.Message):
    if message.from_user.id != ADMIN_TELEGRAM_ID:
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /approve <telegram_id>")
        return

    student_id = int(args[1])

    await db_execute(
        "UPDATE students SET has_paid = TRUE, download_count = 0 WHERE telegram_id = $1",
        (student_id,),
    )

    await message.answer(f"✅ Student {student_id} has been approved.")
    await bot.send_message(student_id, "🎉 Payment approved! You can now download your files.")


@dp.callback_query(F.data.startswith("download:"))
async def cb_download(call: types.CallbackQuery):
    _, cid = call.data.split(":", 1)
    course_id = int(cid)
    telegram_id = call.from_user.id

    # 1. Check Paid Access
    if not await can_download(telegram_id, course_id):
        # 2. If not paid, check/increment free count
        ok, _ = await can_download_and_increment(telegram_id)
        if not ok:
            await call.answer("Limit reached.")
            await show_payment_options(call.message)
            return

    # 3. Proceed with Download Logic
    reg_number = await get_student_reg_number(telegram_id)
    if not reg_number:
        await call.message.answer("Registration incomplete. Use /start.")
        return

    course = await db_fetch_one("SELECT course_code, level FROM courses WHERE id = $1", (course_id,))
    if not course:
        await call.message.answer("Course not found.")
        return

    # Path Setup
    BASE_DIR = r"C:\Users\User\My_Telegram_Bot\My_PDFs\Economics 200 Level Q&P"
    filename = f"{course['course_code'].strip()}.pdf"
    raw_source = os.path.join(BASE_DIR, filename)
    raw_path = os.path.join(TMP_DIR, f"raw_{telegram_id}_{course_id}.pdf")
    secure_path = os.path.join(TMP_DIR, f"secure_{telegram_id}_{course_id}.pdf")

    if not os.path.exists(raw_source):
        await call.message.answer("Error: File not found on server.")
        return

    status_msg = await call.message.answer("⏳ Preparing secure document...")
    try:
        await fetch_pdf_to_file(raw_source, raw_path)
        secure_pdf(raw_path, secure_path, reg_number)
        await call.message.answer_document(
            document=types.FSInputFile(secure_path),
            caption=f"✅ Secured for {reg_number}"
        )
        await status_msg.delete()
    except Exception as e:
        await call.message.answer(f"Failed to prepare document: {e}")
    finally:
        for p in (raw_path, secure_path):
            if os.path.exists(p): os.remove(p)

    return


# =====================
# Past questions by course_code (Q&P PDFs)
# =====================

PDF_BASE_DIR = r"C:\\Users\\User\\My_Telegram_Bot\\My_PDFs\\Economics 200 Level Q&P"


async def get_level_keyboard(department_id: int):
    builder = InlineKeyboardBuilder()
    levels = [100, 200, 300, 400]
    for level in levels:
        builder.button(
            text=f"{level} Level",
            callback_data=f"level_{level}_{department_id}",
        )
    builder.adjust(2)
    return builder.as_markup()


@dp.callback_query(F.data.startswith("level_"))
async def cb_level(callback: types.CallbackQuery):
    # callback_data: level_{level}_{department_id}
    _, lvl_str, dept_id_str = callback.data.split("_", 2)

    department_id = int(dept_id_str)
    level = int(lvl_str)

    kb = InlineKeyboardBuilder()
    kb.button(text="1st Semester", callback_data=f"sem_1_{level}_{department_id}")
    kb.button(text="2nd Semester", callback_data=f"sem_2_{level}_{department_id}")
    kb.adjust(2)

    await callback.answer()
    await callback.message.edit_text(
        "Select Semester:",
        reply_markup=kb.as_markup(),
    )


@dp.callback_query(F.data.startswith("sem_"))
async def cb_semester(callback: types.CallbackQuery):
    _, sem_str, lvl_str, dept_id_str = callback.data.split("_", 3)

    semester = int(sem_str)
    level = int(lvl_str)
    department_id = int(dept_id_str)

    print(f"DEBUG: Querying with: dept_id={department_id}, level={level}, semester={semester}")

    courses = await db_fetch_all(
        "SELECT id, course_code FROM courses WHERE department_id = $1 AND level = $2 AND semester = $3",
        (department_id, level, semester),
    )

    print(f"DEBUG: Courses found: {courses}")

    if not courses:
        await callback.answer(
            f"No courses for Dept:{department_id} Lvl:{level} Sem:{semester}",
            show_alert=True,
        )
        return

    kb = InlineKeyboardBuilder()
    for c in courses:
        kb.button(text=c["course_code"], callback_data=f"download:{c['id']}")
    kb.adjust(2)

    await callback.answer()
    await callback.message.edit_text(
        f"Courses for {level} Level, {semester}nd Semester:",
        reply_markup=kb.as_markup(),
    )


@dp.callback_query(F.data.startswith("course_"))
async def send_pdf_to_student(callback: CallbackQuery):

    course_code = callback.data.split("_", 1)[1]

    row = await db_fetch_one(
        "SELECT file_url FROM courses WHERE course_code = $1 LIMIT 1",
        (course_code,),
    )
    if not row:
        await callback.answer("Sorry, this file is not available yet.")
        return

    filename = row.get("file_url")
    if not filename:
        await callback.answer("Sorry, this file is not available yet.")
        return

    file_path = os.path.join(PDF_BASE_DIR, filename)
    document = FSInputFile(file_path)
    await callback.message.answer_document(
        document=document,
        caption=f"Here is your {course_code} past question.",
    )


# =====================
# Admin: upload/update catalog
# =====================
from aiogram.types import FSInputFile, CallbackQuery, Message


@dp.message(Command("admin"))
async def admin_cmd(message: types.Message):
    if message.from_user.id != ADMIN_TELEGRAM_ID:
        await message.answer("Access denied.")
        return
    await message.answer("Admin mode enabled. Use:")
    await message.answer(
        "\n".join(
            [
                "/add_faculty Name",
                "/add_department FacultyID Name",
                "/add_course DepartmentID CourseCode Level FileURL",
                "\nExample file URL: C:\\pdfs\\Eco201.pdf OR https://example.com/Eco204.pdf",
            ]
        )
    )


@dp.message(F.text.startswith("/add_faculty "))
async def add_faculty(message: types.Message):
    if message.from_user.id != ADMIN_TELEGRAM_ID:
        return await message.answer("Access denied.")

    name = message.text.replace("/add_faculty ", "", 1).strip()
    if not name:
        return await message.answer("Usage: /add_faculty Name")

    await db_execute("INSERT INTO faculties (name) VALUES ($1)", (name,))
    await message.answer("Faculty added ✅")


@dp.message(F.text.startswith("/add_department "))
async def add_department(message: types.Message):
    if message.from_user.id != ADMIN_TELEGRAM_ID:
        return await message.answer("Access denied.")

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.answer("Usage: /add_department FacultyID Name")

    _, faculty_id_str, name = parts
    faculty_id = int(faculty_id_str)
    await db_execute(
        "INSERT INTO departments (faculty_id, name) VALUES ($1, $2)",
        (faculty_id, name.strip()),
    )
    await message.answer("Department added ✅")


@dp.message(F.text.startswith("/add_course "))
async def add_course(message: types.Message):
    if message.from_user.id != ADMIN_TELEGRAM_ID:
        return await message.answer("Access denied.")

    rest = message.text[len("/add_course ") :].strip()
    parts = rest.split(maxsplit=3)
    if len(parts) < 4:
        return await message.answer("Usage: /add_course DepartmentID CourseCode Level FileURL")

    dept_id_str, course_code, level_str, file_url = parts
    dept_id = int(dept_id_str)
    level = int(level_str)
    if level not in (100, 200, 300, 400):
        return await message.answer("Level must be one of: 100, 200, 300, 400")

    await db_execute(
        "INSERT INTO courses (department_id, course_code, level, file_url) VALUES ($1, $2, $3, $4)",
        (dept_id, course_code.strip(), level, file_url.strip()),
    )
    await message.answer("Course added ✅")


# =====================
# Polling main loop (disabled in webhook-only Render deployment)
# =====================
async def main():
    # Keep for local testing, but do NOT call under Render webhook mode.
    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            print("Starting bot polling (with reset)...")
            await dp.start_polling(bot, drop_pending_updates=True, handle_signals=False)

        except Exception as e:
            print(f"Connection dropped: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5) # Wait 5 seconds before trying again


# =====================
# Flask webhook (Render-friendly)
# =====================
# Webhook-only mode: Flask receives Telegram updates and aiogram processes them.
# NOTE: Telegram webhook URL path must match `/webhook` below.
from flask import Flask, request

flask_app = Flask(__name__)


@flask_app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_json(force=True, silent=True) or {}

    # Convert raw JSON -> aiogram Update
    try:
        update = Update.model_validate(payload)
    except Exception:
        # If Telegram sends unexpected payload, respond ok to avoid retries.
        return "ok", 200

    # aiogram expects updates to be fed into its dispatcher
    async def _handle():
        await dp.feed_update(bot, update)

    # Run the async handler and return quickly.
    asyncio.run(_handle())
    return "ok", 200


async def run_alpha_bot() -> None:
    # Kept for compatibility; Alpha bot is webhook-driven in this project.
    # Importing this module should not start the server.
    raise RuntimeError("Alpha_PBot is webhook-driven; call its webhook route via Flask in main.py.")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    flask_app.run(host="0.0.0.0", port=port)


