import os
import logging
import ssl
import certifi
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logging.basicConfig(level=logging.DEBUG)

ssl_context = ssl.create_default_context(cafile=certifi.where())
client = WebClient(token=os.environ['NEWS_BOT_TOKEN'], ssl=ssl_context)
channel_id = os.environ['SLACK_CHANNEL_ID']

def lookup_by_email(email):
    slack_token = os.environ["SLACK_BOT_TOKEN"]
    slack_scope = os.environ["SLACK_SEARCH_TOKEN"]
    client = WebClient()
    try:
        response = client.users_lookupByEmail(token=slack_token, email=email)
        assert response
    except SlackApiError as e:
        assert e.response["error"]

## send_message(simple_message("text", "header")) ##
# sends message to info-sec channel
def send_message(message):
    client.chat_postMessage(
        channel = channel_id,
        text = "News",
        blocks = message["blocks"]
    )

# Message with only text formatting/no actions
def simple_message(text,oracle_header):
    """Send message to slack channel"""
    message = {
        "blocks": [
            {
			"type": "header",
			"text": {
				"type": "plain_text",
				"text": (oracle_header)
			    }
		    },
            {
			"type": "divider"
		    },
            {
            "type": "section",
            "text": {
                "type": "mrkdwn", 
                "text": (text)
                  }
            },
            {
			"type": "divider"
		    }
        ]
    }
    return message

# text[0] will be the first section of text
# text[1] will be the button elements (see dd_signals.py for reference)
def messsage_with_buttons(text,oracle_header):
    """Send message to slack channel"""
    message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": (oracle_header)
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (text[0])
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "actions",
                "elements": (text[1])
            },
            {
                "type": "divider"
            }
        ]
    }
    return message