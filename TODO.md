# TODO

- [x] Read current `main.py`, `database.py`, and `Alpha_PBot.py` to understand existing startup + webhook flow.
- [x] Update `main.py` to run `init_db()` and `setup_database()` exactly once at app startup (Gunicorn worker boot) and remove `before_request` + per-request event loop creation.

- [x] Verify `/webhook_alpha` route still exists and feeds updates to `aiogram` dispatcher.

- [ ] Run a quick local sanity check: `python main.py` and curl POST to `/webhook_alpha` with a minimal JSON payload (or run unit tests).


