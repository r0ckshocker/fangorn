import boto3
import json
import os
import logging
import camelot
import openai
from tabulate import tabulate
from urllib.parse import unquote_plus
from openai.error import OpenAIError
from concurrent.futures import ThreadPoolExecutor
from textwrap import dedent

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3 = boto3.client('s3')

# OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Constants
DOC_CHAR_BUDGET = 8000
LOOKBACK_PAGES = 1
MAX_RETRIES = 3

def event_object(event):
    """Parses an S3 event to extract bucket name and object key."""
    try:
        record = event["Records"][0]
        s3_obj = record["s3"]
        bucket_name = s3_obj["bucket"].get("name")
        key_name = unquote_plus(s3_obj["object"].get("key"))

        if not bucket_name or not key_name:
            raise ValueError("Missing bucket or key information")

        return bucket_name, key_name
    except (KeyError, IndexError, ValueError) as e:
        logger.error(f"Error parsing event: {e}")
        raise Exception("Invalid S3 event structure")

def get_tags(bucket, key):
    """Retrieves the tags associated with an S3 object."""
    try:
        response = s3.get_object_tagging(Bucket=bucket, Key=key)
        tags = response.get('TagSet', [])
        logger.info(f"Tags: {tags}")
        return tags
    except s3.exceptions.NoSuchKey:
        logger.error(f"No such key: {key} in bucket: {bucket}")
        raise
    except Exception as e:
        logger.error(f"Failed to get tags: {e}")
        raise

def download_pdf(bucket, key):
    """Downloads the PDF from S3 and returns the local file path."""
    local_file_path = f"/tmp/{os.path.basename(key)}"
    logger.info(f"Downloading PDF from s3://{bucket}/{key} to {local_file_path}")

    try:
        s3.download_file(bucket, key, local_file_path)
        logger.info(f"Downloaded PDF to {local_file_path}")
        return local_file_path
    except s3.exceptions.NoSuchKey:
        logger.error(f"PDF not found in s3://{bucket}/{key}")
        raise
    except Exception as e:
        logger.error(f"Failed to download PDF from S3: {e}")
        raise

def upload_json(bucket, key, json_data, tags):
    """Uploads the processed JSON data to S3."""
    json_key = key.replace('.pdf', '.json')
    tagging_string = "&".join(f"{tag['Key']}={tag['Value']}" for tag in tags)

    logger.info(f"Uploading JSON to s3://{bucket}/{json_key}")
    try:
        s3.put_object(
            Bucket=bucket,
            Key=json_key,
            Body=json.dumps(json_data, indent=4),
            ContentType='application/json',
            Tagging=tagging_string
        )
        logger.info(f"JSON uploaded to S3 at s3://{bucket}/{json_key}")
    except Exception as e:
        logger.error(f"Failed to upload JSON to S3: {e}")
        raise

def extract_tables(file_path):
    """Extracts tables from the PDF file using Camelot."""
    try:
        tables = camelot.read_pdf(file_path, pages='all', flavor='stream')  # Use stream for complex tables
        table_texts = {
            table.page: tabulate(table.df, showindex=False, tablefmt="plain") for table in tables
        }
        logger.info(f"Extracted {len(tables)} tables from PDF")
        return table_texts
    except Exception as e:
        logger.error(f"Error extracting tables from PDF: {e}")
        raise

def generate_prompt(document_text, previous_steps):
    """Generates a prompt for extracting steps using OpenAI."""
    prior_steps_json = json.dumps(previous_steps, indent=2)
    prompt = f"""
    You are tasked with extracting procedural steps from a pharmaceutical procedure document.
    Given the following document text and previously extracted steps, identify the next procedural steps
    and provide them in the following JSON format:

    [
        {{
            "name": "Step 1",
            "process_actions": [
                {{
                    "type": "text input",
                    "name": "My input"
                }},
                ...
            ]
        }},
        ...
    ]

    Document Text: {document_text}

    Previously Extracted Steps: {prior_steps_json}

    Ensure each step is clearly identified and actions are accurately extracted.
    """
    return dedent(prompt)

def get_chat_completion(prompt, retries=MAX_RETRIES):
    """Uses OpenAI to extract steps from the provided prompt."""
    messages = [
        {"role": "system", "content": "You are a document parsing assistant for pharmaceutical procedures."},
        {"role": "user", "content": prompt}
    ]
    args = {
        'messages': messages,
        'model': 'gpt-4',
        'temperature': 0.0
    }

    for attempt in range(retries):
        try:
            completion = openai.ChatCompletion.create(**args)
            return completion.choices[0].message['content']
        except OpenAIError as e:
            logger.error(f"OpenAI API error: {e}. Attempt {attempt + 1}/{retries}")
            if attempt < retries - 1:
                continue
            else:
                raise e

def extract_steps_from_document(document_text, previous_steps):
    """Extracts steps from the document using OpenAI."""
    all_steps = previous_steps.copy()
    paragraphs = document_text.split('\n\n')

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        prompt = generate_prompt(paragraph, all_steps)
        try:
            step_data = get_chat_completion(prompt)
            steps = json.loads(step_data)
            all_steps.extend(steps)
        except (OpenAIError, json.JSONDecodeError) as e:
            logger.error(f"Error extracting steps: {e}")

    return all_steps

def process_pdf(file_path):
    """Processes the PDF to extract steps using text and table data."""
    # Extract text and tables
    table_texts = extract_tables(file_path)

    # Extract steps from tables
    steps = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(extract_steps_from_document, table_text, steps) for page, table_text in table_texts.items()]
        for future in futures:
            try:
                steps.extend(future.result())
            except Exception as e:
                logger.error(f"Error processing table text: {e}")

    return steps

def handler(event, context):
    """Lambda handler for processing PDF and extracting steps."""
    try:
        # Parse the S3 event
        bucket, key = event_object(event)

        # Get S3 object tags
        tags = get_tags(bucket, key)

        # Download PDF
        local_pdf_path = download_pdf(bucket, key)

        # Process PDF to extract steps
        steps = process_pdf(local_pdf_path)

        # Upload extracted steps as JSON to S3
        upload_json(bucket, key, steps, tags)

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Successfully processed PDF and uploaded JSON."})
        }
    except Exception as e:
        logger.error(f"Handler error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Failed to process PDF"})
        }
