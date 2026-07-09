import os
import asyncio
import logging
from flask import Flask, request
from Alpha_PBot import bot, dp
from database import init_db

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


# Initialize DB when the app starts
@app.before_first_request
def initialize():
    asyncio.run(init_db())


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
    return "Bot is running", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

