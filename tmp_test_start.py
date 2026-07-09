import asyncio
import traceback
from aiogram.types import Update, Message, User, Chat
from Alpha_PBot import dp, bot
from database import init_db

async def main():
    await init_db()
    user = User(id=123456789, is_bot=False, first_name='Test')
    chat = Chat(id=123456789, type='private')
    message = Message(message_id=1, date=0, chat=chat, from_user=user, text='/start')
    update = Update(update_id=1, message=message)
    try:
        await dp.feed_update(bot, update)
        print('feed_update ok')
    except Exception:
        traceback.print_exc()

asyncio.run(main())
