import os
import asyncio
import logging

from flask import Flask, request

from database import init_db, close_db

# NOTE: main.py is the orchestrator. Importing these modules must not auto-start polling/web servers.
# If you later implement proper aiogram webhook handlers, keep those implementations in their modules.
# import Alpha_PBot
# import Admin_Bot

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)


@app.before_request
def setup():
    if not hasattr(setup, "initialized"):
        with app.app_context():
            asyncio.run(init_db())
        setup.initialized = True


# Route for Alpha Bot
@app.route("/webhook_alpha", methods=["POST"])
def alpha_webhook():
    # Forward Telegram update JSON to Alpha_PBot (aiogram webhook-driven).
    payload = request.get_json(force=True, silent=True) or {}

    # Convert raw JSON -> aiogram Update
    try:
        from Alpha_PBot import bot, dp
        from aiogram.types import Update

        update = Update.model_validate(payload)
    except Exception:
        # If Telegram sends unexpected payload, respond ok to avoid retries.
        return "ok", 200

    async def _handle():
        await dp.feed_update(bot, update)

    asyncio.run(_handle())
    return "ok", 200



# Route for Admin Bot
@app.route("/webhook_admin", methods=["POST"])
def admin_webhook():
    payload = request.get_json(force=True, silent=True) or {}

    try:
        from Admin_Bot import bot, dp
        from aiogram.types import Update

        update = Update.model_validate(payload)
    except Exception:
        return "ok", 200

    async def _handle():
        await dp.feed_update(bot, update)

    asyncio.run(_handle())
    return "ok", 200



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
