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


@app.before_first_request
def ensure_db_initialized():
    """Initialize async DB pool once, before the first HTTP request."""
    try:
        asyncio.run(init_db())
        logging.info("Database connection pool created successfully.")
    except Exception as e:
        logging.exception("Failed to initialize database")
        # Let Flask surface the error to the caller.
        raise


# Route for Alpha Bot
@app.route("/webhook_alpha", methods=["POST"])
def alpha_webhook():
    # TODO: Call Alpha_PBot webhook handler here
    # For now, just acknowledge.
    _ = request.get_json(silent=True)
    return "ok", 200


# Route for Admin Bot
@app.route("/webhook_admin", methods=["POST"])
def admin_webhook():
    # TODO: Call Admin_Bot webhook handler here
    _ = request.get_json(silent=True)
    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

