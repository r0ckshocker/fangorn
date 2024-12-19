import requests
import json
import logging
from app.server.services.helper.helper import get_or_throw

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self):
        self.api_key = get_or_throw('OPENAI_API_KEY')

    def call_openai_api(self, prompt):
        try:
            data = {
                'model': 'gpt-4',
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 1500
            }
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            logger.info(f'Calling OpenAI API with data: {json.dumps(data, indent=2)}')
            response = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, json=data)
            response.raise_for_status()
            logger.info(f'Response status code: {response.status_code}')
            logger.info(f'Response content: {response.content}')
            
            response_json = response.json()
            content = response_json['choices'][0]['message']['content']
            
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logger.error(f'Failed to decode JSON response: {content}')
                return {"error": "Failed to decode JSON response", "content": content}
        except requests.RequestException as error:
            logger.error(f'OpenAI API request failed: {error}')
            raise
