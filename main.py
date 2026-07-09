import os
import asyncio
import logging
from flask import Flask, request
from Alpha_PBot import bot, dp, on_startup
from database import init_db, setup_database

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Flag to ensure startup only runs once
startup_done = False

async def perform_startup():
    await init_db()
    await setup_database()
    await on_startup()

@app.before_request
def before_request_func():
    global startup_done
    if not startup_done:
        # Run the async tasks in the event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(perform_startup())
        startup_done = True

@app.route("/webhook_alpha", methods=["POST"])
def alpha_webhook():
    update = request.get_json(force=True)
    # Use run_coroutine_threadsafe to handle async inside sync Flask
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(dp.feed_update(bot, update))
        return "ok", 200
    except Exception as e:
        logging.error(f"Error: {e}")
        return "error", 500

@app.route("/", methods=["GET"])
def health():
    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)



