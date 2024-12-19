import logging
import os
import threading
import time

import dotenv
import requests
from flask import Flask, abort, g, jsonify, request, send_from_directory, session
from flask_assets import Environment
from flask_cors import CORS

from app.server.api import (
    alfred_instance,
    api_bp,
    devision_instance,
    env_config_instance,
    lucius_instance,
)
from app.server.config import get_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app():
    config = get_config()
    app = Flask(
        __name__,
        static_folder=config.STATIC_FOLDER,
        template_folder=config.TEMPLATE_FOLDER,
    )

    # Load configuration
    app.config.from_object(config)

    # Load environment variables
    dotenv.load_dotenv(override=True)
    logger.info("Loaded .env file")

    # Setup CORS
    CORS(
        app,
        resources={
            r"/*": {
                "origins": "*",
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": [
                    "Content-Type",
                    "Authorization",
                    "Access-Control-Allow-Credentials",
                ],
            }
        },
    )

    # Setup Flask-Assets
    assets = Environment(app)

    @app.before_request
    def before_request():
        cf_auth_header = request.headers.get("Cf-Access-Jwt-Assertion")
        environment = app.config["ENVIRONMENT"]
        logger.info(f"Environment: {environment}")
        logger.info(f"Request path: {request.path}")
        logger.info(f"Available headers: {dict(request.headers)}")

        # Initialize g.user as None by default
        g.user = None

        # Skip auth for healthcheck endpoint
        if request.path == '/healthz':
            logger.info("Skipping auth for healthcheck endpoint")
            return

        if cf_auth_header:
            logger.info("Received Cf-Access-Jwt-Assertion header")
            
            # Try to get user from existing session first
            if "user" in session and session["user"].get("id") != "empty":
                logger.info("Found existing user in session")
                g.user = session["user"]
                return
                
            logger.info("No valid user in session, fetching from Cloudflare")
            try:
                response = requests.get(
                    app.config["CF_ACCESS_URL"],
                    headers={
                        "cookie": f"CF_Authorization={cf_auth_header}",
                        "Content-Type": "application/json"
                    },
                    timeout=5
                )
                logger.info(f"Cloudflare response status: {response.status_code}")
                
                if response.status_code == 200:
                    resp_json = response.json()
                    logger.debug(f"Cloudflare user data: {resp_json}")
                    
                    session.permanent = True  # Make session permanent
                    session["user"] = {
                        "id": resp_json["id"],
                        "name": resp_json["name"],
                        "email": resp_json["email"],
                        "groups": resp_json.get("groups", []),
                    }
                    session["running_local"] = False
                    g.user = session["user"]
                    logger.info(f'New session created for user: {resp_json["email"]}')
                else:
                    logger.error(f"Failed to fetch auth info: {response.text}")
            except requests.RequestException as error:
                logger.error(f"Unable to fetch auth info: {error}")
                logger.exception("Full exception details:")

        elif environment in ["development", "testing"]:
            logger.info("Running in local or testing mode, using default user")
            default_user = {
                "id": "testuser",
                "name": "Test User",
                "email": "test@example.com",
                "groups": ["admin", "users"],
            }
            session["user"] = default_user
            session["running_local"] = True
            g.user = default_user
        elif environment == "production":
            logger.warning("Access attempt without Cloudflare header in production environment")
            abort(404)
        else:
            logger.error(f"Unexpected authentication scenario in environment: {environment}")

        if g.user:
            logger.info(f'Request from user: {g.user["email"]}')
        else:
            logger.info("Request from anonymous user")

    @app.after_request
    def after_request(response):
        try:
            # Check if g has the user attribute before trying to access it
            if hasattr(g, 'user') and g.user:
                logger.info(f'Request processed for user: {g.user["email"]}')
            else:
                logger.info("Request processed for anonymous user")
        except Exception as e:
            # Log the error but don't let it affect the response
            logger.error(f"Error in after_request: {str(e)}")
        return response

    @app.route("/<path:path>", methods=["GET"])
    def serve_react_app(path):
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        else:
            return send_from_directory(app.static_folder, "index.html")

    @app.route("/")
    def index():
        logger.info("Serving React app")
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/healthz", methods=["GET"])
    def healthz():
        return jsonify({"status": "ok"})

    @app.errorhandler(404)
    def page_not_found(e):
        return send_from_directory(app.static_folder, "index.html")

    @app.errorhandler(500)
    def internal_server_error(e):
        return jsonify({"error": "500 internal server error"}), 500

    # Register blueprint
    app.register_blueprint(api_bp, url_prefix="/api")

    # Log registered routes
    with app.app_context():
        logger.info("Registered Routes:")
        for rule in app.url_map.iter_rules():
            logger.info(f"{rule.endpoint}: {rule}")

    return app


def preload_caches(app):
    logger.info("Preloading caches for all oracles...")
    try:
        with app.app_context():
            env_config_instance.get_dashboard()
            devision_instance.get_dashboard()
            lucius_instance.get_dashboard()
            alfred_instance.get_dashboard(in_request_context=False)
        logger.info("Cache preloading completed.")
    except Exception as e:
        logger.error(f"Error during cache preloading: {str(e)}")


def periodic_cache_update(app):
    while True:
        time.sleep(900)  # 15 minutes
        logger.info("Performing periodic cache update...")
        try:
            with app.app_context():
                env_config_instance.get_dashboard()
                devision_instance.get_dashboard()
                lucius_instance.get_dashboard()
                alfred_instance.get_dashboard(in_request_context=False)
            logger.info("Periodic cache update completed.")
        except Exception as e:
            logger.error(f"Error during periodic cache update: {str(e)}")


if __name__ == "__main__":
    app = create_app()

    # Preload caches
    preload_caches(app)

    # Start periodic cache update in a separate thread
    update_thread = threading.Thread(target=periodic_cache_update, args=(app,))
    update_thread.daemon = True
    update_thread.start()

    logger.info(f"Running on {app.config['HOST']}:{app.config['PORT']}")
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=app.config["DEBUG"],
    )
    logger.info(f"Closing port {app.config['PORT']}")
