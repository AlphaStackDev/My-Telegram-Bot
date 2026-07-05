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
    if not getattr(setup, "initialized", False):
        with app.app_context():
            try:
                asyncio.run(init_db())
                setup.initialized = True
            except Exception as exc:
                logging.exception("Database initialization failed during startup: %s", exc)
                setup.initialized = False


# Route for Alpha Bot
@app.route("/webhook_alpha", methods=["POST"])
def alpha_webhook():
    # Forward Telegram update JSON to Alpha_PBot (aiogram webhook-driven).
    payload = request.get_json(force=True, silent=True) or {}

    # Convert raw JSON -> aiogram Update
    try:
        from Alpha_PBot import bot, dp
        from aiogram.types import Update

        if not getattr(bot, "token", None):
            logging.error("Alpha bot token is missing. Set ALPHA_BOT_TOKEN in Render.")
            return "ok", 200

        update = Update.model_validate(payload)
    except Exception as exc:
        logging.exception("Alpha webhook failed to parse/update payload: %s", exc)
        return "ok", 200

    try:
        async def _handle():
            await dp.feed_update(bot, update)

        asyncio.run(_handle())
    except Exception as exc:
        logging.exception("Alpha webhook dispatch failed: %s", exc)

    return "ok", 200


# Route for Admin Bot
@app.route("/webhook_admin", methods=["POST"])
def admin_webhook():
    payload = request.get_json(force=True, silent=True) or {}

    try:
        from Admin_Bot import bot, dp
        from aiogram.types import Update

        if not getattr(bot, "token", None):
            logging.error("Admin bot token is missing. Set ADMIN_BOT_TOKEN in Render.")
            return "ok", 200

        update = Update.model_validate(payload)
    except Exception as exc:
        logging.exception("Admin webhook failed to parse/update payload: %s", exc)
        return "ok", 200

    try:
        async def _handle():
            await dp.feed_update(bot, update)

        asyncio.run(_handle())
    except Exception as exc:
        logging.exception("Admin webhook dispatch failed: %s", exc)

    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
