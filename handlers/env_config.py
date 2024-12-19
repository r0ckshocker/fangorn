import os
import json
import requests
import logging
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from openai import OpenAI
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS S3 client
s3_client = boto3.client('s3')

def init_openai_client() -> Optional[OpenAI]:
    """Safely initialize OpenAI client."""
    try:
        if api_key := os.environ.get("OPENAI_API_KEY"):
            return OpenAI(api_key=api_key)
        return None
    except Exception as e:
        logger.error(f"Error initializing OpenAI client: {e}")
        return None

def get_github_content(github_token: str, repo_owner: str, repo_name: str, file_path: str) -> bytes:
    """Fetch content from GitHub repository."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{file_path}"
    headers = {
        "Accept": "application/vnd.github.raw+json",
        "Authorization": f"Bearer {github_token}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching {file_path} from GitHub: {e}")
        raise

def get_account_name(assume_role: str, accounts: Dict) -> Optional[str]:
    """Look up the account name based on assume_role in accounts.json."""
    try:
        for account_name, account_data in accounts.items():
            if account_data.get("assume_role") == assume_role:
                return account_name
        return None
    except Exception as e:
        logger.error(f"Error getting account name: {e}")
        return None

def get_mongo_project(mongo_env: str, mongo_data: Dict) -> Optional[str]:
    """Look up the mongo_project based on mongo_env in mongo.json."""
    try:
        if mongo_env in mongo_data:
            return mongo_data[mongo_env].get("project")
        return None
    except Exception as e:
        logger.error(f"Error getting mongo project: {e}")
        return None

def get_project_uri(project_name: str, project_data: List[Dict]) -> Optional[str]:
    """Look up the project URI based on project_name in project_data."""
    try:
        for project in project_data:
            if project["name"] == project_name:
                return project["uri"]
        return None
    except Exception as e:
        logger.error(f"Error getting project URI: {e}")
        return None

def get_environment_embeddings(env_name: str, env_data: Dict) -> Tuple[Optional[str], Optional[Dict]]:
    """Generate searchable text and embeddings for environment."""
    try:
        # Generate searchable text representation
        sections = []
        
        # Core environment information
        core_info = {
            "Environment": env_name,
            "Type": env_data.get('type', 'unknown'),
            "Customer": env_data.get('customer', 'unknown'),
            "Level": env_data.get('env_level', 'unknown')
        }
        sections.extend(f"{k}: {v}" for k, v in core_info.items())
        
        # Process lists with validation
        list_sections = {
            "Active Projects": env_data.get("projects", []),
            "Vanity URLs": env_data.get("vanity_urls", []),
            "Active Regions": env_data.get("regions", [])
        }
        
        for section_name, items in list_sections.items():
            if items and isinstance(items, list):
                sections.append(f"\n{section_name}:")
                sections.extend(f"- {item}" for item in items)

        # MongoDB information
        mongo_info = {
            "MongoDB Project": env_data.get("mongo_project"),
            "MongoDB Environment": env_data.get("mongo_env")
        }
        sections.extend(f"{k}: {v}" for k, v in mongo_info.items() if v)

        # Configuration section with safety checks
        if configs := env_data.get("configs", {}):
            sections.append("\nConfiguration:")
            for key, value in configs.items():
                if isinstance(value, (str, int, bool)):
                    sections.append(f"- {key}: {value}")

        searchable_text = "\n".join(sections)

        # Generate metadata with validation
        metadata = {
            "name": env_name,
            "type": env_data.get("type", "unknown"),
            "customer": env_data.get("customer", "unknown"),
            "env_level": env_data.get("env_level", "unknown"),
            "cluster": env_data.get("cluster", "none"),
            "topics": [],
            "timestamp": datetime.utcnow().isoformat()
        }

        # Build topics with validation
        topics = []
        if metadata["type"] != "unknown":
            topics.append(f"{metadata['type']}_environment")
        if metadata["customer"] != "unknown":
            topics.append(f"customer_{metadata['customer']}")
        if isinstance(env_data.get("projects"), list):
            topics.extend(f"project_{p}" for p in env_data["projects"])
        if env_data.get("vanity_urls"):
            topics.append("vanity_enabled")
            
        metadata["topics"] = topics

        return searchable_text, metadata

    except Exception as e:
        logger.error(f"Error generating environment embeddings for {env_name}: {e}")
        return None, None

def safe_update_embeddings(bucket: str, environments: Dict) -> bool:
    """Safely update environment embeddings file."""
    try:
        # Early return if OpenAI is not configured
        openai_client = init_openai_client()
        if not openai_client:
            logger.info("OpenAI client not configured, skipping embeddings update")
            return True

        # Generate text and metadata for all environments
        env_data = []
        for env_name, env_info in environments.items():
            result = get_environment_embeddings(env_name, env_info)
            if result is not None:
                text, metadata = result
                if text and metadata:  # Additional validation
                    env_data.append((text, metadata))

        if not env_data:
            logger.warning("No valid environment data for embeddings")
            return True

        # Get embeddings with retry
        max_retries = 3
        embeddings = None
        for attempt in range(max_retries):
            try:
                response = openai_client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=[item[0] for item in env_data]
                )
                embeddings = [item.embedding for item in response.data]
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to generate embeddings after {max_retries} attempts: {e}")
                    return False
                logger.warning(f"Embedding generation attempt {attempt + 1} failed: {e}")
                continue

        if not embeddings:
            return False

        # Create embeddings file content
        embeddings_data = {
            "texts": [item[0] for item in env_data],
            "embeddings": embeddings,
            "metadata": [item[1] for item in env_data],
            "updated_at": datetime.utcnow().isoformat()
        }

        # Store embeddings file with retry
        for attempt in range(max_retries):
            try:
                s3_client.put_object(
                    Bucket=bucket,
                    Key="env_config/env_config_embeddings.json",
                    Body=json.dumps(embeddings_data),
                    ContentType="application/json"
                )
                logger.info(f"Updated embeddings for {len(env_data)} environments")
                return True
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to store embeddings after {max_retries} attempts: {e}")
                    return False
                continue

        return False

    except Exception as e:
        logger.error(f"Error in embeddings update process: {e}")
        return False

def classify_environment(env_name: str, env_data: Dict, accounts: Dict, mongo_data: Dict) -> Dict:
    """Classify and enrich environment data."""
    try:
        # Determine the environment type based on the presence of specific projects
        env_type = "cluster"
        
        if "projects" in env_data:
            if env_data.get("tags", {}).get("is_verify_env"):
                env_type = "verify"
            elif "auth-api" in env_data["projects"]:
                env_type = "shared"
            elif "enterprise-api" in env_data["projects"]:
                env_type = "enterprise"
            elif "main-api" in env_data["projects"]:
                env_type = "app"

        # Look up account_name and mongo_project
        account_name = get_account_name(env_data.get("assume_role"), accounts)
        mongo_project = get_mongo_project(env_data.get("mongo_env"), mongo_data)

        # Build classified environment structure
        classified_env = {
            "name": env_name,
            "type": env_type,
            "env_level": env_data.get("env_level"),
            "shared_env": "self" if env_type == "shared" else env_data.get("shared_env"),
            "enterprise_env": "self" if env_type == "enterprise" else env_data.get("enterprise_env"),
            "customer": env_data.get("customer"),
            "account_name": account_name,
            "mongo_project": mongo_project,
            "mongo_env": env_data.get("mongo_env"),
            "cluster": "self" if env_type == "cluster" else env_data.get("cluster"),
            "vanity_urls": env_data.get("vanity_urls"),
            "regions": env_data.get("regions"),
            "projects": env_data.get("projects"),
            "tags": env_data.get("tags"),
            "branch": env_data.get("branch"),
            "health_check_uri": None,
            "configs": {}
        }

        # Set health_check_uri based on environment type
        if env_type == "app":
            classified_env["health_check_uri"] = "api"
        elif env_type == "shared":
            classified_env["health_check_uri"] = "auth"
        elif env_type == "enterprise":
            classified_env["health_check_uri"] = "api"

        # Move remaining configurations to configs section
        top_level_keys = set(classified_env.keys()).union({"assume_role"})
        classified_env["configs"] = {k: v for k, v in env_data.items() if k not in top_level_keys}
        classified_env["configs"]["assume_role"] = env_data.get("assume_role")

        return classified_env

    except Exception as e:
        logger.error(f"Error classifying environment {env_name}: {e}")
        # Return a minimal valid environment to prevent complete failure
        return {
            "name": env_name,
            "type": "unknown",
            "error": str(e)
        }

def handler(event, context):
    """Lambda handler with enhanced error handling and isolation."""
    start_time = datetime.now()
    status = {
        "environments_processed": False,
        "embeddings_updated": False,
        "error": None
    }

    try:
        # Get environment variables with validation
        required_vars = ["GITHUB_TOKEN", "REPO_OWNER", "REPO_NAME", "DATA_BUCKET"]
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

        github_token = os.environ["GITHUB_TOKEN"]
        repo_owner = os.environ["REPO_OWNER"]
        repo_name = os.environ["REPO_NAME"]
        data_bucket = os.environ["DATA_BUCKET"]
        
        # Core environment processing
        try:
            # Fetch and process required files
            required_files = {
                "env.json": None,
                "account.json": None,
                "mongo.json": None,
                "project.json": None
            }
            
            for file_name in required_files:
                content = get_github_content(github_token, repo_owner, repo_name, file_name)
                required_files[file_name] = json.loads(content)
                
                # Store raw file
                s3_client.put_object(
                    Bucket=data_bucket,
                    Key=f"env_config/raw/{file_name}",
                    Body=content,
                    ContentType="application/json"
                )
                logger.info(f"Stored raw {file_name}")

            # Process environments
            environments = required_files["env.json"]
            classified_environments = {
                env_name: classify_environment(
                    env_name, 
                    env_data, 
                    required_files["account.json"],
                    required_files["mongo.json"]
                )
                for env_name, env_data in environments.items()
            }

            # Store main configuration
            s3_client.put_object(
                Bucket=data_bucket,
                Key="env_config/env_config.json",
                Body=json.dumps(classified_environments, indent=2),
                ContentType="application/json"
            )
            status["environments_processed"] = True
            logger.info("Successfully processed and stored environment configurations")

            # Update embeddings as a separate operation
            status["embeddings_updated"] = safe_update_embeddings(data_bucket, classified_environments)

        except Exception as e:
            status["error"] = str(e)
            logger.error(f"Error in core processing: {e}")
            # Don't raise here - we want to return a proper response

        # Prepare response
        execution_time = (datetime.now() - start_time).total_seconds()
        response_body = {
            "message": "Environment processing completed",
            "environments_processed": status["environments_processed"],
            "embeddings_updated": status["embeddings_updated"],
            "execution_time": execution_time
        }
        
        if status["error"]:
            response_body["error"] = status["error"]

        # Return success if core processing worked, even if embeddings failed
        return {
            "statusCode": 200 if status["environments_processed"] else 500,
            "body": json.dumps(response_body)
        }

    except Exception as e:
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"Critical error in handler: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Critical error in environment processing",
                "details": str(e),
                "execution_time": execution_time
            })
        }

if __name__ == "__main__":
    handler(None, None)