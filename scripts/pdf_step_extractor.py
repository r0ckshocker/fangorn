import os
import json
import logging
import click
import pdfplumber
from concurrent.futures import ThreadPoolExecutor, as_completed
from textwrap import dedent
import re
import time
from dotenv import load_dotenv
from tqdm import tqdm
from scripts.alfred import ask_alfred  # Import the ask_alfred function

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
DOC_CHAR_BUDGET = 8000
MAX_RETRIES = 3
MAX_WORKERS = 5  # Number of threads for parallel processing

def extract_text_from_pdf(file_path):
    """Extracts text from the PDF file using pdfplumber."""
    try:
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
        logger.info("Extracted text from PDF")
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        raise

def clean_extracted_text(text):
    """Cleans the extracted text by adding spaces between words."""
    text = re.sub(r'(?<=[.,])(?=[^\s])', r' ', text)
    text = re.sub(r'(?<=[a-z])(?=[A-Z])', r' ', text)
    return text

def chunk_document(document_text, chunk_size=DOC_CHAR_BUDGET):
    """Splits the document into chunks of approximately chunk_size characters."""
    chunks = []
    current_chunk = ""
    for line in document_text.split('\n'):
        if len(current_chunk) + len(line) > chunk_size:
            chunks.append(current_chunk.strip())
            current_chunk = line
        else:
            current_chunk += line + '\n'
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

def generate_system_prompt():
    """Generates the system prompt for Alfred."""
    return """You are an expert in pharmaceutical manufacturing procedures and GMP (Good Manufacturing Practice) guidelines. Your task is to analyze pharmaceutical procedure documents and extract detailed, structured information about each procedural step.

    Key points:
    1. Focus only on the actual procedure steps. Ignore title pages, tables of contents, introductions, checklists, and other non-procedural content.
    2. Maintain the original order of steps as presented in the document. Do not reorder steps.
    3. Each step should be clearly defined with its name and description.
    4. Capture all relevant details for each step, including equipment, materials, measurements, and specific instructions.
    5. Within each step, include ALL actions mentioned, even if they are not explicitly numbered in the original text.
    6. Create a separate action for each distinct instruction, bullet point, or subprocess within a step.
    7. Pay attention to safety precautions, quality control checks, and critical process parameters.
    8. If a step involves multiple sub-steps or actions, include them as separate actions within that step.
    9. Ensure that the extracted information adheres to GMP standards and regulatory requirements.
    10. If you encounter any ambiguities or potential issues in the procedure, note them in the 'comments' field.
    11. Extract all information present in the document, including form numbers, specific instructions, and notes."""

def generate_user_prompt(document_chunk, chunk_number, total_chunks):
    """Generates the user prompt for extracting steps using Alfred."""
    prompt = f"""
    Analyze the following chunk ({chunk_number} of {total_chunks}) of a pharmaceutical procedure document and extract detailed procedural steps. Ignore title pages, tables of contents, introductions, and other non-procedural content. If no procedural steps are found in this chunk, return an empty list.

    Provide the structured output in the following JSON format only if procedural steps are found:

    [
        {{
            "name": "Step Name",
            "type": "Procedure Type (e.g., Preparation, Execution, Verification, Cleaning)",
            "description": "Detailed description of the step",
            "equipment": ["List of equipment used"],
            "materials": ["List of materials used"],
            "actions": [
                {{
                    "description": "Detailed description of the action",
                    "parameters": [
                        {{
                            "name": "Parameter Name",
                            "value": "Parameter Value",
                            "unit": "Unit of measurement (if applicable)"
                        }}
                    ]
                }}
            ],
            "critical_parameters": [
                {{
                    "name": "Critical Parameter Name",
                    "acceptable_range": "Acceptable range or threshold",
                    "unit": "Unit of measurement"
                }}
            ],
            "safety_precautions": ["List of safety precautions"],
            "quality_checks": ["List of quality control checks"],
            "relevant_documents": ["List of relevant documents, sops, or forms"],
            "comments": "Any additional comments or notes about the step"
        }}
    ]

    Document Chunk:
    {document_chunk}

    Please extract steps from this chunk, including all detailed actions within each step. If no procedural steps are found, return an empty list.
    """
    return dedent(prompt)

def get_alfred_completion(system_prompt, user_prompt, retries=MAX_RETRIES):
    """Uses Alfred to extract steps from the provided prompt."""
    for attempt in range(retries):
        try:
            response = ask_alfred(user_prompt, system_prompt)
            return response
        except Exception as e:
            logger.error(f"Alfred API error: {e}. Attempt {attempt + 1}/{retries}")
            if attempt < retries - 1:
                continue
            else:
                raise e

def clean_step_data(step_data):
    """Removes markdown code block formatting from the step data."""
    return step_data.strip()

def extract_json_from_response(response_text):
    """Extracts JSON from Alfred's response text."""
    try:
        # Find the start of the JSON array
        json_start = response_text.find('[')
        if json_start == -1:
            json_start = response_text.find('{')
        if json_start == -1:
            raise ValueError("No JSON start found")
        
        # Find the end of the JSON array or object
        json_end = response_text.rfind(']')
        if json_end == -1:
            json_end = response_text.rfind('}')
        if json_end == -1:
            raise ValueError("No JSON end found")
        
        # Extract the JSON part
        json_str = response_text[json_start:json_end+1].strip()
        
        # Parse the JSON
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON Decode Error: {e}")
        logger.error(f"Problematic JSON string: {json_str}")
        raise
    except Exception as e:
        logger.error(f"Error extracting JSON: {e}")
        logger.error(f"Full response text: {response_text}")
        raise

def extract_steps_from_document_chunk(chunk, system_prompt, chunk_number, total_chunks):
    """Helper function to extract steps from a document chunk using Alfred."""
    user_prompt = generate_user_prompt(chunk, chunk_number, total_chunks)
    try:
        step_data = get_alfred_completion(system_prompt, user_prompt)
        logger.info(f"Raw step data from Alfred for chunk {chunk_number}: {step_data}")

        # Clean the step_data
        step_data = clean_step_data(step_data)

        # Extract JSON from Alfred's response
        steps = extract_json_from_response(step_data)

        if not steps:
            logger.info(f"No procedural steps found in chunk {chunk_number}")
            return []

        logger.info(f"Extracted steps from chunk {chunk_number}: {steps}")
        return steps
    except Exception as e:
        logger.error(f"Error extracting steps from chunk {chunk_number}: {e}")
        return []  # Return an empty list in case of error

def extract_steps_from_document(document_text):
    """Extracts steps from the document using Alfred."""
    chunks = chunk_document(document_text)
    system_prompt = generate_system_prompt()
    all_steps = []

    with tqdm(total=len(chunks), desc="Processing chunks", unit="chunk") as pbar:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_chunk = {executor.submit(extract_steps_from_document_chunk, 
                                               chunk, system_prompt, i+1, len(chunks)): i 
                               for i, chunk in enumerate(chunks)}
            
            for future in as_completed(future_to_chunk):
                chunk_index = future_to_chunk[future]
                try:
                    steps = future.result()
                    if steps:
                        all_steps.append((chunk_index, steps))
                    pbar.update(1)
                    pbar.set_postfix({"Processed Chunk": chunk_index + 1})
                except Exception as e:
                    logger.error(f"Error processing document chunk {chunk_index + 1}: {e}")
                    pbar.update(1)

    all_steps.sort(key=lambda x: x[0])
    return [step for _, chunk_steps in all_steps for step in chunk_steps]

def number_steps_and_actions(steps):
    """Add step numbers and action numbers to the extracted steps."""
    for i, step in enumerate(steps, start=1):
        step['step_number'] = str(i)
        for j, action in enumerate(step['actions'], start=1):
            action['action_number'] = f"{i}.{j}"
    return steps

def process_pdf(file_path):
    """Processes the PDF to extract steps using text data."""
    click.echo("Extracting text from PDF...")
    document_text = extract_text_from_pdf(file_path)

    click.echo("Cleaning extracted text...")
    cleaned_text = clean_extracted_text(document_text)

    click.echo("Extracting steps from text...")
    steps = extract_steps_from_document(cleaned_text)

    if not steps:
        logger.warning("No steps were extracted from the document.")
    else:
        click.echo("Numbering steps and actions...")
        steps = number_steps_and_actions(steps)
    
    return steps

@click.command()
@click.option('--pdf-path', required=True, help='Path to the input PDF file')
@click.option('--output-path', required=True, help='Path for saving the output JSON file')
def pdf_step_extractor(pdf_path, output_path):
    """Extract steps from a PDF and save results to a local JSON file."""
    start_time = time.time()
    click.echo("Starting PDF step extraction process...")
    
    try:
        with click.progressbar(length=100, label="Overall progress") as bar:
            bar.update(10)
            steps = process_pdf(pdf_path)
            bar.update(80)

            click.echo("Saving extracted steps to JSON...")
            with open(output_path, 'w') as json_file:
                json.dump(steps, json_file, indent=4)
            bar.update(10)

        end_time = time.time()
        processing_time = end_time - start_time
        
        if steps:
            click.echo(click.style(f"\nStep extraction completed successfully!", fg="green", bold=True))
        else:
            click.echo(click.style(f"\nStep extraction completed, but no steps were extracted.", fg="yellow", bold=True))
        
        click.echo(f"Results saved to: {click.style(output_path, fg='blue', underline=True)}")
        click.echo(f"Processing Time: {click.style(f'{processing_time:.2f} seconds', fg='yellow')}")
        click.echo(f"Steps Generated: {click.style(str(len(steps)), fg='yellow')}")
    except Exception as e:
        click.echo(click.style(f"\nError during processing: {str(e)}", fg="red", bold=True), err=True)

if __name__ == "__main__":
    pdf_step_extractor()
