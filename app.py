from flask import Flask, request, abort, jsonify
import requests
import os
import hmac
import hashlib
import logging
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
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
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("Telegram message sent successfully")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Telegram API error: {str(e)}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Telegram API response: {e.response.text}")
        return False

@app.route('/')
def health_check():
    """Root endpoint with service information"""
    return jsonify({
        "status": "running",
        "service": "github-webhook",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "webhook": "/github (POST)",
            "health": "/health (GET)"
        }
    })

@app.route('/health')
def deep_health_check():
    """Detailed health check"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "telegram": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
            "github_webhook": bool(GITHUB_WEBHOOK_SECRET),
            "system_time": datetime.utcnow().isoformat()
        }
    })

@app.route('/github', methods=['POST'])
def github_webhook():
    """Handle GitHub webhook events"""
    # Log incoming request
    logger.info(f"Incoming webhook request from IP: {request.remote_addr}")
    logger.debug(f"Request headers: {dict(request.headers)}")

    # Verify signature
    signature = request.headers.get('X-Hub-Signature-256')
    if not signature:
        logger.error("Missing X-Hub-Signature-256 header")
        abort(400, "Missing signature header")

    if not verify_github_signature(request.data, signature):
        logger.error("Invalid webhook signature")
        abort(403, "Invalid signature")

    # Process payload
    try:
        data = request.get_json()
        if not data:
            logger.warning("Empty payload received")
            return jsonify({"status": "ignored", "reason": "Empty payload"}), 200

        event_type = request.headers.get('X-GitHub-Event', 'unknown')
        logger.info(f"Processing {event_type} event")

        # Handle ping event
        if event_type == 'ping':
            logger.info("Received ping event")
            return jsonify({"status": "pong", "zen": data.get('zen', '')}), 200

        # Handle push event
        if event_type == 'push':
            repo = data.get('repository', {})
            commits = data.get('commits', [])
            branch = data.get('ref', '').split('/')[-1]
            pusher = data.get('pusher', {}).get('name', 'Unknown')

            if not commits:
                logger.info("Push event with no commits")
                return jsonify({"status": "ignored", "reason": "No commits"}), 200

            results = []
            for commit in commits:
                try:
                    message = (
                        f"📌 *New Commit to {repo.get('name', 'Unnamed Repository')}*\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"👤 *Author*: {commit.get('author', {}).get('name', 'Unknown')}\n"
                        f"🔹 *Branch*: `{branch}`\n"
                        f"💬 *Message*: _{commit.get('message', 'No message')}_\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"🔗 [View Commit ↗]({commit.get('url', '#')})"
                    )
                    logger.debug(f"Formatted message: {message}")

                    if send_telegram_message(message):
                        results.append({"commit_id": commit.get('id'), "status": "sent"})
                    else:
                        results.append({"commit_id": commit.get('id'), "status": "failed"})
                except Exception as commit_error:
                    logger.error(f"Error processing commit: {str(commit_error)}")
                    results.append({"commit_id": commit.get('id'), "status": "error"})

            return jsonify({
                "status": "processed",
                "repo": repo.get('name'),
                "branch": branch,
                "results": results
            }), 200

        logger.warning(f"Unhandled event type: {event_type}")
        return jsonify({"status": "ignored", "reason": f"Unhandled event type: {event_type}"}), 200

    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}", exc_info=True)
        abort(500, "Internal server error")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))