"""Send a test message to each configured Discord webhook; no news is fabricated."""
import os
import requests

CHANNELS = {
    "critical": "DISCORD_CRITICAL_WEBHOOK_URL",
    "crypto": "DISCORD_CRYPTO_WEBHOOK_URL",
    "stocks": "DISCORD_STOCK_WEBHOOK_URL",
    "status": "DISCORD_STATUS_WEBHOOK_URL",
}

for channel, key in CHANNELS.items():
    url = os.environ.get(key, "").strip()
    if not url:
        print(f"{channel}: skipped (variable {key} not set)")
        continue
    if not url.startswith("https://discord.com/api/webhooks/"):
        print(f"{channel}: invalid webhook URL")
        continue
    try:
        response = requests.post(url, json={"content": f"Market News Intelligence connection test: #{channel}. This is a test, not a financial news alert.", "allowed_mentions": {"parse": []}}, timeout=20)
        response.raise_for_status()
        print(f"{channel}: test delivered (HTTP {response.status_code})")
    except requests.RequestException as exc:
        print(f"{channel}: delivery failed ({type(exc).__name__}; HTTP {getattr(exc.response, 'status_code', 'unknown')})")
