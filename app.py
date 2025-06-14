from flask import Flask, request, abort, jsonify
import requests
import os
import hmac
import hashlib
import logging
from datetime import datetime

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET')

def verify_signature(payload, signature):
    if not WEBHOOK_SECRET:
        return True  # Allow if no secret configured
    
    secret = WEBHOOK_SECRET.encode()
    expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f'sha256={expected}', signature)

def send_telegram(message):
    if not all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        logger.error("Missing Telegram config")
        return False

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            },
            timeout=10
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

def format_message(repo, commits, branch, pusher):
    return (
        f"📌 *{repo['name']}* | {len(commits)} new commit(s)\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔹 *Branch*: `{branch}`\n"
        f"👤 *By*: {pusher}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💬 *Message*:\n`{commits[0]['message']}`\n"
        f"🔗 [View Changes]({repo['url']}/compare/{commits[-1]['id']...{commits[0]['id']})"
    )

@app.route('/')
def health():
    return jsonify({
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    })

@app.route('/github', methods=['POST'])
def webhook():
    # Verify signature
    sig = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(request.data, sig):
        abort(403, "Invalid signature")

    data = request.get_json()
    event = request.headers.get('X-GitHub-Event')

    if event == 'ping':
        return jsonify({"status": "pong"})

    if event == 'push':
        repo = data.get('repository', {})
        commits = data.get('commits', [])
        if not commits:
            return jsonify({"status": "ignored", "reason": "No commits"})

        message = format_message(
            repo,
            commits,
            data.get('ref', '').split('/')[-1],
            data.get('pusher', {}).get('name', 'Unknown')
        )

        if send_telegram(message):
            return jsonify({"status": "sent"})
        return jsonify({"status": "failed"})

    return jsonify({"status": "ignored", "reason": "Unhandled event"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))