import datetime
import json
import logging
import os
import time
import uuid
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from openai import OpenAI
from anthropic import Anthropic
from flask import g
from scipy.spatial.distance import cosine

from app.server.services.helper.actions import LambdaService, S3Service
from app.server.services.helper.helper import get_or_throw

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

data_bucket = os.getenv("DATA_BUCKET")

class Entmoot:
    """Base Entmoot class with embedding capabilities."""
    
    def __init__(self, blob_filename, chat, tasks=None, lambda_function=None):
        self.blob_filename = blob_filename
        self.tasks = tasks if tasks else []
        self.data = {}
        self.lambda_function = lambda_function
        self.chat = chat
        self.s3_service = S3Service()
        self.lambda_service = LambdaService()
        self.admin_group = os.getenv("ADMIN_GROUP", "admin")
        self.user_group = os.getenv("USERS_GROUP", "users")
        self.dashboard_context = (
            "The Entmoot base class, the user is most likely developing a new Entmoot dashboard"
        )
        self.last_updated = None
        self.update_interval = timedelta(minutes=15)
        self.data_bucket = os.getenv("DATA_BUCKET")
        
        # Initialize OpenAI client if key is available
        self._init_openai()

    def _init_openai(self):
        """Initialize OpenAI client lazily"""
        self._openai_client = None
        self._embedding_cache = {}
        self._last_cache_clear = datetime.now()
        self._cache_duration = timedelta(minutes=5)
        self.SIMILARITY_THRESHOLD = 0.85

    @property
    def openai_client(self):
        """Lazy initialization of OpenAI client"""
        if self._openai_client is None and os.getenv("OPENAI_API_KEY"):
            try:
                self._openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
        return self._openai_client

    def _clear_old_cache(self):
        """Clear expired cache entries."""
        now = datetime.now()
        if now - self._last_cache_clear > self._cache_duration:
            self._embedding_cache.clear()
            self._last_cache_clear = now

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for text with caching."""
        if not self.openai_client or not text:
            return None
            
        self._clear_old_cache()
        cache_key = hash(text)
        
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]
            
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=[text]
            )
            embedding = response.data[0].embedding
            self._embedding_cache[cache_key] = embedding
            return embedding
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return None
    
    def get_document_context(self, query: str, conversation_id: str, user_email: str) -> List[Dict]:
        """Get relevant document chunks based on query similarity."""
        if not self.openai_client:
            return []
            
        query_embedding = self.get_embedding(query)
        if not query_embedding:
            return []
            
        try:
            username = self.chat.get_username_from_email(user_email)
            uploads_prefix = f"{username}/{conversation_id}/uploads/"
            
            # List all files in the conversation's uploads directory
            response = self.s3_service.list_objects_v2(
                Bucket=self.data_bucket,
                Prefix=uploads_prefix
            )
            
            all_relevant_chunks = []
            for obj in response.get('Contents', []):
                if not obj['Key'].endswith('_embeddings.json'):
                    continue
                    
                try:
                    embeddings_data = self.s3_service.get_json(self.data_bucket, obj['Key'])
                    if not embeddings_data:
                        continue
                        
                    chunks = embeddings_data.get('chunks', [])
                    doc_embeddings = embeddings_data.get('embeddings', [])
                    metadata = embeddings_data.get('metadata', [])
                    
                    # Calculate similarities
                    for chunk, emb, meta in zip(chunks, doc_embeddings, metadata):
                        similarity = self.calculate_similarity(query_embedding, emb)
                        if similarity > self.SIMILARITY_THRESHOLD:
                            all_relevant_chunks.append({
                                'chunk': chunk,
                                'similarity': similarity,
                                'metadata': meta
                            })
                            
                except Exception as e:
                    logger.error(f"Error processing embeddings file {obj['Key']}: {e}")
                    continue
            
            # Sort by similarity and return top chunks
            relevant_chunks = sorted(
                all_relevant_chunks,
                key=lambda x: x['similarity'],
                reverse=True
            )[:5]  # Limit to top 5 most relevant chunks
            
            return relevant_chunks
            
        except Exception as e:
            logger.error(f"Error getting document context: {e}")
            return []
            

    def calculate_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between vectors."""
        if not vec1 or not vec2:
            return 0.0
        try:
            return 1 - cosine(vec1, vec2)
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0

    def get_relevant_facts(self, query: str, username: str) -> List[Dict]:
        """Get relevant user facts based on query similarity."""
        if not self.openai_client:
            return []
            
        query_embedding = self.get_embedding(query)
        if not query_embedding:
            return []
            
        try:
            facts_key = f"{username}/embeddings.json"
            facts_data = self.s3_service.get_json(self.data_bucket, facts_key, max_retries=4) or {}
            
            similarities = []
            for text, emb, meta in zip(
                facts_data.get('texts', []),
                facts_data.get('embeddings', []),
                facts_data.get('metadata', [])
            ):
                if not all([text, emb, meta]):
                    continue
                    
                if meta.get('type') == 'user_fact':
                    sim = 1 - cosine(query_embedding, emb)
                    if sim > 0.75:  # Reduced similarity threshold
                        similarities.append((sim, text, meta))
            
            return [
                {'text': text, 'metadata': meta}
                for _, text, meta in sorted(similarities, reverse=True)[:5]
            ]
            
        except Exception as e:
            logger.error(f"Error getting relevant facts: {e}")
            return []

    def requires_group(self, group):
        def decorator(f):
            def decorated_function(*args, **kwargs):
                user = g.user if g.user else {"groups": []}
                if group not in user.get("groups", []):
                    logger.warning(
                        f"Unauthorized access attempt by user: {user.get('email', 'unknown')} to group: {group}"
                    )
                    return {"error": "Unauthorized access"}, 403
                return f(*args, **kwargs)

            decorated_function.__name__ = f.__name__
            return decorated_function

        return decorator

    def get_blob_data(self):
        try:
            return self.s3_service.get_json(bucket=data_bucket, key=self.blob_filename)
        except Exception as e:
            logger.error(f"Failed to fetch blob data")
            logger.debug(f"Error details: {e}")
            return {"error": "Failed to fetch blob data"}

    def refresh_dashboard(self):
        if self.lambda_function:
            logger.info(f"Invoking lambda {self.lambda_function}")
            try:
                response = self.lambda_service.invoke_function(self.lambda_function, {})
                if isinstance(response, dict) and "error" in response:
                    return response

                time.sleep(5)

                self.data = {}
                self.last_updated = None
                fresh_data = self.get_dashboard(force_refresh=True)

                return {
                    "status": "refreshed",
                    "last_updated": self.last_updated,
                    "data": fresh_data,
                }
            except Exception as e:
                logger.error(f"Failed to refresh dashboard")
                logger.debug(f"Error details: {e}")
                return {"error": "An internal error occurred while refreshing the dashboard."}
        else:
            logger.error("No lambda function specified for refresh")
            return {"error": "No lambda function specified"}

    def get_dashboard(self, in_request_context=True):
        logger.info("Getting dashboard data")
        if in_request_context:
            user = (
                g.user
                if g.user
                else {"id": "anonymous", "name": "Unknown User", "email": "test@example.com"}
            )
        else:
            user = {"id": "system", "name": "System"}
        data = user
        data["last_updated"] = self.last_updated
        return data

    def get_dashboard_summary(self):
        return "No summary available for base Entmoot class"

    def handle_prompt(self, conversation_id, prompt, current_view, messages, dashboard_context):
        full_context = f"{dashboard_context}\n\nCurrent view: {current_view}"
        dashboard_summary = self.get_dashboard_summary()
        full_context += f"\n\nCurrent dashboard summary: {dashboard_summary}"

        # Get document context if we have a user
        document_context = []
        if conversation_id and hasattr(g, 'user') and g.user:
            document_context = self.get_document_context(prompt, conversation_id, g.user['email']) 

        response = self.chat.handle_conversation({
            "conversation_id": conversation_id,  
            "prompt": prompt,
            "messages": messages,
            "dashboard_context": full_context,
            "document_context": document_context  # Pass document context to chat
        })
        return response

class Chat:
    def __init__(self, system_prompt, model="claude-3-5-haiku-20241022"):
        self.system_prompt = system_prompt
        self.model = model
        api_key = get_or_throw("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=api_key)
        self.s3_service = S3Service()
        self.data_bucket = os.getenv("DATA_BUCKET")
        self.MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        self.ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.doc', '.docx', '.csv', '.json', '.js', '.py', '.html', '.css', '.md'}
        self.CHUNK_SIZE = 8000
        
    

    def get_chat_completion(self, messages, dashboard_context):
        try:
            full_system_prompt = f"{self.system_prompt}\n\n{dashboard_context}"
            filtered_messages = [msg for msg in messages if msg["role"] != "system"]
            logger.debug(f"Messages sent to AI in get_chat_completion: {filtered_messages}")
            
            # Add file analysis as a system message if it exists
            if "file_analysis" in dashboard_context:
                filtered_messages.insert(0, {
                    "role": "system",
                    "content": f"File analysis: {dashboard_context.split('Recently analyzed file:')[1]}"
                })
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0,
                system=full_system_prompt,
                messages=filtered_messages,
            )
            return "".join(block.text for block in response.content)
        except Exception as e:
            logger.error(f"Error in get_chat_completion: {str(e)}")
            raise

    def handle_conversation(self, data):
        """Handle conversation with enhanced context."""
        try:
            prompt = data.get("prompt")
            messages = data.get("messages", [])
            conversation_id = data.get("conversation_id")
            dashboard_context = data.get("dashboard_context", "")
            file_analysis = data.get("file_analysis")  # Keep file analysis support
            document_context = data.get("document_context", [])  # Add document context support

            # Clean up messages
            messages = [
                msg for msg in messages 
                if isinstance(msg, dict) 
                and msg.get("role") in ["user", "assistant"]
                and msg.get("content")
            ]

            # Build context parts
            context_parts = [dashboard_context]

            # Add document context if available 
            if document_context:
                context_parts.append("\nRelevant Document Sections:")
                for chunk in document_context:
                    context_parts.append(f"- {chunk['chunk'][:500]}...")

            # Add file analysis if available
            if file_analysis:
                context_parts.append(f"\nRecently analyzed file: {json.dumps(file_analysis, indent=2)}")

            context_parts.append(f"User query: {prompt}")

            # Get response with full context
            full_context = "\n\n".join(filter(None, context_parts))
            response_text = self.get_chat_completion(messages, full_context)
            messages.append({"role": "assistant", "content": response_text})

            return {
                "response": response_text,
                "conversation_id": conversation_id,
                "messages": messages,
                "file_analysis": file_analysis
            }

        except Exception as e:
            logger.error(f"Error in handle_conversation: {e}")
            return {"error": str(e)}

    @staticmethod
    def get_username_from_email(email):
        """Standardize username extraction."""
        if not email or email == "test@example.com":
            return "testuser"
        username = email.split("@")[0].lower()
        return "".join(c if c.isalnum() else "_" for c in username)

    def get_file_summary(self, file_name, user_email, conversation_id):
        """Get file analysis summary."""
        username = self.get_username_from_email(user_email)
        summary_file_name = f"{username}/{conversation_id}/uploads/{os.path.splitext(os.path.basename(file_name))[0]}_analysis.json"
        try:
            summary = self.s3_service.get_json(self.data_bucket, summary_file_name)
            return summary if summary else {
                "status": "error",
                "message": "No analysis available",
                "file_name": file_name
            }
        except Exception as e:
            logger.error(f"Error getting file summary: {e}")
            return {
                "status": "error",
                "message": "Failed to get file summary",
                "file_name": file_name
            }

    def generate_conversation_name(self, messages):
        """Generate a descriptive name for the conversation based on content."""
        try:
            # Get the first few messages to analyze
            relevant_messages = messages[:3]
            content = "\n".join(msg.get("content", "") for msg in relevant_messages if msg.get("role") == "user")
            
            if not content:
                return None
                
            # Use Claude to generate a name
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0,
                system="Generate a brief (2-5 words) title summarizing the topic of this conversation. Only respond with the title, nothing else.",
                messages=[{"role": "user", "content": content}]
            )
            
            name = "".join(block.text for block in response.content).strip()
            return name[:50] if name else None
        except Exception as e:
            logger.error(f"Error generating conversation name: {e}")
            return None

    def list_conversations(self, user_email):
        """List conversations with limit enforcement."""
        username = self.get_username_from_email(user_email)
        prefix = f"{username}/"
        try:
            # Get all conversations first
            conversations = self.s3_service.list_conversations(self.data_bucket, prefix)
            
            # Sort by last modified date (newest first) and limit to 10
            sorted_conversations = sorted(
                conversations,
                key=lambda x: x.get('last_modified', ''),
                reverse=True
            )
            return sorted_conversations[:10]  # Enforce 10 conversation limit
        except Exception as e:
            logger.error(f"Error listing conversations")
            logger.debug(f"Error details: {e}")
            return []

    def save_conversation(self, conversation_id, messages, user_email):
        """Save conversation with limit check and automatic naming."""
        if not conversation_id or not messages:
            return {"error": "Missing required data"}
            
        username = self.get_username_from_email(user_email)
        key = f"{username}/{conversation_id}/messages.json"
        
        # Check if this is a new conversation
        try:
            existing = self.s3_service.head_object(self.data_bucket, key)
            is_new = existing is None
        except Exception:
            is_new = True
            
        if is_new:
            # Count existing conversations
            existing_conversations = self.list_conversations(user_email)
            if len(existing_conversations) >= 10:
                return {
                    "error": "Maximum limit of 10 conversations reached. Please delete some conversations before creating new ones."
                }
        
        try:
            # Validate messages
            if not all(isinstance(msg, dict) and 'role' in msg and 'content' in msg 
                    for msg in messages):
                raise ValueError("Invalid message format")

            # Save messages
            save_result = self.s3_service.upload_json(self.data_bucket, key, messages)
            if not save_result:
                return {"error": "Failed to save conversation"}
            
            # Get existing tags
            existing_tags = self.s3_service.get_object_tags(self.data_bucket, key)
            
            # Only generate name if one doesn't exist or was auto-generated
            if not existing_tags.get('name') or existing_tags.get('auto_named') == 'true':
                # Generate name
                generated_name = self.generate_conversation_name(messages)
                if generated_name:
                    # Update tags with new name
                    tags = {
                        **existing_tags,
                        'name': generated_name,
                        'last_modified': datetime.utcnow().isoformat(),
                        'auto_named': 'true'
                    }
                    logger.info(f"Auto-generated conversation name: {generated_name}")
                    logger.info(f"Tags: {tags}")
                    self.s3_service.put_object_tags(self.data_bucket, key, tags)
                    return {"status": "success", "name": generated_name}
                    
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
            return {"error": str(e)}

    def generate_upload_url(self, file_extension, user_email, conversation_id, original_filename):
        """Generate presigned URL for file upload."""
        try:
            username = self.get_username_from_email(user_email)
            unique_id = str(uuid.uuid4())
            file_name = f"{username}/{conversation_id}/uploads/{unique_id}{file_extension}"
            
            self.validate_file(0, file_extension)
            presigned_post = self.s3_service.generate_presigned_url(
                self.data_bucket,
                file_name,
                username,
                conversation_id,
                file_extension,
                original_filename
            )
            return {
                "presigned_post": presigned_post,
                "file_name": file_name,
                "conversation_id": conversation_id
            }
        except Exception as e:
            logger.error(f"Failed to generate upload URL: {e}")
            return {"error": f"Failed to generate upload URL"}

    def validate_file(self, file_size, file_extension):
        """Validate file size and type."""
        if file_size > self.MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds maximum allowed size of {self.MAX_FILE_SIZE/1024/1024}MB")
        if not any(file_extension.lower().endswith(ext) for ext in self.ALLOWED_EXTENSIONS):
            raise ValueError(f"Unsupported file type: {file_extension}")

    def delete_conversation(self, conversation_id, user_email):
        """Delete conversation and related files."""
        try:
            username = self.get_username_from_email(user_email)
            prefix = f"{username}/{conversation_id}/"
            
            response = self.s3_service.list_objects_v2(
                Bucket=self.data_bucket,
                Prefix=prefix
            )
            
            for obj in response.get('Contents', []):
                try:
                    self.s3_service.delete_object(
                        self.data_bucket,
                        obj['Key']
                    )
                except Exception as e:
                    logger.error(f"Error deleting object {obj['Key']}: {e}")
                    return {"error": "Failed to delete some conversation files"}
                    
            return {"status": "success", "message": "Conversation deleted successfully"}
        except Exception as e:
            logger.error(f"Error deleting conversation: {e}")
            return {"error": "Failed to delete conversation"}

    def delete_upload(self, conversation_id, upload_key, user_email):
        """Delete upload file and analysis."""
        try:
            username = self.get_username_from_email(user_email)
            
            if not upload_key.startswith(f"{username}/{conversation_id}/uploads/"):
                return {"error": "Unauthorized access to file"}
            
            try:
                self.s3_service.delete_object(
                    self.data_bucket,
                    upload_key
                )
                
                # Delete associated analysis file
                analysis_key = upload_key.rsplit('.', 1)[0] + '_analysis.json'
                self.s3_service.delete_object(
                    self.data_bucket,
                    analysis_key
                )
                
                return {"status": "success", "message": "Upload deleted successfully"}
            except Exception as e:
                logger.error(f"Error deleting upload {upload_key}: {e}")
                return {"error": "Failed to delete upload"}
                
        except Exception as e:
            logger.error(f"Error in delete_upload: {e}")
            return {"error": "Failed to process delete request"}
        
    def load_existing_analysis(self, conversation_id, user_email):
        username = self.get_username_from_email(user_email)
        analysis_key_prefix = f"{username}/{conversation_id}/uploads/"
        try:
            response = self.s3_service.list_objects_v2(
                Bucket=self.data_bucket, Prefix=analysis_key_prefix
            )
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    if key.endswith('_analysis.json'):
                        analysis = self.s3_service.get_json(self.data_bucket, key)
                        return analysis
            return None
        except Exception as e:
            logger.error(f"Error loading existing analysis for conversation {conversation_id}: {e}")
            return None

    def get_conversation(self, conversation_id, user_email):
        """Retrieve conversation with validation."""
        username = self.get_username_from_email(user_email)
        messages_key = f"{username}/{conversation_id}/messages.json"

        try:
            messages = self.s3_service.get_json(self.data_bucket, messages_key)
            if not messages or "error" in messages:
                return {"error": "Conversation not found"}

            # Get current analysis if it exists
            file_analysis = self._get_current_analysis(username, conversation_id)
            
            return {
                "messages": messages,
                "file_analysis": file_analysis
            }
        except Exception as e:
            logger.error(f"Error retrieving conversation: {e}")
            return {"error": "Failed to retrieve conversation"}

    def _get_current_analysis(self, username: str, conversation_id: str) -> Optional[Dict]:
        """Get current file analysis for conversation if it exists."""
        try:
            analysis_prefix = f"{username}/{conversation_id}/uploads/"
            response = self.s3_service.list_objects_v2(
                Bucket=self.data_bucket, 
                Prefix=analysis_prefix
            )
            
            for obj in response.get('Contents', []):
                if obj['Key'].endswith('_analysis.json'):
                    analysis = self.s3_service.get_json(
                        self.data_bucket,
                        obj['Key']
                    )
                    if analysis:
                        return analysis
            return None
        except Exception as e:
            logger.error(f"Error getting analysis: {e}")
            return None

    def update_conversation_name(self, conversation_id, name, user_email):
        """Update conversation name via tags."""
        try:
            if not name or not name.strip():
                return {"error": "Name cannot be empty"}
                
            username = self.get_username_from_email(user_email)
            messages_key = f"{username}/{conversation_id}/messages.json"
            
            try:
                self.s3_service.head_object(
                    self.data_bucket,
                    messages_key
                )
            except Exception:
                return {"error": "Conversation not found"}
            
            tags = {
                'name': name.strip(),
                'last_modified': datetime.utcnow().isoformat(),
                'auto_named': 'false'
            }
            
            success = self.s3_service.put_object_tags(self.data_bucket, messages_key, tags)
            if not success:
                return {"error": "Failed to update conversation name"}
                
            return {"status": "success", "name": name.strip()}
        except Exception as e:
            logger.error(f"Error updating conversation name: {str(e)}")
            return {"error": f"Failed to update conversation name: {str(e)}"}