import logging
import time
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, g
from flask_restful import Api, Resource
import json
from app.server.models import Chat, Entmoot
from app.server.services.devision import Devision
from app.server.services.env_config import EnvConfig
from app.server.services.lucius import Lucius

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

normalness_suffix = """Remember to keep your responses natural and conversational:
- Use contractions and casual language
- Be brief and direct
- Skip unnecessary formalities 
- Talk like a helpful colleague
- Use simple words over complex ones
- Show personality while staying professional
- Skip phrases like "I'd be happy to..." or "Let me assist you with..."
- Get straight to the point"""

# Initialize the chat instance with a generic system prompt
chat_instance = Chat(
    system_prompt = """You are Treebeard, the AI chatbot assistant for Apprentice.io's internal CRM and Support Automation site.
    You have access to multiple dashboards called Entmoots that provide real-time information about different aspects of the system.
    You also maintain understanding of user preferences and work patterns to provide more personalized assistance.
    When given context about the user or files, incorporate that information naturally into your responses.""" + normalness_suffix)

# Initialize Entmoots
env_config_instance = EnvConfig(chat=chat_instance)
devision_instance = Devision(chat=chat_instance)
lucius_instance = Lucius(chat=chat_instance)

class Treebeard(Entmoot):
    def __init__(self, chat):
        super().__init__(blob_filename=None, tasks=["upload"], chat=chat)
        self.dashboards = ["env_config", "devision", "lucius"]
        self.cached_summaries = None
        self.last_summary_update = None
        self.cache_duration = timedelta(minutes=15)
        self.dashboard_context = (
            f"User is on the home page; The available Entmoots are {', '.join(self.dashboards)}."
            " There is a Beta Feature For uploading files for analysis and saving/loading conversations. "
        )

    def get_conversation(self, conversation_id, user_email):
        try:
            messages = self.chat.get_conversation(conversation_id, user_email)
            if "error" in messages:
                logger.error(f"Error retrieving conversation {conversation_id}: {messages['error']}")
                return {"error": "Failed to retrieve conversation"}
            return messages
        except Exception as e:
            logger.error(f"Error in get_conversation: {str(e)}")
            return {"error": "An error occurred while retrieving the conversation"}

    def get_entmoots(self, force_refresh=False):
        current_time = datetime.now()
        if (
            self.cached_summaries is None
            or self.last_summary_update is None
            or (current_time - self.last_summary_update) > self.cache_duration
            or force_refresh
        ):
            logger.info("Fetching fresh summaries for all entmoots")
            summaries = {
                "env_config": env_config_instance.get_dashboard_summary(),
                "devision": devision_instance.get_dashboard_summary(),
                "lucius": lucius_instance.get_dashboard_summary(),
            }
            self.cached_summaries = summaries
            self.last_summary_update = current_time
            logger.info(f"entmoot summaries updated successfuly")
        else:
            logger.info("Using cached entmoot summaries")

        return {
            "apps": self.cached_summaries,
            "last_updated": self.last_summary_update.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "ok",
        }

    def get_dashboard(self, in_request_context=True):
        logger.info("Getting Treebeard's dashboard")
        if in_request_context:
            user = (
                g.user
                if g.user
                else {
                    "id": "anonymous",
                    "name": "Unknown User",
                    "email": "test_user@example.com",
                }
            )
        else:
            user = {"id": "system", "name": "System", "email": "test_user@example.com"}

        conversations = self.chat.list_conversations(user["email"])
        data = {
            "conversations": conversations,
            "user": {
                "name": user["name"],
                "email": user["email"],
            },
            "status": "success",
        }
        return data
    
    def get_dashboard_summary(self):
        return self.get_entmoots()
    
    def refresh_dashboard(self):
        self.get_entmoots(force_refresh=True)
        self.get_dashboard(in_request_context=False)

treebeard_instance = Treebeard(chat=chat_instance)

class DashResource(Resource):
    def get(self):
        user_email = g.user["email"] if g.user else "test@example.com"
        action = request.args.get("action")
        dashboard_id = request.args.get("dashboard_id")
        logger.info(
            f"Received request for dashboard: {dashboard_id} with action: {action}"
        )

        instance = self.get_instance_by_dashboard_id(dashboard_id)
        if not instance:
            return jsonify({"error": "Invalid dashboard ID"}), 400

        try:
            if action == "refresh":
                return instance.refresh_dashboard()
            else:
                data = instance.get_dashboard()
        except Exception as e:
            logger.error(f"Error in get dashboard: {str(e)}")
            return {"error": "An internal error occurred"}, 500
        logger.info(f"Dashboard request successful for {dashboard_id}")
        return jsonify(data)

    @staticmethod
    def get_instance_by_dashboard_id(dashboard_id):
        if dashboard_id == "env_config":
            return env_config_instance
        elif dashboard_id == "devision":
            return devision_instance
        elif dashboard_id == "lucius":
            return lucius_instance
        elif dashboard_id in ["treebeard", "null"]:
            return treebeard_instance
        else:
            return None

class ChatResource(Resource):
    def get_entmoot_instance(self, dashboard_id):
        return DashResource.get_instance_by_dashboard_id(dashboard_id)

    def get(self):
        user_email = g.user["email"] if g.user else "test@example.com"
        dashboard_id = request.args.get("dashboard_id", "treebeard")
        action = request.args.get("action")
        conversation_id = request.args.get("conversation_id")

        instance = self.get_entmoot_instance(dashboard_id)
        if not instance:
            return {"error": "Invalid dashboard ID"}, 400

        try:
            if action == "get_conversation":
                if not conversation_id:
                    return {"error": "conversation_id is required"}, 400
                messages = instance.get_conversation(conversation_id, user_email)
                if "error" in messages:
                    return messages, 404
                return {"conversation_id": conversation_id, "messages": messages}
            else:
                return {"error": "Invalid action"}, 400
        except Exception as e:
            logger.error(f"Error in ChatResource GET: {str(e)}")
            return {"error": "An internal error occurred"}, 500

    def post(self):
        try:
            user = g.user if g.user else {
                "id": "testing",
                "name": "Test User",
                "email": "test@example.com",
                "groups": []
            }
            data = request.json or {}
            action = data.get("action", "chat")
            dashboard_id = data.get("dashboard_id", "treebeard")

            instance = self.get_entmoot_instance(dashboard_id)
            if not instance:
                return {"error": "Invalid dashboard ID"}, 400

            handlers = {
                "get_upload_url": self.handle_get_upload_url,
                "chat": self.handle_chat,
                "save": self.handle_save,
                "delete_conversation": self.handle_delete_conversation,
                "delete_upload": self.handle_delete_upload,
                "update_name": self.handle_update_name
            }

            handler = handlers.get(action)
            if not handler:
                return {"error": "Invalid action"}, 400

            return handler(instance, data, user)
        except Exception as e:
            logger.error(f"Error in ChatResource: {str(e)}")
            return {"error": "An unexpected error occurred"}, 500

    def handle_chat(self, instance, data, user):
        try:
            prompt = data.get("prompt", "")
            conversation_id = data.get("conversation_id")
            messages = list({
                msg['content']: msg 
                for msg in data.get("messages", [])
                if isinstance(msg, dict) and msg.get("content")
            }.values())
            file_name = data.get("file_name")

            # Handle case where there's no explicit prompt but there is a file
            if not prompt and file_name:
                prompt = "Please analyze the uploaded file."

            if not prompt and not file_name:
                return {"error": "No prompt or file name provided"}, 400

            is_new_conversation = not conversation_id
            if is_new_conversation:
                conversation_id = f'conv-{datetime.now().strftime("%Y%m%d%H%M%S")}'

            # Build context parts
            context_parts = []
            file_analysis = None

            # Handle file analysis first
            if file_name:
                file_analysis = instance.chat.get_file_summary(
                    file_name, user["email"], conversation_id
                )
                if isinstance(file_analysis, dict) and "error" in file_analysis:
                    return file_analysis, 500
            else:
                file_analysis = instance.chat.load_existing_analysis(
                    conversation_id, user["email"]
                )

            # Add user context
            user_context = f"User: {user['name']} (Email: {user['email']}, Groups: {', '.join(user.get('groups', []))}"
            context_parts.append(user_context)

            # Add dashboard context and summary
            context_parts.append(instance.dashboard_context)
            summary = instance.get_dashboard_summary()
            if summary:
                context_parts.append(f"\nDashboard Status: {json.dumps(summary)}")

            # Add file analysis context
            if file_analysis:
                context_parts.append(f"A file has been uploaded and analyzed. Here are the analysis results:\n{json.dumps(file_analysis, indent=2)}\n\nPlease discuss these analysis results in your response.")

            # NEW: Add environment-specific context if instance is EnvConfig
            if isinstance(instance, EnvConfig) and instance.openai_client:
                relevant_envs = instance.get_relevant_environments(prompt)
                if relevant_envs:
                    env_context = "\nRelevant Environments:\n" + json.dumps(relevant_envs, indent=2)
                    context_parts.append(env_context)
                    
                    # Add smart suggestions based on found environments
                    suggestions = []
                    for env in relevant_envs:
                        if env.get('health') == 'error':
                            suggestions.append(f"Environment {env['name']} is currently unhealthy")
                        if env.get('type') == 'cluster':
                            suggestions.append(f"Note: {env['name']} is a cluster environment")
                        if env.get('customer'):
                            suggestions.append(f"{env['name']} belongs to customer {env['customer']}")
                    
                    if suggestions:
                        context_parts.append("\nSuggested Points:\n- " + "\n- ".join(suggestions))

            

            # Get relevant user facts if available (existing code)
            if instance.openai_client:
                facts = instance.get_relevant_facts(
                    prompt, 
                    instance.chat.get_username_from_email(user['email'])
                )
                if facts:
                    facts_context = "\nRelevant User Context:\n" + "\n".join(
                        f"- {fact['text']}" for fact in facts
                    )
                    context_parts.append(facts_context)

            # Combine context and get response
            full_context = "\n\n".join(filter(None, context_parts))
            logger.debug(f"Full context in handle_conversation: {full_context}")
            
            response = instance.chat.handle_conversation({
                "conversation_id": conversation_id,
                "prompt": prompt,
                "messages": messages,
                "dashboard_context": full_context,
                "file_analysis": file_analysis
            })

            # Ensure the response includes all necessary components
            complete_response = {
                "conversation_id": conversation_id,
                "messages": response.get("messages", messages),
                "response": response.get("response", ""),
                "file_analysis": file_analysis if file_analysis else None
            }

            if is_new_conversation:
                logger.info(f"Created new chat for {user['name']}: {conversation_id}")

            return jsonify(complete_response)

        except Exception as e:
            logger.error(f"Error in handle_chat: {e}")
            return {"error": "An error occurred while processing the chat"}, 500

        except Exception as e:
            logger.error(f"Error in handle_chat: {e}")
            return {"error": "An error occurred while processing the chat"}, 500

    def handle_save(self, instance, data, user):
        """Handle conversation save with automatic naming."""
        conversation_id = data.get("conversation_id")
        messages = data.get("messages", [])
        user_email = user["email"]

        if not conversation_id or not messages:
            return {"error": "conversation_id and messages are required"}, 400
            
        try:
            # Save conversation messages
            result = instance.chat.save_conversation(
                conversation_id, messages, user_email
            )
            
            if "error" in result:
                # Check specifically for the conversation limit error
                if "Maximum limit" in result["error"]:
                    return {"error": result["error"]}, 409  # HTTP 409 Conflict
                return result, 500
                
            # Return name if one was generated
            response = {"status": "success", "message": "Conversation saved"}
            if "name" in result:
                response["name"] = result["name"]
                
            return response
                
        except Exception as e:
            logger.error(f"Error in handle_save: {e}")
            return {"error": str(e)}, 500

    def handle_get_upload_url(self, instance, data, user):
        file_extension = data.get("file_extension", "txt")
        conversation_id = data.get("conversation_id")
        original_filename = data.get("original_filename", "unknown")
        if not conversation_id:
            conversation_id = f'conv-{datetime.now().strftime("%Y%m%d%H%M%S")}'
            logger.info(
                f"User {user['name']} Created New Chat Via upload; conversation ID generated: {conversation_id}"
            )
        upload_data = instance.chat.generate_upload_url(
            file_extension, user["email"], conversation_id, original_filename
        )
        return jsonify(upload_data)

    def handle_delete_conversation(self, instance, data, user):
        conversation_id = data.get("conversation_id")
        if not conversation_id:
            return {"error": "conversation_id is required"}, 400
            
        result = instance.chat.delete_conversation(conversation_id, user["email"])
        if "error" in result:
            return result, 500
        return {"status": "success", "message": "Conversation deleted"}

    def handle_delete_upload(self, instance, data, user):
        conversation_id = data.get("conversation_id")
        upload_key = data.get("upload_key")
        
        if not conversation_id or not upload_key:
            return {"error": "conversation_id and upload_key are required"}, 400
            
        result = instance.chat.delete_upload(conversation_id, upload_key, user["email"])
        if "error" in result:
            return result, 500
        return {"status": "success", "message": "Upload deleted"}

    def handle_update_name(self, instance, data, user):
        conversation_id = data.get("conversation_id")
        name = data.get("name")
        user_email = user["email"]
        
        if not conversation_id or not name:
            return {"error": "conversation_id and name are required"}, 400
            
        result = instance.chat.update_conversation_name(conversation_id, name, user_email)
        if "error" in result:
            return result, 500
        return {"status": "success", "name": name}

api_bp = Blueprint("api_bp", __name__)
api = Api(api_bp)
api.add_resource(DashResource, "/dash")
api.add_resource(ChatResource, "/chat")