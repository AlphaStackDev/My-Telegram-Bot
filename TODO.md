# TODO

- [x] Replace `main.py` webhook server with the provided Flask version
  - [x] Ensure `/webhook_alpha` route uses `async def` and `await dp.feed_update(bot, update)`
  - [x] Ensure DB is initialized once at startup using `@app.before_first_request` + `asyncio.run(init_db())`
  - [x] Ensure `/` health route returns `Bot is running`
  - [x] Ensure `PORT` env var is respected in `__main__`
- [ ] Run tests
  - [x] `python -m unittest` (or pytest if configured)



