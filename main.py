import os
import asyncio
import logging
from flask import Flask, request
from Alpha_PBot import bot, dp, on_startup
from database import init_db, setup_database

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


# Run this once at startup
async def startup_tasks():
    await init_db()
    await setup_database()
    await on_startup()



@app.route("/webhook_alpha", methods=["POST"])
async def alpha_webhook():
    update = request.get_json(force=True)
    try:
        # Feed the update directly to the dispatcher
        await dp.feed_update(bot, update)
        return "ok", 200
    except Exception as e:
        logging.error(f"Error: {e}")
        return "error", 500


@app.route("/", methods=["GET"])
def health():
    return "ok", 200



if __name__ == "__main__":
    # Initialize database + tables + Telegram webhook before running Flask
    asyncio.run(startup_tasks())

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


