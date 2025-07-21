import os
from typing import Dict, Any

class EmailConfig:
    
    SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.hostinger.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '465'))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME', 'noreply@callsure.ai')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
    SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'True').lower() == 'true'
    
    SENDER_NAME = os.getenv('SENDER_NAME', 'Callsure AI')
    SENDER_EMAIL = os.getenv('SENDER_EMAIL', 'noreply@callsure.ai')
    REPLY_TO_EMAIL = os.getenv('REPLY_TO_EMAIL', 'support@callsure.ai')
    
    MAX_RECIPIENTS_BULK = int(os.getenv('MAX_RECIPIENTS_BULK', '100'))
    MAX_EMAIL_SIZE = int(os.getenv('MAX_EMAIL_SIZE', '1048576'))  # 1MB
    MAX_ATTACHMENTS = int(os.getenv('MAX_ATTACHMENTS', '5'))
    
    RATE_LIMIT_PER_MINUTE = int(os.getenv('EMAIL_RATE_LIMIT_PER_MINUTE', '60'))
    RATE_LIMIT_PER_HOUR = int(os.getenv('EMAIL_RATE_LIMIT_PER_HOUR', '1000'))
    
    TEMPLATE_BASE_URL = os.getenv('TEMPLATE_BASE_URL', 'https://callsure.ai')
    UNSUBSCRIBE_URL = os.getenv('UNSUBSCRIBE_URL', 'https://callsure.ai/unsubscribe')
    
    @classmethod
    def validate_config(cls) -> Dict[str, Any]:
        errors = []
        warnings = []
        
        if not cls.SMTP_PASSWORD:
            errors.append("SMTP_PASSWORD is required")
        
        if not cls.SENDER_EMAIL:
            errors.append("SENDER_EMAIL is required")
        
        if cls.MAX_RECIPIENTS_BULK > 500:
            warnings.append("MAX_RECIPIENTS_BULK is very high, consider lowering it")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    @classmethod
    def get_smtp_config(cls) -> Dict[str, Any]:
        return {
            "hostname": cls.SMTP_HOST,
            "port": cls.SMTP_PORT,
            "use_tls": cls.SMTP_USE_TLS,
            "username": cls.SMTP_USERNAME,
            "password": cls.SMTP_PASSWORD
        }
