import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Core Application
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key')
    JWT_SECRET = os.getenv('JWT_SECRET', 'secret')
    PORT = int(os.getenv('PORT', 8080))
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    
    # PostgreSQL Database Configuration
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    
    # GitHub Configuration
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    
    # AWS Configuration
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.getenv('AWS_REGION', 'ap-south-1')
    AWS_BUCKET_NAME = os.getenv('AWS_BUCKET_NAME')
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', os.getenv('AWS_BUCKET_NAME'))  # Fallback to AWS_BUCKET_NAME
    
    # Email Configuration (Updated to match .env)
    SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.hostinger.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 465))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME', 'noreply@callsure.ai')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
    SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'True').lower() == 'true'
    
    # Legacy SMTP fields for backward compatibility
    SMTP_USER = os.getenv('SMTP_USERNAME', os.getenv('SMTP_USER'))
    SMTP_FROM_EMAIL = os.getenv('SENDER_EMAIL', os.getenv('SMTP_FROM_EMAIL'))
    
    # Email Identity
    SENDER_NAME = os.getenv('SENDER_NAME', 'Callsure AI')
    SENDER_EMAIL = os.getenv('SENDER_EMAIL', 'noreply@callsure.ai')
    REPLY_TO_EMAIL = os.getenv('REPLY_TO_EMAIL', 'support@callsure.ai')
    
    # Email Limits
    MAX_RECIPIENTS_BULK = int(os.getenv('MAX_RECIPIENTS_BULK', 100))
    MAX_EMAIL_SIZE = int(os.getenv('MAX_EMAIL_SIZE', 1048576))
    EMAIL_RATE_LIMIT_PER_MINUTE = int(os.getenv('EMAIL_RATE_LIMIT_PER_MINUTE', 60))
    EMAIL_RATE_LIMIT_PER_HOUR = int(os.getenv('EMAIL_RATE_LIMIT_PER_HOUR', 1000))
    
    # Template Settings
    TEMPLATE_BASE_URL = os.getenv('TEMPLATE_BASE_URL', 'https://callsure.ai')
    UNSUBSCRIBE_URL = os.getenv('UNSUBSCRIBE_URL', 'https://callsure.ai/unsubscribe')
    
    # File Upload Settings
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 10485760))  # 10MB
    ALLOWED_FILE_TYPES = os.getenv('ALLOWED_FILE_TYPES', 'jpg,jpeg,png,pdf,doc,docx,txt').split(',')
    
    # WhatsApp/Facebook Configuration
    FACEBOOK_APP_ID = os.getenv('FACEBOOK_APP_ID')
    FACEBOOK_VERSION = os.getenv('FACEBOOK_VERSION', 'v23.0')
    WHATSAPP_CONFIG_ID = os.getenv('WHATSAPP_CONFIG_ID')

class DevelopmentConfig(Config):
    DEBUG = True
    
class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

class ElevenLabsConfig:
    def __init__(self):
        self.api_key = os.getenv('ELEVENLABS_API_KEY')
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY is not set in the environment.")

elevenlabs_config = ElevenLabsConfig()