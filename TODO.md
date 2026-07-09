# TODO

## Done
- (none)

## To do
- [x] Update `main.py` to run a single startup coroutine (`startup_tasks`) that calls `init_db()` and `setup_database()` once at process start.
- [x] Remove the Flask `@app.before_first_request` initializer so startup does not run multiple times.
- [ ] Run unit tests / import check.


