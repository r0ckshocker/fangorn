import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
    DATA_BUCKET = os.getenv("DATA_BUCKET")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    ADMIN_GROUP = os.getenv("ADMIN_GROUP", "admin")
    USERS_GROUP = os.getenv("USERS_GROUP", "users")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8080))
    
    # Cloudflare Access settings
    CF_ACCESS_URL = os.getenv("CF_ACCESS_URL", "https://apprenticefs.cloudflareaccess.com/cdn-cgi/access/get-identity")
    USE_CF_ACCESS = os.getenv("USE_CF_ACCESS", "true").lower() == "true"
    
    # Static folder and template folder settings
    STATIC_FOLDER = os.getenv("STATIC_FOLDER", "app/client/dist")
    TEMPLATE_FOLDER = os.getenv("TEMPLATE_FOLDER", "app/client/html")
    
    # Local development user settings
    LOCAL_USER = {
        'id': os.getenv("LOCAL_USER_ID", "local_admin"),
        'name': os.getenv("LOCAL_USER_NAME", "Local Admin"),
        'email': os.getenv("LOCAL_USER_EMAIL", "local_admin@example.com"),
        'groups': os.getenv("LOCAL_USER_GROUPS", "admin").split(",")
    }

class DevelopmentConfig(Config):
    ENVIRONMENT = "development"

class ProductionConfig(Config):
    pass

class TestingConfig(Config):
    TESTING = True

def get_config():
    env = os.getenv("ENVIRONMENT", "production")
    if env == "development":
        return DevelopmentConfig()
    elif env == "testing":
        return TestingConfig()
    else:
        return ProductionConfig()