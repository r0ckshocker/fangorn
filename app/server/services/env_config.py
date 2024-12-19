import os
import json
import requests
import asyncio
from app.server.services.helper.actions import LambdaService
from app.server.models import Entmoot
from requests.exceptions import SSLError, ConnectionError, Timeout, HTTPError
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnvConfig(Entmoot):
    def __init__(self, chat):
        super().__init__(
            blob_filename="env_config/env_config.json",
            chat=chat,
            lambda_function=os.getenv("ENV_JSON_LAMBDA")
        )
        # Initialize core data structure
        self.data = {
            "apps": {},
            "stats": {
                "clusters": {},
                "mongo": {
                    "projects": {},
                    "envs": {}
                },
                "env_types": {},
                "env_levels": {},
                "health": {
                    "healthy": 0,
                    "unhealthy": 0,
                    "total": 0,
                    "na": 0
                }
            },
            "updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        self.lambda_service = LambdaService()
        self.dashboard_context = (
            "User is on the EnvConfig page. EnvConfig Entmoot displays configuration info and healthz responses "
            "of all Tempo Environments with filtering capabilities. Data is pulled from env_config.json, which feeds "
            "into deployment pipelines and terraform workspaces inputs. This dashboard is crucial for monitoring "
            "the health and configuration of various environments."
        )
        self.initialized = False
        self.SIMILARITY_THRESHOLD = 0.75  # Lower threshold for environment matches

    def get_relevant_environments(self, query: str) -> List[Dict]:
        """Get relevant environments based on query similarity."""
        if not self.openai_client:
            return []
            
        query_embedding = self.get_embedding(query)
        if not query_embedding:
            return []
            
        try:
            # Fetch environment embeddings
            embeddings_data = self.s3_service.get_json(
                self.data_bucket, 
                "env_config/env_config_embeddings.json"
            ) or {}
            
            if not embeddings_data:
                return []

            # Calculate similarities and gather relevant info
            similarities = []
            current_data = self.get_dashboard() if self.initialized else self.get_blob_data()
            
            for text, emb, meta in zip(
                embeddings_data.get('texts', []),
                embeddings_data.get('embeddings', []),
                embeddings_data.get('metadata', [])
            ):
                if not all([text, emb, meta]):
                    continue
                
                sim = self.calculate_similarity(query_embedding, emb)
                if sim > self.SIMILARITY_THRESHOLD:
                    env_name = meta.get('name')
                    current_env_data = None
                    
                    # Try to get the most up-to-date data
                    if isinstance(current_data, dict):
                        if 'apps' in current_data:
                            current_env_data = current_data['apps'].get(env_name)
                        else:
                            current_env_data = current_data.get(env_name)
                    
                    if current_env_data:
                        similarities.append((
                            sim,
                            {
                                'name': env_name,
                                'description': text,
                                'health': current_env_data.get('healthz', 'unknown'),
                                'type': meta.get('type', 'unknown'),
                                'customer': meta.get('customer', 'unknown'),
                                'projects': meta.get('topics', []),
                                'details': current_env_data
                            }
                        ))
            
            # Return top matches
            return [
                item[1] for item in 
                sorted(similarities, key=lambda x: x[0], reverse=True)[:5]
            ]
            
        except Exception as e:
            logger.error(f"Error getting relevant environments: {e}")
            return []

    def calculate_stats(self, env_data):
        """Calculate statistics from environment data"""
        stats = {
            "clusters": defaultdict(int),
            "mongo": {
                "projects": defaultdict(int),
                "envs": defaultdict(int)
            },
            "env_types": defaultdict(int),
            "env_levels": defaultdict(int),
            "customers": defaultdict(int),
            "health": {
                "healthy": 0,
                "unhealthy": 0,
                "total": 0,
                "na": 0
            }
        }

        try:
            total_vanity_urls = 0
            for app_name, app_data in env_data.items():
                if not isinstance(app_data, dict):
                    continue

                # Count vanity URLs first
                if vanity_urls := app_data.get("vanity_urls"):
                    if isinstance(vanity_urls, list):
                        total_vanity_urls += len(vanity_urls)

                # Only continue with other stats if it's a typed environment
                if env_type := app_data.get("type"):
                    stats["env_types"][env_type] += 1
                    
                    # Count cluster
                    cluster = app_data.get("cluster")
                    if cluster:
                        cluster_name = cluster if cluster != "self" else app_name
                        stats["clusters"][cluster_name] += 1

                    # Count environment level
                    if env_level := app_data.get("env_level"):
                        stats["env_levels"][env_level] += 1

                    # Count customer
                    if customer := app_data.get("customer", "Unknown"):
                        stats["customers"][customer] += 1

                    # Count MongoDB info
                    if mongo_project := app_data.get("mongo_project"):
                        stats["mongo"]["projects"][mongo_project] += 1
                    if mongo_env := app_data.get("mongo_env"):
                        stats["mongo"]["envs"][mongo_env] += 1

                    # Count cluster environments separately
                    if env_type == "cluster":
                        stats["health"]["na"] += 1

            return {
                "clusters": dict(stats["clusters"]),
                "mongo": {
                    "projects": dict(stats["mongo"]["projects"]),
                    "envs": dict(stats["mongo"]["envs"])
                },
                "env_types": dict(stats["env_types"]),
                "env_levels": dict(stats["env_levels"]),
                "customers": dict(stats["customers"]),
                "health": stats["health"],
                "total_vanity_urls": total_vanity_urls
            }

        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")
            return {
                "clusters": {},
                "mongo": {"projects": {}, "envs": {}},
                "env_types": {},
                "env_levels": {},
                "customers": {},
                "health": {"healthy": 0, "unhealthy": 0, "total": 0, "na": 0},
                "total_vanity_urls": 0
            }

    def build_healthz_url(self, app_name, app_data):
        """Build the correct healthz URL based on environment type and URI"""
        uri = app_data.get("health_check_uri", "api")
        project_uri = app_data.get("project_uri")
        
        if project_uri:
            return f"https://{app_name}.{project_uri}.apprentice.io/healthz"
        elif app_data.get("type") in ["enterprise", "shared"]:
            return f"https://{app_name}.{uri}.apprentice.io/healthz"
        return f"https://{app_name}.api.apprentice.io/healthz"

    def initialize_data(self):
        """Initialize data with proper error handling"""
        logger.info("Starting initialize_data")
        
        env_data = self.get_blob_data()
        if not env_data:
            logger.error("No environment data found in the blob.")
            return []
        if isinstance(env_data, dict) and 'error' in env_data:
            logger.error(f"Error in blob data: {env_data['error']}")
            return []

        # Reset stats
        self.data["stats"] = {
            "clusters": {},
            "mongo": {
                "projects": {},
                "envs": {}
            },
            "env_types": {},
            "env_levels": {},
            "health": {
                "healthy": 0,
                "unhealthy": 0,
                "total": 0,
                "na": 0
            }
        }
        
        self.data["stats"] = self.calculate_stats(env_data)
        logger.info(f"Statistics calculated successfully: {self.data['stats']}")
            
        tasks = []

        for app_name, app_data in env_data.items():
            if not isinstance(app_data, dict):
                continue

            # Store the original data
            self.data["apps"][app_name] = app_data.copy()
            
            # Skip health checks for cluster environments
            if app_data.get("type") == "cluster":
                self.get_health(app_name, app_data, is_vanity=False, regions=app_data.get("regions", ["no regions"]), env_level=app_data.get("env_level", "N/A"))
                continue
            
            # Only check health for environments with projects
            if app_data.get("projects"):
                regions = app_data.get("regions", ["no regions"])
                env_level = app_data.get("env_level", "N/A")
                
                # Count total environments for health tracking (excluding clusters)
                if app_data.get("type") and app_data.get("type") != "cluster":
                    self.data["stats"]["health"]["total"] += 1
                
                tasks.append(
                    (self.get_health, {
                        "app_name": app_name,
                        "app_data": app_data,
                        "is_vanity": False,
                        "regions": regions,
                        "env_level": env_level
                    })
                )

                # Handle vanity URLs
                vanity_urls = app_data.get("vanity_urls", [])
                if isinstance(vanity_urls, list):
                    for vanity in vanity_urls:
                        tasks.append(
                            (self.get_health, {
                                "app_name": vanity,
                                "app_data": app_data,
                                "is_vanity": True,
                                "parent_env": app_name,
                                "regions": regions,
                                "env_level": env_level
                            })
                        )

        logger.info(f"Created {len(tasks)} health check tasks")
        return tasks

    @staticmethod
    def normalize_health_status(status):
        """Normalize different health status formats to a consistent format."""
        if not status:
            return 'error', False
            
        status_str = str(status).strip().lower()
        
        if status_str == 'n/a':
            return ('n/a', None)
            
        healthy_statuses = {'ok', 'up', 'healthy', 'running', 'true', '1'}
        status_str = ''.join(status_str.split())
        status_str = status_str.replace('"', '').replace("'", "")
        
        is_healthy = status_str in healthy_statuses
        return ('ok' if is_healthy else 'error', is_healthy)

    def is_environment_healthy(self, health_info):
        """Check if an environment is healthy based on its health info."""
        status = health_info.get('healthz', 'error')
        normalized_status, is_healthy = self.normalize_health_status(status)
        return is_healthy

    def create_na_response(self, app_name, app_data, healthz_url=None):
        """Create a response for environments that don't need health checks."""
        return {
            "healthz": "n/a",
            "commit_date": "n/a",
            "commit_hash": "n/a",
            "copyright": "n/a",
            "deployment_dt": "n/a",
            "env": app_data.get("env", "n/a"),
            "package_version": "n/a",
            "server_start_at": "n/a",
            "healthz_url": healthz_url or "n/a",
            "customer": app_data.get("customer", "Unknown")
        }

    def get_health(self, app_name, app_data, is_vanity=False, parent_env=None, regions=["No Regions"], env_level="N/A"):
        """Get health status with improved error handling and field normalization"""
        # Skip health check for cluster environments
        if app_data.get("type") == "cluster":
            env_info = self.create_na_response(app_name, app_data)
            env_info.update({
                "env_level": env_level,
                "regions": regions,
                "customer": app_data.get("customer", "Unknown")
            })
            self.data["apps"][app_name] = env_info
            self.data["stats"]["health"]["na"] += 1
            return

        try:
            healthz_url = self.build_healthz_url(app_name, app_data)
            response = requests.get(healthz_url, timeout=10)
            response.raise_for_status()
            
            # Normalize the JSON response
            raw_info = response.json()
            info = {}
            for k, v in raw_info.items():
                clean_key = k.strip()
                clean_value = v.strip() if isinstance(v, str) else v
                
                key_mapping = {
                    'status': 'status',
                    'start_time': 'server_start_at',
                    'deploy_time': 'deployment_dt',
                    'commit_time': 'commit_date',
                    'message': 'service'
                }
                
                normalized_key = key_mapping.get(clean_key, clean_key)
                info[normalized_key] = clean_value
            
            # Normalize status
            status = info.get("status", "Error")
            normalized_status, is_healthy = self.normalize_health_status(status)
            
            # Handle timestamps
            timestamp_fields = ['server_start_at', 'deployment_dt', 'commit_date']
            for field in timestamp_fields:
                if field in info:
                    try:
                        timestamp_value = info[field]
                        if ';' in timestamp_value:
                            timestamp_value = timestamp_value.split(';')[0].strip()
                        
                        try:
                            parsed_time = datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
                        except ValueError:
                            try:
                                unix_timestamp = int(timestamp_value)
                                parsed_time = datetime.fromtimestamp(unix_timestamp)
                            except ValueError:
                                continue
                        
                        info[field] = parsed_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                    except Exception as e:
                        logger.warning(f"Error processing timestamp for {field}: {str(e)}")
                        info[field] = info[field]  # Keep original if parsing fails

            health_info = {
                "healthz": normalized_status,
                "commit_date": info.get("commit_date", "Unknown"),
                "commit_hash": info.get("commit_hash", "Unknown"),
                "copyright": info.get("copyright", "Unknown"),
                "deployment_dt": info.get("deployment_dt", "Unknown"),
                "env": info.get("env", "Unknown"),
                "package_version": info.get("package_version", "Unknown"),
                "server_start_at": info.get("server_start_at", "Unknown"),
                "healthz_url": healthz_url,
                "customer": app_data.get("customer", "Unknown"),
                "service": info.get("service", info.get("message", "Unknown"))
            }

            if is_vanity:
                parent_data = self.data["apps"].get(parent_env, {})
                parent_data.setdefault("vanity_health", {})[app_name] = health_info
                if not is_healthy:
                    parent_data.setdefault("unhealthy_vanity_count", 0)
                    parent_data["unhealthy_vanity_count"] += 1
            else:
                env_info = self.data["apps"].get(app_name, {})
                env_info.update(health_info)
                env_info.update({
                    "env_level": env_level,
                    "regions": regions,
                    "customer": app_data.get("customer", "Unknown")
                })
                if is_healthy:
                    self.data["stats"]["health"]["healthy"] += 1
                else:
                    self.data["stats"]["health"]["unhealthy"] += 1
                self.data["apps"][app_name] = env_info

            logger.debug(f"Health check for {app_name}: Original status='{status}', " 
                    f"Normalized='{normalized_status}', Healthy={is_healthy}")

        except (SSLError, ConnectionError, Timeout, HTTPError) as e:
            error_response = self.create_error_response(app_name, str(e), healthz_url)
            error_response["customer"] = app_data.get("customer", "Unknown")
            
            if is_vanity:
                parent_data = self.data["apps"].get(parent_env, {})
                parent_data.setdefault("vanity_health", {})[app_name] = error_response
                parent_data.setdefault("unhealthy_vanity_count", 0)
                parent_data["unhealthy_vanity_count"] += 1
            else:
                self.data["apps"][app_name].update(error_response)
                self.data["stats"]["health"]["unhealthy"] += 1

    def create_error_response(self, app_name, error_message, healthz_url):
        return {
            "healthz": "Error",
            "commit_date": "Error",
            "commit_hash": "Error",
            "copyright": "Error",
            "deployment_dt": "Error",
            "env": "Error",
            "message": error_message,
            "package_version": "Error",
            "server_start_at": "Error",
            "healthz_url": healthz_url
        }

    def get_all_data(self):
        """Get all data with proper error handling and timestamp updates"""
        self.data["stats"]["health"] = {"healthy": 0, "unhealthy": 0, "total": 0, "na": 0}
        
        try:
            tasks = self.initialize_data()
            if not tasks:
                logger.warning("No tasks generated during initialization")
                return {
                    "status": "error",
                    "updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "message": "No environment data available"
                }

            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_task = {executor.submit(task, **kwargs): (task, kwargs) for task, kwargs in tasks}
                for future in as_completed(future_to_task):
                    task, kwargs = future_to_task[future]
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"Error in task {task} with args {kwargs}: {e}")

            current_time = datetime.utcnow()
            self.data["updated"] = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            return {
                "status": "updated",
                "updated": self.data["updated"],
                "message": (f"{len(self.data['apps'])} environments refreshed, "
                        f"{self.data['stats']['health']['unhealthy']} unhealthy.")
            }
        except Exception as e:
            logger.error(f"Error in get_all_data: {e}")
            return {"error": str(e)}

    def get_dashboard(self, in_request_context=True):
        """Get dashboard data."""
        logger.info("Getting dashboard data.")
        if not self.initialized or not self.data["apps"]:
            self.get_all_data()
            self.initialized = True
        return self.data

    def refresh_dashboard(self):
        """Refresh dashboard data and embeddings."""
        logger.info(f"Refreshing dashboard data. Lambda function: {self.lambda_function}")
        try:
            # Invoke lambda to refresh environment data and embeddings
            if self.lambda_function:
                self.lambda_service.invoke_function(self.lambda_function, {})
                logger.info("Lambda function invoked successfully")
            else:
                logger.warning("No lambda function configured")

            # Get fresh data
            status = self.get_all_data()
            logger.info("Dashboard refreshed")
            return status

        except Exception as e:
            logger.error(f"Error refreshing dashboard: {e}")
            return {"error": str(e)}

    def get_dashboard_summary(self):
        """Enhanced dashboard summary with embeddings info."""
        try:
            if not self.initialized or not self.data["apps"]:
                logger.info("Dashboard not initialized, loading data first")
                result = self.get_all_data()
                self.initialized = True
                
                if isinstance(result, dict) and "error" in result:
                    logger.error(f"Failed to get data: {result['error']}")
                    raise ValueError(f"Data initialization failed: {result['error']}")

            stats = self.data.get("stats", {})

            # Get embedding stats if available
            try:
                embeddings_data = self.s3_service.get_json(
                    self.data_bucket, 
                    "env_config/env_config_embeddings.json"
                ) or {}
                embeddings_status = {
                    "available": bool(embeddings_data),
                    "count": len(embeddings_data.get('embeddings', [])),
                    "last_updated": embeddings_data.get('updated_at', 'Never')
                }
            except Exception as e:
                logger.error(f"Error getting embeddings stats: {e}")
                embeddings_status = {
                    "available": False,
                    "count": 0,
                    "last_updated": "Error"
                }

            # Build comprehensive summary
            summary = {
                "total_environments": len(self.data["apps"]),
                "total_vanity_urls": stats.get("total_vanity_urls", 0),
                "health_status": dict(stats.get("health", {"healthy": 0, "unhealthy": 0, "total": 0})),
                "environment_types": dict(stats.get("env_types", {})),
                "environment_levels": dict(stats.get("env_levels", {})),
                "clusters": dict(stats.get("clusters", {})),
                "customers": dict(stats.get("customers", {})),
                "mongo": {
                    "projects": dict(stats.get("mongo", {}).get("projects", {})),
                    "environments": dict(stats.get("mongo", {}).get("envs", {}))
                },
                "embeddings": embeddings_status,
                "last_updated": self.data.get("updated", "Never")
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating dashboard summary: {e}")
            return {
                "total_environments": 0,
                "total_vanity_urls": 0,
                "health_status": {"healthy": 0, "unhealthy": 0, "total": 0},
                "environment_types": {},
                "environment_levels": {},
                "clusters": {},
                "customers": {},
                "mongo": {"projects": {}, "environments": {}},
                "embeddings": {"available": False, "count": 0, "last_updated": "Error"},
                "last_updated": "Error"
            }

    async def invoke_lambda(self):
        await self.lambda_service.invoke_lambda_async(self.lambda_function, {})