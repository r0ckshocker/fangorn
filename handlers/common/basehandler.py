import os
import json
import logging
import boto3
from datetime import datetime
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.content_encoding import ContentEncoding
from datadog_api_client.v2.model.http_log_item import HTTPLogItem
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from cryptography.fernet import Fernet

class BaseHandler:
    def __init__(self):
        self.dd_source = os.getenv("DD_SOURCE", "oracle")
        self.dd_tags = os.getenv("DD_TAGS", "")
        self.dd_service = os.getenv("DD_SERVICE", "oracle_service")
        self.dd_api_key = os.getenv("DD_API_KEY")
        self.dd_app_key = os.getenv("DD_APP_KEY")
        self.s3_bucket = os.getenv("S3_BUCKET")
        self.slack_token = os.getenv("SLACK_TOKEN")
        self.slack_channel_id = os.getenv("SLACK_CHANNEL_ID")
        self.s3_client = boto3.client('s3')
        self.slack_client = WebClient(token=self.slack_token)
        
        # Configure logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def log_to_datadog(self, level, message, **kwargs):
        """
        Logs a message to Datadog.
        
        :param level: Log level (e.g., 'info', 'error')
        :param message: Log message
        :param kwargs: Additional key-value pairs to include in the log message
        """
        log_message = self.create_log_message(level=level, message=message, **kwargs)
        body = [
            HTTPLogItem(
                ddsource=self.dd_source,
                ddtags=self.dd_tags,
                message=log_message,
                service=self.dd_service,
            ),
        ]
        configuration = Configuration()
        with ApiClient(configuration) as api_client:
            api_instance = LogsApi(api_client)
            try:
                response = api_instance.submit_log(content_encoding=ContentEncoding.DEFLATE, body=body)
                self.logger.info("Successfully posted event to Datadog.")
                return response
            except Exception as e:
                self.logger.error(f"Failed to post event to Datadog: {e}")
                raise

    def create_log_message(self, **kwargs):
        """
        Creates a log message in JSON format with the provided key-value pairs.
        
        :param kwargs: Key-value pairs to include in the log message
        :return: JSON-formatted log message
        """
        current_time = datetime.utcnow().isoformat()
        message = {
            "timestamp": kwargs.get("timestamp", current_time),
            "level": kwargs.get("level", "info"),
            "application": kwargs.get("application", "Security"),
            "environment": kwargs.get("environment", "Security"),
        }

        for key, value in kwargs.items():
            message[key] = value

        return json.dumps(message, default=str)

    def send_message_to_slack(self, message):
        """
        Sends a message to the configured Slack channel.
        
        :param message: Message to send
        """
        try:
            self.slack_client.chat_postMessage(
                channel=self.slack_channel_id,
                text="News",
                blocks=message["blocks"]
            )
            self.logger.info("Message sent successfully to Slack.")
        except SlackApiError as e:
            self.logger.error(f"Error sending message to Slack: {e.response['error']}")

    def upload_to_s3(self, data, path):
        """
        Uploads data to S3, encrypting it before uploading.
        
        :param data: Data to upload
        :param path: S3 path
        """
        key = Fernet.generate_key()  # This should be stored securely and not hard-coded
        cipher_suite = Fernet(key)
        cipher_text = cipher_suite.encrypt(json.dumps(data).encode())
        try:
            self.s3_client.put_object(Bucket=self.s3_bucket, Key=path, Body=cipher_text)
            self.logger.info(f"Data successfully uploaded to S3 at {path}.")
        except Exception as e:
            self.logger.error(f"Failed to upload data to S3: {e}")

    def process(self):
        """
        This method should be overridden by subclasses to implement specific processing logic.
        """
        raise NotImplementedError("Subclasses should implement this method")
