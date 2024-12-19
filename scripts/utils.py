import logging
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from datadog import initialize
import certifi
import random
import string
import click

def setup_logger():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

logger = setup_logger()

def handle_error(error_message):
    logger.error(error_message)
    raise click.ClickException(error_message)

session = None
client_context = None

# Environment setup
def setup_environment():
    load_dotenv()
    options = {
        'api_key': os.getenv('DD_API_KEY'),
        'app_key': os.getenv('DD_APP_KEY')
    }
    initialize(**options)

# HTTP session setup with retry logic
def create_http_session():
    global session
    if session is None:  # Ensure the session is initialized only once
        session = requests.Session()
        retry = Retry(
            total=5,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.verify = certifi.where()
    return session

# Function to generate headers
def get_headers(url):
    return {
        'Content-Type': 'application/json',
        'X-Dd-Web-Session-Id': session if isinstance(session, str) else '',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.160 Safari/537.36',
        'X-Client-Context': client_context if isinstance(client_context, str) else '',
        'Accept': 'application/json, text/plain, */*',
        'X-Session-Id': session if isinstance(session, str) else '',
        'Sec-Ch-Ua-Platform': 'macOS',
        'Origin': f'https://{url}.apprentice.io',
        'Sec-Fetch-Site': 'same-site',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Referer': f'https://{url}.apprentice.io/'
    }

# Function to retrieve a bearer token
def get_bearer_token(url, email, password):
    global session, client_context
    if session is None:  # Ensure session is initialized before use
        session = create_http_session()
    
    logger.info(f"Attempting to get bearer token for {url} using email: {email}")
    headers = get_headers(url)
    payload = {"email": email, "password": password}
    response = session.post(f'https://{url}.api.apprentice.io/v1/login', json=payload, headers=headers)
    if response.status_code == 200:
        # Assuming the API returns session and client context upon login
        session_data = response.json()
        session = session_data.get('session_id', '')
        client_context = session_data.get('client_context', '')
        return session_data['token']
    else:
        logger.error(f"Failed to get bearer token. Status code: {response.status_code}, Response: {response.text}")
        return None

# Add more utility functions from other files as needed

def generate_random_password(length=12):	
    characters = string.ascii_letters + string.digits + string.punctuation	
    return ''.join(random.choice(characters) for i in range(length))