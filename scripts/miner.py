import os
import csv
import logging
import json
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from dotenv import load_dotenv
import random
import re
import time
import threading
from ratelimit import limits, sleep_and_retry
from hrai_python.hrai_logger import hrai_logger
from openai import OpenAI
import click
import backoff


# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
GOOGLE_API_KEY = os.getenv('GOOGLE_SEARCH_API_KEY')
GOOGLE_CSE_ID = os.getenv('GOOGLE_CSE_ID')
INPUT_FILE = 'sites.csv'
OUTPUT_FILE = 'sites_out.csv'
MAX_WORKERS = 5
MAX_RETRIES = 3
RETRY_DELAY = 5
MAX_SEARCH_RESULTS = 10
API_CALL_LIMIT = 10
TIME_PERIOD = 60
BATCH_SIZE = 10
DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"
HRAI_LOGGING_ENABLED = os.getenv('HRAI_LOGGING_ENABLED', 'false').lower() == 'true'

# HumanReadable Logger
hrai_logger_instance = hrai_logger(
    base_url="https://api.humanreadable.ai",
    apikey=os.environ.get("HRAI_API_KEY"),
    project_id=os.environ.get("HRAI_PROJECT_ID")
) if HRAI_LOGGING_ENABLED else None

# OpenAI Client
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are an expert in evaluating potential customers for a pharmaceutical and manufacturing-focused company. Your task is to analyze company data and provide a structured response based on the following criteria:

1. Is the company involved in pharma or manufacturing?
2. Is the company currently active?

Respond only in the following JSON format:
{
    "pharma_or_manufacturing": true/false,
    "currently_active": true/false,
    "justification": "A brief explanation of your decision"
}
"""

URL_SELECTION_SYSTEM_PROMPT = """
You are an AI assistant that helps in selecting the most relevant URL for a company based on search results. You will be given a company name, a list of search results, and a query. Your task is to analyze the search results and select the most relevant URL for the company.

The JSON format for your response should be:
{
    "selected_url": "the most relevant URL",
    "reason": "the reason for selecting this URL"
}
"""

# Random User-Agent headers to mimic human browsing
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1"
]

@sleep_and_retry
@limits(calls=API_CALL_LIMIT, period=TIME_PERIOD)
def make_request(url, headers=None):
    response = requests.get(url, timeout=10, headers=headers)
    response.raise_for_status()
    return response

def get_random_user_agent():
    return random.choice(USER_AGENTS)

def is_valid_company_name(name):
    """Check if the company name is valid."""
    return bool(re.match(r'^[A-Za-z0-9\s\-&.,]+$', name))

@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=MAX_RETRIES)
def search_company(company_name, query):
    """Search for the company website using Google Custom Search API."""
    if not is_valid_company_name(company_name):
        logger.warning(f"Invalid company name: {company_name}")
        return []

    search_query = query
    search_url = f"https://www.googleapis.com/customsearch/v1"
    params = {
        'key': GOOGLE_API_KEY,
        'cx': GOOGLE_CSE_ID,
        'q': search_query,
        'num': MAX_SEARCH_RESULTS
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(search_url, params=params)
            response.raise_for_status()
            search_results = response.json().get('items', [])
            urls = [item['link'] for item in search_results]

            if urls:
                logger.info(f"Found {len(urls)} search results for {company_name} - Query: {query}")
                return urls
            else:
                logger.warning(f"No search results found for {company_name} - Query: {query}")
                return []
        except requests.RequestException as e:
            logger.error(f"Error searching for {company_name} (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (2 ** attempt))  # Exponential backoff
            else:
                logger.error(f"Max retries reached for {company_name}, switching to DuckDuckGo.")
                return search_duckduckgo(company_name, query)

def search_duckduckgo(company_name, query):
    """Fallback to DuckDuckGo if Google fails."""
    search_query = query
    data = {'q': search_query}
    headers = {'User-Agent': get_random_user_agent()}

    try:
        response = requests.post(DUCKDUCKGO_URL, data=data, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        search_results = [result['href'] for result in soup.find_all('a', href=True) if 'duckduckgo.com' not in result['href']]
        return search_results[:MAX_SEARCH_RESULTS]
    except requests.RequestException as e:
        logger.error(f"DuckDuckGo search failed for {company_name}: {str(e)}")
        return []

def get_webpage_content(url):
    """Fetch and parse the webpage content."""
    try:
        response = make_request(url, headers={'User-Agent': get_random_user_agent()})
        soup = BeautifulSoup(response.content, 'html.parser')
        content = soup.get_text()
        logger.info(f"Successfully fetched content from {url} ({len(content)} characters)")
        return content
    except Exception as e:
        logger.error(f"Error fetching webpage {url}: {str(e)}")
        return None

def extract_json_from_text(text):
    """Extract JSON from text that may contain additional content."""
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            logger.error(f"Failed to parse extracted JSON: {json_match.group(0)}")
    return None

def get_chat_completion(prompt, system_prompt):
    """Get chat completion using OpenAI GPT-4 with optional HRAI logging."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    if HRAI_LOGGING_ENABLED:
        @hrai_logger_instance.readable
        def logged_completion():
            return openai_client.chat.completions.create(model="gpt-4", messages=messages)
        return logged_completion()
    else:
        return openai_client.chat.completions.create(model="gpt-4", messages=messages)

def evaluate_company(company_data, webpage_content, url):
    """Evaluate the company based on company data and webpage content."""
    prompt = f"""
    Based on the following company information and webpage content, evaluate the company according to the criteria specified in the system prompt.

    Company Data:
    {company_data}

    Webpage Content:
    {webpage_content[:5000]}  # Limiting content to first 5000 characters

    URL: {url}

    Provide your analysis in the specified JSON format.
    """
    return extract_json_from_text(get_chat_completion(prompt, SYSTEM_PROMPT)['choices'][0]['message']['content'])

def select_company_url(company_name, search_results, query):
    """Select the most relevant URL for the company."""
    if not search_results:
        return None

    prompt = f"""
    Given the company name '{company_name}' and the following search results, select the most relevant URL for the company.

    Search Results:
    {json.dumps(search_results)}

    Query: {query}

    Provide your analysis in the specified JSON format.
    """
    response = get_chat_completion(prompt, URL_SELECTION_SYSTEM_PROMPT)
    response_content = extract_json_from_text(response['choices'][0]['message']['content'])
    return response_content.get("selected_url")

def load_checkpoint(output_file):
    """Load checkpoint from the output file to avoid reprocessing companies."""
    if os.path.exists(output_file):
        with open(output_file, 'r', newline='', encoding='utf-8') as outfile:
            reader = csv.DictReader(outfile)
            processed_companies = {row['Account Name'] for row in reader}
            return processed_companies
    return set()

def process_company(row, writer, lock):
    """Process a single company using the AI-guided flow."""
    company_name = row.get('Account Name', '').strip()

    if not is_valid_company_name(company_name):
        logger.warning(f"Skipping invalid company name: {company_name}")
        result = {**row, 'ERROR': 'Invalid company name'}
    else:
        company_data = ', '.join(f"{k}: {v}" for k, v in row.items() if v)

        try:
            query = f"Company {company_name} official website"
            search_results = search_company(company_name, query)

            if not search_results:
                logger.warning(f"No search results found for {company_name}")
                company_url = None
            else:
                company_url = select_company_url(company_name, search_results, query)

            if not company_url:
                logger.warning(f"No suitable URL found for {company_name}")
                result = {**row, 'USED_URL': 'N/A', 'PHARMA_OR_MANUFACTURING': 'N/A', 'CURRENTLY_ACTIVE': 'N/A', 'JUSTIFICATION': 'No suitable URL found', 'ERROR': 'No suitable URL found'}
            else:
                webpage_content = get_webpage_content(company_url)
                if not webpage_content:
                    result = {**row, 'USED_URL': company_url, 'PHARMA_OR_MANUFACTURING': 'N/A', 'CURRENTLY_ACTIVE': 'N/A', 'JUSTIFICATION': 'Failed to fetch webpage content', 'ERROR': 'Failed to fetch webpage content'}
                else:
                    evaluation = evaluate_company(company_data, webpage_content, company_url)
                    result = {
                        **row,
                        'USED_URL': company_url,
                        'PHARMA_OR_MANUFACTURING': str(evaluation.get('pharma_or_manufacturing', 'N/A')),
                        'CURRENTLY_ACTIVE': str(evaluation.get('currently_active', 'N/A')),
                        'JUSTIFICATION': evaluation.get('justification', 'N/A'),
                    }
        except Exception as e:
            logger.error(f"Error processing {company_name}: {str(e)}")
            result = {**row, 'USED_URL': 'N/A', 'PHARMA_OR_MANUFACTURING': 'N/A', 'CURRENTLY_ACTIVE': 'N/A', 'JUSTIFICATION': 'N/A', 'ERROR': str(e)}

    with lock:
        writer.writerow(result)

    return result

def process_data(input_file, output_file):
    """Process the input CSV file and write results to the output file."""
    processed_companies = load_checkpoint(output_file)

    with open(input_file, 'r', newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames + ['USED_URL', 'PHARMA_OR_MANUFACTURING', 'CURRENTLY_ACTIVE', 'JUSTIFICATION', 'ERROR']

        with open(output_file, 'a', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            if os.stat(output_file).st_size == 0:
                writer.writeheader()

            lock = threading.Lock()
            batch = []

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_row = {
                    executor.submit(process_company, row, writer, lock): row
                    for row in reader
                    if row['Account Name'] not in processed_companies
                }

                for future in tqdm(as_completed(future_to_row), total=len(future_to_row), desc="Processing companies"):
                    batch.append(future.result())

                    if len(batch) >= BATCH_SIZE:
                        with lock:
                            for result in batch:
                                writer.writerow(result)
                        batch = []

                if batch:
                    with lock:
                        for result in batch:
                            writer.writerow(result)

@click.command()
@click.option('--input-file', default=INPUT_FILE, help='Path to the input CSV file')
@click.option('--output-file', default=OUTPUT_FILE, help='Path to the output CSV file')
def data_mining_cmd(input_file, output_file):
    """Run the AI-guided data mining script to evaluate potential customers."""
    start_time = time.time()
    click.echo("Starting AI-guided data mining process...")

    try:
        process_data(input_file, output_file)
        end_time = time.time()
        processing_time = end_time - start_time
        click.echo(click.style(f"\nData mining completed successfully!", fg="green", bold=True))
        click.echo(f"Results saved to: {click.style(output_file, fg='blue', underline=True)}")
        click.echo(f"Processing Time: {click.style(f'{processing_time:.2f} seconds', fg='yellow')}")
    except Exception as e:
        click.echo(click.style(f"\nError during processing: {str(e)}", fg="red", bold=True), err=True)

if __name__ == "__main__":
    data_mining_cmd()
