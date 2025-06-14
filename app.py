from flask import Flask, request, abort, jsonify
import requests
import os
import hmac
import hashlib
import logging

# Initialize Flask app
app = Flask(__name__)

# Basic logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET')

def verify_signature(data, signature):
    """Verify GitHub webhook signature"""
    if not WEBHOOK_SECRET:
        return True  # Skip if no secret set
    
    secret = WEBHOOK_SECRET.encode()
    expected = hmac.new(secret, data, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f'sha256={expected}', signature)

def send_to_telegram(text):
    """Send message to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

@app.route('/github', methods=['POST'])
def handle_webhook():
    """Process GitHub webhooks"""
    # Verify signature
    sig = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(request.data, sig):
        abort(403, "Invalid signature")

    # Get push data
    data = request.get_json()
    if not data or 'commits' not in data:
        return jsonify({"status": "ignored"}), 200

    repo = data['repository']['name']
    branch = data['ref'].split('/')[-1]
    commit = data['commits'][0]  # Only process the latest commit
    
    # Format message
    message = (
        f"📌 *{repo}* | New commit\n"
        f"Branch: `{branch}`\n"
        f"Author: {commit['author']['name']}\n"
        f"Message: {commit['message']}\n"
        f"View: {commit['url']}"
    )

    # Send notification
    if send_to_telegram(message):
        return jsonify({"status": "sent"}), 200
    return jsonify({"status": "failed"}), 200

@app.route('/')
def health_check():
    return "Webhook is running"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))