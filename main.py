import os
import asyncio
import hashlib
import hmac
import json
import logging

from flask import Flask, request

# Alpha Bot
from Alpha_PBot import bot as alpha_bot, dp as alpha_dp, on_startup as alpha_on_startup

# Admin Bot
from Admin_Bot import admin_bot, dp as admin_dp, on_startup as admin_on_startup

from database import init_db

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ──────────────────────────────────────────
# One-time async startup (Gunicorn worker boot)
# ──────────────────────────────────────────
_init_done = False


def ensure_startup():
    global _init_done
    if _init_done:
        return
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(init_db())
        loop.run_until_complete(alpha_on_startup())
        loop.run_until_complete(admin_on_startup())
        loop.close()
    except Exception as e:
        logging.exception("Startup initialization failed (continuing anyway): %s", e)
    finally:
        _init_done = True


# ──────────────────────────────────────────
# Helper: feed an update to a dispatcher
# ──────────────────────────────────────────
def _feed_update(dp_instance, bot_instance, update_dict):
    """Run one Telegram update through aiogram dispatcher using a temporary loop."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(dp_instance.feed_update(bot_instance, update_dict))
        return "ok", 200
    except Exception as e:
        logging.exception("Webhook error: %s", e)
        return "error", 500
    finally:
        try:
            loop.close()
        except Exception:
            pass


# ──────────────────────────────────────────
# Health check
# ──────────────────────────────────────────
@app.route("/", methods=["GET"])
def health():
    return "ok", 200


# ──────────────────────────────────────────
# Alpha Bot webhook
# ──────────────────────────────────────────
@app.route("/webhook_alpha", methods=["POST"])
def alpha_webhook():
    ensure_startup()
    update = request.get_json(force=True)
    return _feed_update(alpha_dp, alpha_bot, update)


# ──────────────────────────────────────────
# Admin Bot webhook
# ──────────────────────────────────────────
@app.route("/webhook_admin", methods=["POST"])
def admin_webhook():
    ensure_startup()
    update = request.get_json(force=True)
    return _feed_update(admin_dp, admin_bot, update)


# ──────────────────────────────────────────
# Paystack webhook
# ──────────────────────────────────────────
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")


@app.route("/webhook/paystack", methods=["POST"])
def paystack_webhook():
    # Verify signature
    payload = request.get_data()
    signature = request.headers.get("x-paystack-signature", "")
    expected = hmac.new(PAYSTACK_SECRET_KEY.encode(), payload, hashlib.sha512).hexdigest()
    if signature != expected:
        logging.warning("Invalid Paystack signature")
        return "invalid signature", 400

    event = json.loads(payload)
    if event.get("event") == "charge.success":
        customer_email = event["data"]["customer"]["email"]

        # Update DB in a temporary event loop
        async def _handle():
            from database import db_execute
            await db_execute("UPDATE students SET download_count = 0 WHERE email = $1", (customer_email,))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_handle())
        except Exception as e:
            logging.exception("Paystack webhook error: %s", e)
        finally:
            loop.close()

    return {"status": "success"}, 200


# ──────────────────────────────────────────
# Moniepoint webhook
# ──────────────────────────────────────────
@app.route("/webhook/moniepoint", methods=["POST"])
def moniepoint_webhook():
    data = request.get_json(force=True)
    event = data.get("event")

    if event == "charge.success":
        reg_number = data.get("data", {}).get("customerReference")

        async def _handle():
            from database import db_execute
            await db_execute("UPDATE students SET has_paid = TRUE WHERE reg_number = $1", (reg_number,))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_handle())
        except Exception as e:
            logging.exception("Moniepoint webhook error: %s", e)
        finally:
            loop.close()

    return {"status": "success"}, 200

