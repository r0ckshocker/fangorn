import os
import logging
from dotenv import load_dotenv
import anthropic
import openai

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

def ask_alfred(message, system_prompt=None, api='openai'):
    """Ask Alfred a question and get a response."""
    if api == 'anthropic':
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": message
                    }
                ]
            }
        ]

        system_messages = []
        if system_prompt:
            system_messages = [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": system_prompt
                        }
                    ]
                }
            ]

        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=4000,
                temperature=0,
                system=system_prompt,
                messages=messages
            )
            # Extract the text content from the TextBlock objects
            return "".join(block.text for block in response.content)
        except Exception as e:
            logger.error(f"Failed to connect to Anthropics: {str(e)}")
            return 'No response or error occurred.'
    elif api == 'openai':
        openai.api_key = OPENAI_API_KEY
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt} if system_prompt else {},
                    {"role": "user", "content": message}
                ]
            )
            return response.choices[0].message['content']
        except Exception as e:
            logger.error(f"Failed to connect to OpenAI: {str(e)}")
            return 'No response or error occurred.'
    else:
        logger.error(f"Unsupported API: {api}")
        return 'Unsupported API specified.'

if __name__ == "__main__":
    message = "What is the weather like today?"
    system_prompt = "You are a helpful assistant."
    response = ask_alfred(message, system_prompt)
    print("Alfred's Response:", response)