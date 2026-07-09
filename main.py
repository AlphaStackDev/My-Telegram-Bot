import os
import asyncio
import logging
from flask import Flask, request
from Alpha_PBot import bot, dp, on_startup
from database import init_db, setup_database

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- One-time async startup (Gunicorn worker boot) ---
# Important: keep module import fast. Initialize only once per process.
_init_done = False

def ensure_startup():
    global _init_done
    if _init_done:
        return
    try:
        asyncio.run(init_db())
        asyncio.run(on_startup())
    except Exception as e:
        logging.exception("Startup initialization failed (continuing anyway): %s", e)
    finally:
        _init_done = True



@app.route("/webhook_alpha", methods=["POST"])

def alpha_webhook():
    ensure_startup()
    update = request.get_json(force=True)
    try:

        # Create a temporary event loop for this request.
        # (Using a fresh loop here keeps Flask sync-handler simple.)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(dp.feed_update(bot, update))
        return "ok", 200
    except Exception as e:
        logging.exception("Webhook error")
        return "error", 500


@app.route("/", methods=["GET"])
def health():
    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)





