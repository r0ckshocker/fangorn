import json
import boto3
import os
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
from urllib.parse import unquote_plus
from collections import Counter
import PyPDF2
import docx
import chardet
from anthropic import Anthropic
from openai import OpenAI
import math

import logging

# Configure logger with structured format
logging.basicConfig(
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Initialize clients
s3 = boto3.client('s3')
anthropic_client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY")) if os.environ.get("OPENAI_API_KEY") else None

# Constants
MAX_RETRIES = 3
MAX_WORKERS = 5
USER_FACT_MAX = 50
SIMILARITY_THRESHOLD = 0.90
SUPPORTED_EXTENSIONS = {'.pdf', '.txt', '.docx', '.csv', '.py', '.json', '.log', '.md', '.html', '.js', '.css'}
CHUNK_SIZE = 8000

def set_request_id(context):
    """Set request ID from Lambda context for log correlation."""
    if context and hasattr(context, 'aws_request_id'):
        logger.info(f"Request ID: {context.aws_request_id}")
        return context.aws_request_id
    return None

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate the cosine similarity between two vectors."""
    try:
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)
    except Exception as e:
        logger.error(f"Error calculating similarity: {e}")
        return 0.0

def analyze_document_chunk(chunk: str) -> Dict:
    """Analyze a single document chunk."""
    try:
        prompt = """Analyze this document chunk and create a structured analysis. 
        Output ONLY valid JSON with this exact structure:
        {
            "summary": "Brief summary of chunk content",
            "key_points": ["List of important points"],
            "technical_details": ["Any technical specifics"],
            "topics": ["Main topics covered"],
            "concerns": ["List of potential issues or concerns"]
        }

        Rules:
        1. Only output valid JSON, nothing else
        2. Keep responses concise and relevant
        3. Include specific technical details when present
        4. List actual concerns found, not hypotheticals
        5. Ensure all arrays contain strings"""

        response = anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            temperature=0,
            system="You are a document analysis assistant. Only output valid JSON analysis.",
            messages=[{
                "role": "user", 
                "content": f"{prompt}\n\nDocument chunk to analyze:\n{chunk}"
            }]
        )

        # Clean and parse response
        json_str = response.content[0].text.strip()
        json_start = json_str.find('{')
        json_end = json_str.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            analysis = json.loads(json_str[json_start:json_end])
            
            # Validate and standardize fields
            required_fields = ['summary', 'key_points', 'technical_details', 'topics', 'concerns']
            for field in required_fields:
                if field not in analysis:
                    analysis[field] = [] if field != 'summary' else 'No summary provided'
                elif field != 'summary' and not isinstance(analysis[field], list):
                    analysis[field] = []
                
            return analysis

        raise ValueError("No valid JSON found in response")

    except Exception as e:
        logger.error(f"Error analyzing chunk: {str(e)}")
        return {
            "summary": "Error analyzing chunk",
            "key_points": [],
            "technical_details": [],
            "topics": [],
            "concerns": []
        }

def merge_analyses(analyses: List[Dict]) -> Dict:
    """Merge multiple chunk analyses with improved deduplication."""
    if not analyses:
        return {
            "summary": "No analysis available",
            "topics": [],
            "technical_details": [],
            "concerns": [],
            "key_points": []
        }

    # Use sets for deduplication
    all_topics = set()
    all_details = set()
    all_concerns = set()
    all_points = set()
    summaries = []

    for analysis in analyses:
        if not isinstance(analysis, dict):
            continue

        if analysis.get("summary") and analysis["summary"] != "Error analyzing chunk":
            summaries.append(analysis["summary"])

        # Process lists if they exist
        for field, target_set in [
            ("topics", all_topics),
            ("technical_details", all_details),
            ("concerns", all_concerns),
            ("key_points", all_points)
        ]:
            if isinstance(analysis.get(field), list):
                target_set.update(item for item in analysis[field] if isinstance(item, str))

    # Create final merged analysis
    summary = " ".join(summaries) if summaries else "No summary available"
    if len(summary) > 1000:
        summary = summary[:997] + "..."

    return {
        "summary": summary,
        "topics": sorted(list(all_topics)),
        "technical_details": sorted(list(all_details)),
        "concerns": sorted(list(all_concerns)),
        "key_points": sorted(list(all_points))
    }

def read_file_content(file_path: str) -> str:
    """Read and extract content from supported file types."""
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    try:
        if ext == '.pdf':
            with open(file_path, 'rb') as f:
                pdf = PyPDF2.PdfReader(f)
                return '\n'.join(
                    page.extract_text() 
                    for page in pdf.pages
                )

        elif ext == '.docx':
            doc = docx.Document(file_path)
            return '\n'.join(
                para.text 
                for para in doc.paragraphs
            )

        else:  # txt, csv, py, json, etc.
            with open(file_path, 'rb') as f:
                raw = f.read()
                encoding = chardet.detect(raw)['encoding'] or 'utf-8'
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()

    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        raise

def get_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for texts using OpenAI with validation."""
    if not openai_client or not texts:
        return []
        
    try:
        valid_texts = [text.strip() for text in texts if text and text.strip()]
        if not valid_texts:
            return []

        try:
            response = openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=valid_texts
            )
            embeddings = [item.embedding for item in response.data]
            logger.info(f"Generated {len(embeddings)} embeddings")
            return embeddings
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return []
            
    except Exception as e:
        logger.error(f"Error getting embeddings: {e}")
        return []

def analyze_conversation(content: str, user_messages: Optional[str] = None) -> Dict:
    """Extract user facts from conversation content."""
    try:
        if not content.strip():
            return {"user_facts": []}

        analysis_content = (
            f"User Messages:\n{user_messages}\n\nFull Conversation:\n{content}"
            if user_messages else content
        )

        prompt = """Analyze this conversation to extract ONLY definitive facts about the user.
        Focus on:
        - Role and permissions
        - Work patterns and preferences
        - Technical skills and knowledge
        - Project involvement
        - Tool usage patterns
        - Communication style
        - Important personal details

        Format response EXACTLY as this JSON structure:
        {
            "user_facts": [
                "Specific fact about user's role/preferences/skills/etc"
            ]
        }

        Rules:
        1. Only include information that is clearly stated or strongly implied
        2. Focus on facts about the user themselves
        3. Include only information relevant for future interactions
        4. Avoid speculation or uncertain information
        5. Output ONLY the JSON, no other text
        6. Each fact should be a complete, standalone statement"""

        response = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1000,
            temperature=0,
            system="You are an analysis assistant that outputs only valid JSON.",
            messages=[{
                "role": "user",
                "content": f"{prompt}\n\nConversation to analyze:\n{analysis_content[:2000]}"
            }]
        )

        # Clean and parse response
        json_str = response.content[0].text.strip()
        json_start = json_str.find('{')
        json_end = json_str.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            clean_json = json_str[json_start:json_end]
            result = json.loads(clean_json)
            
            # Validate and clean facts
            facts = result.get("user_facts", [])
            valid_facts = [
                fact for fact in facts 
                if isinstance(fact, str) and fact.strip()
            ][:5]  # Limit to top 5 most relevant facts
            
            return {"user_facts": valid_facts}

        raise ValueError("No valid JSON found in response")

    except Exception as e:
        logger.error(f"Error analyzing conversation: {e}")
        return {"user_facts": []}

def update_embeddings_file(bucket: str, key: str, texts: List[str], 
                         embeddings: List[List[float]], metadata: List[Dict], max_facts: int = USER_FACT_MAX) -> bool:
    """Update embeddings file with enhanced deduplication and validation."""
    logger.info(f"Updating embeddings at {key} with {len(texts)} new items")
    try:
        # Validate input arrays
        if len(texts) != len(embeddings) or len(embeddings) != len(metadata):
            logger.error("Mismatched input array lengths")
            return False

        # Get existing data with error handling
        try:
            current_obj = s3.get_object(Bucket=bucket, Key=key)
            existing_data = json.loads(current_obj['Body'].read())
            version_id = current_obj.get('VersionId')
            
            # Validate existing data structure
            if not all(k in existing_data for k in ["texts", "embeddings", "metadata"]):
                logger.warning("Invalid existing data structure, initializing new")
                existing_data = {"texts": [], "embeddings": [], "metadata": []}
            
            # Get existing items with validation
            existing_items = []
            for t, e, m in zip(
                existing_data.get("texts", []),
                existing_data.get("embeddings", []),
                existing_data.get("metadata", [])
            ):
                if not all([
                    isinstance(t, str),
                    isinstance(e, list) and len(e) > 0,
                    isinstance(m, dict)
                ]):
                    logger.warning(f"Skipping invalid existing item: {t[:100]}")
                    continue
                existing_items.append((t, e, m))
                
        except s3.exceptions.NoSuchKey:
            logger.info(f"No existing embeddings file at {key}, creating new")
            existing_data = {"texts": [], "embeddings": [], "metadata": []}
            existing_items = []
            version_id = None
        except Exception as e:
            logger.error(f"Error reading existing embeddings: {e}")
            return False

        # Validate and filter new items
        valid_items = []
        for t, e, m in zip(texts, embeddings, metadata):
            if not all([
                isinstance(t, str) and t.strip(),
                isinstance(e, list) and len(e) > 0,
                isinstance(m, dict) and 'timestamp' in m
            ]):
                logger.warning(f"Skipping invalid new item: {t[:100]}")
                continue
            valid_items.append((t.strip(), e, m))

        if not valid_items:
            logger.info("No valid new items to add")
            return True

        # Combine items with enhanced deduplication
        all_items = []
        seen_texts = set()
        duplicate_count = 0

        # Process new items first
        for new_text, new_emb, new_meta in valid_items:
            if new_text in seen_texts:
                duplicate_count += 1
                continue

            # Check semantic similarity with existing items
            duplicates = []
            for i, (exist_text, exist_emb, exist_meta) in enumerate(existing_items):
                try:
                    similarity = cosine_similarity(new_emb, exist_emb)
                    if similarity > SIMILARITY_THRESHOLD:
                        duplicates.append((i, similarity, exist_meta.get('timestamp', '')))
                except Exception as e:
                    logger.error(f"Error calculating similarity: {e}")
                    continue

            if not duplicates:
                all_items.append((new_text, new_emb, new_meta))
                seen_texts.add(new_text)
            else:
                # Keep most recent version if duplicates found
                duplicates.sort(key=lambda x: x[2], reverse=True)
                newest_duplicate = duplicates[0]
                if new_meta.get('timestamp', '') > newest_duplicate[2]:
                    all_items.append((new_text, new_emb, new_meta))
                else:
                    all_items.append(existing_items[newest_duplicate[0]])
                seen_texts.add(new_text)
                duplicate_count += 1

        # Add remaining existing items if not duplicated
        for exist_text, exist_emb, exist_meta in existing_items:
            if exist_text not in seen_texts:
                all_items.append((exist_text, exist_emb, exist_meta))
                seen_texts.add(exist_text)

        # Sort by timestamp and limit size
        all_items.sort(
            key=lambda x: (
                x[2].get('timestamp', ''),
                -len(x[2].get('source', ''))  # Secondary sort by source length
            ),
            reverse=True
        )
        all_items = all_items[:max_facts]

        # Update data with metadata
        updated_data = {
            "texts": [item[0] for item in all_items],
            "embeddings": [item[1] for item in all_items],
            "metadata": [item[2] for item in all_items],
            "stats": {
                "total_facts": len(all_items),
                "duplicates_removed": duplicate_count,
                "sources": dict(Counter(
                    item[2].get('source', 'unknown').split(':')[0] 
                    for item in all_items
                )),
            },
            "updated_at": datetime.utcnow().isoformat()
        }

        # Put object with TODO:version checking for historical embeddings
        try:
            extra_args = {}
            # if version_id:
            #     logger.info(f"Using version ID: {version_id}")

            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=json.dumps(updated_data, indent=2),
                ContentType='application/json',
                Metadata={
                    'total_facts': str(len(all_items)),
                    'duplicates_removed': str(duplicate_count),
                    'last_updated': updated_data['updated_at']
                },
                **extra_args
            )
            
            logger.info(
                f"Updated embeddings at {key} with {len(all_items)} items "
                f"({duplicate_count} duplicates removed)"
            )
            return True

        except Exception as e:
            logger.error(f"Error writing embeddings: {e}")
            return False

    except Exception as e:
        logger.error(f"Error in update_embeddings: {e}")
        return False

def batch_messages(messages: List[Dict], batch_size: int = 10) -> List[List[Dict]]:
    """Safely batch messages into chunks."""
    return [
        messages[i:i + batch_size]
        for i in range(0, len(messages), batch_size)
    ]

def process_messages_json(bucket: str, key: str, messages: List[Dict]) -> bool:
    """Process conversation messages with parallel fact extraction."""
    try:
        parts = key.split('/')
        if len(parts) < 3:
            raise ValueError(f"Invalid key structure: {key}")
            
        username = parts[0]
        conv_id = parts[1]
        
        logger.info(f"Processing messages for conversation {conv_id}")

        msg_chunks = batch_messages(messages)
        facts_queue = Queue()
        
        def process_message_chunk(chunk):
            try:
                chunk_content = "\n".join([
                    f"{msg['role'].upper()}: {msg['content']}"
                    for msg in chunk
                    if msg.get('role') in ['user', 'assistant'] and msg.get('content')
                ])
                
                analysis = analyze_conversation(chunk_content)
                if analysis.get('user_facts'):
                    for fact in analysis['user_facts']:
                        facts_queue.put(fact)
            except Exception as e:
                logger.error(f"Error processing message chunk: {e}")

        # Process chunks in parallel
        chunk_count = len(msg_chunks)
        successful_chunks = 0
        failed_chunks = 0
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(process_message_chunk, chunk)
                for chunk in msg_chunks
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                    successful_chunks += 1
                except Exception as e:
                    failed_chunks += 1
                    logger.error(f"Error in message chunk processing: {e}")

        # Collect facts
        facts = []
        while not facts_queue.empty() and len(facts) < USER_FACT_MAX:
            facts.append(facts_queue.get())

        if not facts:
            logger.info("No user facts found in conversation")
            return True

        # Generate embeddings
        embeddings = get_embeddings(facts)
        if not embeddings:
            logger.warning("Could not generate embeddings for facts")
            return True

        # Create metadata
        metadata = [{
            "type": "user_fact",
            "source": f"conversation:{conv_id}",
            "timestamp": datetime.utcnow().isoformat(),
            "conversation_id": conv_id,
            "index": idx
        } for idx in range(len(facts))]

        # Update embeddings file
        success = update_embeddings_file(
            bucket,
            f"{username}/embeddings.json",
            facts,
            embeddings,
            metadata
        )
        
        logger.info(
            f"Processed {chunk_count} chunks "
            f"({successful_chunks} successful, {failed_chunks} failed) "
            f"and extracted {len(facts)} facts"
        )
        return success

    except Exception as e:
        logger.error(f"Error processing messages: {e}")
        return False

def get_document_embeddings(text_chunks: List[str]) -> List[List[float]]:
    """Generate embeddings for document chunks using OpenAI."""
    if not openai_client or not text_chunks:
        return []

    try:
        valid_chunks = [chunk.strip() for chunk in text_chunks if chunk and chunk.strip()]
        if not valid_chunks:
            return []

        embeddings = []
        # Process in batches of 100 to avoid rate limits
        for i in range(0, len(valid_chunks), 100):
            batch = valid_chunks[i:i+100]
            try:
                response = openai_client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=batch
                )
                embeddings.extend([item.embedding for item in response.data])
            except Exception as e:
                logger.error(f"OpenAI API error in batch {i}: {e}")
                continue

        logger.info(f"Generated {len(embeddings)} document chunk embeddings")
        return embeddings
    except Exception as e:
        logger.error(f"Error getting document embeddings: {e}")
        return []

def process_file(bucket: str, key: str, local_path: str) -> bool:
    """Process file content with parallel chunk analysis and embeddings."""
    logger.info(f"Starting file processing: s3://{bucket}/{key}")
    try:
        content = read_file_content(local_path)
        content_length = len(content) if content else 0
        logger.info(f"Read {content_length} bytes from {local_path}")

        if not content.strip():
            raise ValueError("Empty file content")

        # Split into smaller chunks for embeddings
        chunks = [
            content[i:i + CHUNK_SIZE] 
            for i in range(0, len(content), CHUNK_SIZE)
        ]

        chunk_count = len(chunks)
        logger.info(f"Split content into {chunk_count} chunks of size {CHUNK_SIZE}")

        # Generate embeddings for chunks
        embeddings = get_document_embeddings(chunks)
        if not embeddings:
            logger.error("Failed to generate document embeddings")
            return False

        # Process chunks for analysis in parallel
        analyses = []
        successful_chunks = 0
        failed_chunks = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_chunk = {
                executor.submit(analyze_document_chunk, chunk): idx 
                for idx, chunk in enumerate(chunks)
            }

            for future in as_completed(future_to_chunk):
                chunk_idx = future_to_chunk[future]
                try:
                    result = future.result()
                    if result and isinstance(result, dict):
                        analyses.append(result)
                        successful_chunks += 1
                    else:
                        failed_chunks += 1
                        logger.warning(f"Chunk {chunk_idx} produced invalid analysis")
                except Exception as e:
                    failed_chunks += 1
                    logger.error(f"Error processing chunk {chunk_idx}: {str(e)}")

        if not analyses:
            logger.error(f"Analysis failed: {failed_chunks} failed chunks out of {chunk_count}")
            return False

        # Merge analyses and prepare full document data
        merged_analysis = merge_analyses(analyses)
        
        # Create document embeddings data
        embeddings_data = {
            "chunks": chunks,
            "embeddings": embeddings,
            "metadata": [{
                "type": "document_chunk",
                "source": key,
                "chunk_index": idx,
                "timestamp": datetime.utcnow().isoformat()
            } for idx in range(len(chunks))],
            "document_info": {
                "key": key,
                "chunk_count": len(chunks),
                "total_length": content_length
            },
            "updated_at": datetime.utcnow().isoformat()
        }

        # Save embeddings
        embeddings_key = f"{os.path.splitext(key)[0]}_embeddings.json"
        s3.put_object(
            Bucket=bucket,
            Key=embeddings_key,x
            Body=json.dumps(embeddings_data, indent=2),
            ContentType='application/json'
        )

        # Save analysis
        analysis_key = f"{os.path.splitext(key)[0]}_analysis.json"
        s3.put_object(
            Bucket=bucket,
            Key=analysis_key,
            Body=json.dumps(merged_analysis, indent=2),
            ContentType='application/json',
            Metadata={
                'original_key': key,
                'chunks_processed': str(successful_chunks),
                'chunks_failed': str(failed_chunks),
                'embeddings_key': embeddings_key
            }
        )

        logger.info(f"Analysis and embeddings saved for {key}")
        return True

    except Exception as e:
        logger.error(f"Error processing file {key}: {str(e)}", exc_info=True)
        return False

def parse_sns_event(event: Dict) -> Tuple[str, str]:
    """Parse SNS event to extract S3 bucket and key."""
    try:
        sns_message = json.loads(event['Records'][0]['Sns']['Message'])
        
        if 'Event' in sns_message and sns_message['Event'] == 's3:TestEvent':
            logger.info("Processing S3 test event")
            return sns_message['Bucket'], 'test_event.txt'
        
        if 'Records' not in sns_message:
            raise ValueError("No 'Records' found in S3 event")
        
        s3_record = sns_message['Records'][0]['s3']
        bucket_name = s3_record['bucket']['name']
        key_name = unquote_plus(s3_record['object']['key'])

        if not bucket_name or not key_name:
            raise ValueError("Missing bucket or key information")

        return bucket_name, key_name
    except Exception as e:
        logger.error(f"Error parsing SNS event: {e}")
        raise

def should_process_file(key: str) -> bool:
    """
    Determine if a file should be processed based on its key.
    
    Rules:
    1. Ignore files in env_config/, lucius/, devision/ directories
    2. Only process files that either:
       - End with messages.json
       - Have uploads/ in their path
    
    Args:
        key: The S3 object key to check
        
    Returns:
        bool: True if the file should be processed, False otherwise
    """
    # Ignore specific directories
    excluded_prefixes = ['env_config/', 'lucius/', 'devision/', 'alfred/']
    if any(key.startswith(prefix) for prefix in excluded_prefixes):
        return False

    messages = key.endswith('messages.json')
    upload = '/uploads/' in key
    analysis = key.endswith('analysis.json')
    embeddings = key.endswith('embeddings.json')

    if analysis or embeddings:
        return False
    
    # Process only messages.json files or files in uploads/
    return key.endswith('messages.json') or '/uploads/' in key

def handler(event: Dict, context: Any) -> Dict:
    """Main Lambda handler with improved error handling."""
    request_id = set_request_id(context)
    temp_files = set()
    start_time = datetime.now()

    try:
        logger.info(f"Processing event: {json.dumps(event)}")
        bucket, key = parse_sns_event(event)
        logger.info(f"Parsed event for s3://{bucket}/{key}")

        if should_process_file(key):
            # Proceed with file processing
            if key.endswith('messages.json'):
                try:
                    messages = json.loads(s3.get_object(Bucket=bucket, Key=key)['Body'].read())
                    success = process_messages_json(bucket, key, messages)
                    status_code = 200 if success else 500
                    body = 'Successfully processed messages' if success else 'Failed to process messages'
                except Exception as e:
                    logger.error(f"Error processing messages.json: {str(e)}")
                    return {'statusCode': 500, 'body': str(e)}
            else:
                local_path = f"/tmp/{os.path.basename(key)}"
                temp_files.add(local_path)
                
                try:
                    s3.download_file(bucket, key, local_path)
                    success = process_file(bucket, key, local_path)
                    status_code = 200 if success else 500
                    body = 'Successfully processed file' if success else 'Failed to process file'
                except Exception as e:
                    logger.error(f"Error processing file: {str(e)}")
                    return {'statusCode': 500, 'body': str(e)}
        else:
            logger.info(f"Skipping file processing for {key}")
            return {'statusCode': 200, 'body': 'File skipped'}

        process_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Processing completed in {process_time:.2f} seconds")
        
        return {
            'statusCode': status_code,
            'body': body,
            'requestId': request_id,
            'processingTime': process_time
        }

    except Exception as e:
        logger.error(f"Handler error: {str(e)}")
        return {'statusCode': 500, 'body': str(e)}

    finally:
        # Cleanup temp files
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                logger.error(f"Error cleaning up {temp_file}: {str(e)}")


# Tests to verify the behavior
def test_should_process_file():
    # Should process
    assert should_process_file('user123/conv456/messages.json') == True
    assert should_process_file('user123/conv456/uploads/document.pdf') == True
    assert should_process_file('team/project/uploads/data.csv') == True
    
    # Should not process
    assert should_process_file('env_config/settings.json') == False
    assert should_process_file('lucius/data.json') == False
    assert should_process_file('devision/config.json') == False
    assert should_process_file('alfred/settings.json') == False
    assert should_process_file('random.json') == False
    assert should_process_file('user123/regular.json') == False
    assert should_process_file('user123/data/file.pdf') == False

if __name__ == "__main__":
    # Run tests
    test_should_process_file()
    print("All tests passed!")
    
    # Example usage
    test_keys = [
        'user123/conv456/messages.json',
        'user123/conv456/uploads/document.pdf',
        'env_config/settings.json',
        'lucius/data.json',
        'random.json'
    ]
    
    for key in test_keys:
        result = should_process_file(key)
        print(f"Key: {key:<40} Should process: {result}")