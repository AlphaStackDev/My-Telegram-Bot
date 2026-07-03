# TODO

- [ ] (Confirmed) Keep `/webhook` in FastAPI (`webhook_server.py`).
- [ ] Add Telegram webhook processing to FastAPI route `/webhook` (pass update into aiogram dispatcher).
- [ ] Ensure Alpha bot webhook is handled by aiogram without starting polling.
- [ ] Remove/avoid conflicting Flask webhook routes if needed.
- [ ] Run `python -m py_compile webhook_server.py Alpha_PBot.py main.py Admin_Bot.py database.py`.
- [ ] Test locally: POST a sample Telegram update to `/webhook` and verify `200 OK`.


