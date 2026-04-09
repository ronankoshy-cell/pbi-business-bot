import os
import sys
import requests
import re
import time
from slack_sdk import WebClient

# 1. Setup - Pulling environment variables
token = os.environ.get('SLACK_TOKEN')
source_id = os.environ.get('SLACK_CHANNEL_ID') # Where the snapshots arrive
target_id = os.environ.get('GROWTH_CHANNEL_ID') # Where to send them

client = WebClient(token=token)

def run_relay():
    try:
        print("--- Business Dashboards Regex Scraper Relay ---")

        # 2. Get today's messages (24h window)
        cutoff = time.time() - (24 * 60 * 60)
        res = client.conversations_history(channel=source_id, limit=40)
        messages = res.get("messages", [])

        # 3. Targets for the Business Dashboard Views
        # Keywords are exact lowercase matches of the Power BI report names
        reports = {
            "B2C_and_B2B": {"kw": "business dashboard - ( b2c + b2b )", "text": "📊 Hi Team, sharing the Business Dashboard - ( B2C + B2B ) Snapshot.", "url": None},
            "B2C_Only": {"kw": "business dashboard - b2c", "text": "📊 Hi Team, sharing the Business Dashboard - B2C Snapshot.", "url": None},
            "B2B_Only": {"kw": "business dashboard - b2b", "text": "📊 Hi Team, sharing the Business Dashboard - B2B Snapshot.", "url": None},
            "Overall_STYLI": {"kw": "business dashboard - overall styli", "text": "📊 Hi Team, sharing the Business Dashboard - Overall STYLI Snapshot.", "url": None}
        }

        # 4. Scrape the raw message string for hosted image links
        for msg in messages:
            if float(msg.get("ts", 0)) < cutoff: continue

            text_content = str(msg).lower()
            found_urls = re.findall(r'https://[^\s"\'<>]*files-origin\.slack\.com/[^\s"\'<>]+', str(msg))

            for raw_url in found_urls:
                url = raw_url.replace('\\', '')
                for key, data in reports.items():
                    # Check if the specific keyword is in this message
                    if data["kw"] in text_content and not data["url"]:
                        data["url"] = url
                        print(f":white_check_mark: Regex Matched Image Link for: {key}")

        # 5. Download and Re-Upload to the target channel
        headers = {'Authorization': f'Bearer {token}'}
        for key, data in reports.items():
            if data["url"]:
                print(f"Relaying {key}...")
                img_data = requests.get(data["url"], headers=headers).content

                temp_filename = f"today_{key.lower()}.png"
                with open(temp_filename, "wb") as f:
                    f.write(img_data)

                # Post clean binary to Growth channel
                client.files_upload_v2(
                    channel=target_id,
                    file=temp_filename,
                    title=f"Automated Report - {key.replace('_', ' ')}",
                    initial_comment=data["text"]
                )
                print(f"SUCCESS: {key} relayed to target channel.")
                
                # The crucial 3-second delay to prevent Slack API crashes
                time.sleep(3) 
                
                os.remove(temp_filename)
            else:
                print(f"SKIP: No today's snapshot found for {key}.")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_relay()
