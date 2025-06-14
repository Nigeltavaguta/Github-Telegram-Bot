from flask import Flask, request
import requests
import os

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


app = Flask(__name__)

# Replace with your Telegram Bot token and Chat ID
TELEGRAM_BOT_TOKEN = '8054638204:AAEtP-ilMQWRL1ECzI-2SUHxqHX9QZRV2qk'
TELEGRAM_CHAT_ID = '6786416278'

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    requests.post(url, data=data)

@app.route('/github', methods=['POST'])
def github_webhook():
    data = request.json

    # Only proceed on push events
    if 'commits' in data:
        repo_name = data['repository']['name']
        pusher = data['pusher']['name']
        branch = data['ref'].split('/')[-1]

        for commit in data['commits']:
            msg = (
                f"📦 *New Commit to {repo_name}*\n"
                f"👤 Author: {commit['author']['name']}\n"
                f"📤 Pushed by: {pusher}\n"
                f"🌿 Branch: {branch}\n"
                f"🕒 Time: {commit['timestamp']}\n"
                f"📝 Message: {commit['message']}\n"
                f"🔗 [View Commit]({commit['url']})"
            )
            send_telegram_message(msg)

    return '', 200

@app.route('/')
def index():
    return "Webhook Listener is running!"

if __name__ == '__main__':
    app.run(debug=True)
