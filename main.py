from flask import Flask, request
import os
# If your bot code is in separate files, import them here:
import Alpha_PBot
import Admin_Bot
import payment_server
import webhook_server

# NOTE: main.py is the orchestrator. Importing these modules must not auto-start polling/web servers.

app = Flask(__name__)


# Route for Alpha Bot
@app.route('/webhook_alpha', methods=['POST'])
def alpha_webhook():
    # Call your Alpha bot logic here
    # Alpha_PBot.process(request.json)
    return "ok", 200

# Route for Admin Bot
@app.route('/webhook_admin', methods=['POST'])
def admin_webhook():
    # Call your Admin bot logic here
    # Admin_Bot.process(request.json)
    return "ok", 200

if __name__ == "__main__":
    # Render uses the PORT environment variable
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)