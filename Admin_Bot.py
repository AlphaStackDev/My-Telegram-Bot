import asyncio
import asyncpg
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup

import logging
from database import db_execute, db_fetch_one
from dotenv import load_dotenv


# USE YOUR NEW ADMIN BOT TOKEN HERE

load_dotenv()
ADMIN_TOKEN = os.environ.get('ADMIN_BOT_TOKEN')
if not ADMIN_TOKEN:
    raise RuntimeError("Missing ADMIN_BOT_TOKEN")
admin_bot = Bot(token=ADMIN_TOKEN)

ADMIN_ID = 8271633745  # Your Telegram ID

dp = Dispatcher()


async def set_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Show Admin Panel"),
        BotCommand(command="approve", description="Approve a student: /approve <id> <type> (sem1/sem2/all)"),

        BotCommand(command="check", description="Check payment status: /check <id>"),
    ]
    await bot.set_my_commands(commands)

@dp.message(Command("start"))
async def start_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Access Denied.")
        return
    await message.answer("✅ Admin Panel Active.\n\nCommands:\n/approve <student_id>\n/check <student_id>")

@dp.message(Command("approve"))
async def approve_student(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    # Usage: /approve <student_id> <type>
    # type: sem1 | sem2 | all
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Usage: /approve <student_id> <type> (sem1/sem2/all)")
        return

    student_id = int(args[1])
    payment_type = args[2].lower().strip()
    if payment_type not in ("sem1", "sem2", "all"):
        await message.answer("Invalid type. Use: sem1 or sem2 or all")
        return

    if payment_type == "sem1":
        await db_execute(
            "UPDATE students SET has_paid_sem1 = TRUE WHERE telegram_id = $1",
            (student_id,),
        )
    elif payment_type == "sem2":
        await db_execute(
            "UPDATE students SET has_paid_sem2 = TRUE WHERE telegram_id = $1",
            (student_id,),
        )
    else:  # all
        await db_execute(
            "UPDATE students SET has_paid_sem1 = TRUE, has_paid_sem2 = TRUE, has_paid_all = TRUE WHERE telegram_id = $1",
            (student_id,),
        )

    await db_execute(
        "UPDATE students SET download_count = 0 WHERE telegram_id = $1",
        (student_id,),
    )

    await message.answer(f"✅ Approved {payment_type} for {student_id}.")
    try:
        await admin_bot.send_message(student_id, f"🎉 Payment approved! You unlocked: {payment_type}. You can now download files.")
    except Exception:
        pass


@dp.message(Command("check"))
async def check_student(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return
    student_id = int(args[1])

    student = await db_fetch_one(
        "SELECT has_paid_sem1, has_paid_sem2, has_paid_all FROM students WHERE telegram_id = $1",
        (student_id,),
    )

    if not student:
        await message.answer("Student not found in database.")
        return

    if student.get("has_paid_all"):
        status = "PAID (ALL)"
    else:
        sem1 = bool(student.get("has_paid_sem1"))
        sem2 = bool(student.get("has_paid_sem2"))
        status = f"PAID sem1={sem1}, sem2={sem2}"

    await message.answer(f"Status for {student_id}: {status}")


@dp.message(F.photo)
async def admin_review_receipt(message: types.Message):
    if not message.caption: return
    import re
    m = re.search(r"ID:\s*(\d+)", message.caption)
    student_id = int(m.group(1)) if m else None
    if not student_id: return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Approve Sem 1", callback_data=f"admin_approve:{student_id}:sem1"),
        InlineKeyboardButton(text="✅ Approve Sem 2", callback_data=f"admin_approve:{student_id}:sem2"),
        InlineKeyboardButton(text="✅ Approve Pay All", callback_data=f"admin_approve:{student_id}:all"),
        InlineKeyboardButton(text="❌ Decline", callback_data=f"admin_decline:{student_id}")

    ]])
    await message.answer(f"🧾 New Payment Receipt!\nStudent ID: {student_id}", reply_markup=kb)

@dp.callback_query(F.data.startswith("admin_approve:"))
async def approve_callback(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    parts = call.data.split(":")
    # admin_approve:<student_id>:<type>
    student_id = int(parts[1])
    payment_type = parts[2].lower().strip() if len(parts) > 2 else "all"

    if payment_type not in ("sem1", "sem2", "all"):
        payment_type = "all"

    if payment_type == "sem1":
        await db_execute("UPDATE students SET has_paid_sem1 = TRUE WHERE telegram_id = $1", (student_id,))
    elif payment_type == "sem2":
        await db_execute("UPDATE students SET has_paid_sem2 = TRUE WHERE telegram_id = $1", (student_id,))
    else:
        await db_execute("UPDATE students SET has_paid_sem1 = TRUE, has_paid_sem2 = TRUE, has_paid_all = TRUE WHERE telegram_id = $1", (student_id,))

    await db_execute("UPDATE students SET download_count = 0 WHERE telegram_id = $1", (student_id,))

    await call.message.edit_text(f"✅ Approved: {student_id}")
    await call.answer("Approved!")

@dp.callback_query(F.data.startswith("admin_decline:"))
async def decline_callback(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    student_id = int(call.data.split(":")[1])
    await call.message.edit_text(f"❌ Declined: {student_id}")
    await call.answer("Declined!")

async def on_startup():
    """Called by main.py to set Admin bot webhook."""
    base_url = os.environ.get("RENDER_URL", "https://your-render-app-name.onrender.com")
    webhook_url = f"{base_url.rstrip('/')}/webhook_admin"
    await admin_bot.set_webhook(webhook_url)
    logging.info(f"Admin bot webhook set to: {webhook_url}")


async def run_admin_bot() -> None:
    await set_commands(admin_bot)
    raise RuntimeError("Admin_Bot is webhook-driven; call its webhook route via Flask in main.py.")



if __name__ == "__main__":
    asyncio.run(run_admin_bot())

