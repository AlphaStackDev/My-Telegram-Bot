from pathlib import Path

path = Path('c:/Users/User/My_Telegram_Bot/Alpha_PBot.py')
text = path.read_text(encoding='utf-8')

old = '''if not ok:
        await call.answer()
        await call.message.answer(
            "You have used your 2 free downloads.\n"
            "Send payment proof / complete payment as instructed by admin."
        )
        return'''

new = '''if not ok:
        await call.answer()
        await show_payment_options(call.message)
        return'''

if old not in text:
    raise SystemExit('Old block not found; aborting to avoid corrupt edits.')

path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('Patched download gatekeeper successfully.')

