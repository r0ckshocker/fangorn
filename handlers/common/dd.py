from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.content_encoding import ContentEncoding
from datadog_api_client.v2.model.http_log_item import HTTPLogItem
import json
from datetime import datetime


def create_log_message(**kwargs):
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

def post_dd_event(ddsource, tags, service, **kwargs):
    message = create_log_message(**kwargs)
    body = [
            HTTPLogItem(
                ddsource=ddsource,
                ddtags=tags,
                message=message,
                service=service,
        ),]
    configuration = Configuration()
    with ApiClient(configuration) as api_client:
        api_instance = LogsApi(api_client)
        response = api_instance.submit_log(content_encoding=ContentEncoding.DEFLATE, body=body)
        return response
