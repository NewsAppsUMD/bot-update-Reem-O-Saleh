import os
import json
from datetime import datetime
import requests
from slack import WebClient
from slack.errors import SlackApiError

# Load Slack API Token from environment variable
slack_token = os.environ.get("SLACK_API_TOKEN")

# FDA API Endpoint
url = "https://api.fda.gov/food/enforcement.json?limit=100&sort=report_date:desc"

# Make request to FDA API
response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
response.raise_for_status()

# Parse response
data = response.json()
first_result = data["results"][0]  # Get the latest recall

# Extract recall details
display_url = "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts"
display_date = datetime.strptime(first_result["report_date"], "%Y%m%d")
formatted_date = display_date.strftime("%B %-d, %Y")

# Create formatted message
sentence = (
    f"🚨 *FDA Recall Alert* 🚨\n"
    f"⚠️ *Product:* {first_result['product_description']}\n"
    f"❗ *Reason:* {first_result['reason_for_recall']}\n"
    f"🏭 *Company:* {first_result['recalling_firm']}\n"
    f"🌎 *Distribution:* {first_result['distribution_pattern']}\n"
    f"📅 *Recall Date:* {formatted_date}\n"
    f"🔗 [More Info]({display_url})"
)

print(sentence)

# Send message to Slack
client = WebClient(token=slack_token)
msg = sentence

try:
    response = client.chat_postMessage(
        channel="slack-bots",
        text=msg,
        unfurl_links=True,
        unfurl_media=True
    )
    print("✅ Success! Alert sent to Slack.")
except SlackApiError as e:
    print(f"❌ Slack API error: {e.response['error']}")