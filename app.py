from flask import Flask, request, abort
import requests
import os
import hmac
import hashlib
import logging

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
GITHUB_WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET')

def verify_github_signature(payload_body, signature_header):
    """Verify GitHub webhook signature using HMAC-SHA256"""
    if not GITHUB_WEBHOOK_SECRET:
        logger.error("Webhook secret not configured")
        return False
        
    secret = GITHUB_WEBHOOK_SECRET.encode()
    expected_signature = hmac.new(secret, payload_body, hashlib.sha256).hexdigest()
    expected_header = f'sha256={expected_signature}'
    return hmac.compare_digest(expected_header, signature_header)

def send_telegram_message(text):
    """Send message to Telegram with error handling"""
    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        logger.error("Telegram credentials not configured")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Telegram API error: {str(e)}")
        return False

@app.route('/github', methods=['POST'])
def github_webhook():
    """Handle GitHub webhook events"""
    # Verify signature
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_github_signature(request.data, signature):
        logger.warning("Invalid webhook signature")
        abort(403, "Invalid signature")

    # Process push events
    try:
        data = request.get_json()
        if not data or 'commits' not in data:
            return '', 204

        repo = data['repository']
        commits = data['commits']
        branch = data['ref'].split('/')[-1]
        pusher = data['pusher']['name']

        for commit in commits:
            message = (
                f"📦 *New Commit to {repo['name']}*\n"
                f"👤 Author: {commit['author']['name']}\n"
                f"📤 Pushed by: {pusher}\n"
                f"🌿 Branch: {branch}\n"
                f"🕒 Time: {commit['timestamp']}\n"
                f"📝 Message: {commit['message']}\n"
                f"🔗 [View Commit]({commit['url']})"
            )
            if not send_telegram_message(message):
                logger.error("Failed to send Telegram notification")

        return '', 200

    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        abort(500, "Internal server error")

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return {'status': 'healthy', 'service': 'github-webhook'}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))