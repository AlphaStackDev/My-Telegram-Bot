from pathlib import Path

path = Path('c:/Users/User/My_Telegram_Bot/Alpha_PBot.py')
text = path.read_text(encoding='utf-8')

# 1) Ensure start_cmd clears state (add a line right after function def if missing)
marker = '@dp.message(Command("start"))'
start_idx = text.find(marker)
if start_idx == -1:
    raise SystemExit('start_cmd marker not found')

# Find function header line
func_idx = text.find('async def start_cmd', start_idx)
if func_idx == -1:
    raise SystemExit('start_cmd function not found')

# Check within next 400 chars for await state.clear()
window = text[func_idx:func_idx+500]
if 'await state.clear()' not in window:
    # insert after first line inside function (after signature line)
    sig_end = text.find(':', func_idx)
    # insert after newline following signature indent
    insert_at = text.find('\n', sig_end)
    if insert_at == -1:
        raise SystemExit('cannot find insertion point for state.clear')
    insert_at += 1
    indent = '    '
    text = text[:insert_at] + f'{indent}await state.clear()  # This clears any stuck registration steps\n' + text[insert_at:]

# 2) Add logout handler if missing
logout_marker = '@dp.message(Command("logout"))'
if logout_marker not in text:
    # append near start_cmd or end; place after start_cmd block if possible
    # simplest: add near after start_cmd definition block - right after its first 'return'/'send_faculty_menu' path.
    # We'll insert after the start_cmd function ends by locating the next '@dp.message' decorator after start_cmd marker.
    next_dec = text.find('\n\n@dp.message', start_idx + 1)
    if next_dec == -1:
        next_dec = len(text)
    logout_code = """

@dp.message(Command("logout"))
async def logout_cmd(message: types.Message, state: FSMContext):
    # This deletes the user's data from your database, forcing a fresh start
    await db_execute("DELETE FROM students WHERE telegram_id = $1", (message.from_user.id,))
    await state.clear()
    await message.answer("You have been logged out. Send /start to register a new student.")
"""
    text = text[:next_dec] + logout_code + text[next_dec:]

path.write_text(text, encoding='utf-8')
print('Patched Alpha_PBot.py for start_cmd state.clear and logout_cmd')

