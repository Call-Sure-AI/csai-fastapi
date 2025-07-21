import os
from typing import Optional

class S3Settings:
    AWS_REGION: str = os.getenv('AWS_REGION', 'us-east-1')
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv('AWS_SECRET_ACCESS_KEY')
    S3_BUCKET_NAME: Optional[str] = os.getenv('S3_BUCKET_NAME')

    MAX_FILE_SIZE: int = int(os.getenv('MAX_FILE_SIZE', '10485760'))  # 10MB default
    ALLOWED_FILE_TYPES: list = os.getenv('ALLOWED_FILE_TYPES', '').split(',') if os.getenv('ALLOWED_FILE_TYPES') else []
    
    @classmethod
    def validate_config(cls):
        missing_vars = []
        
        if not cls.AWS_ACCESS_KEY_ID:
            missing_vars.append('AWS_ACCESS_KEY_ID')
        if not cls.AWS_SECRET_ACCESS_KEY:
            missing_vars.append('AWS_SECRET_ACCESS_KEY')
        if not cls.S3_BUCKET_NAME:
            missing_vars.append('S3_BUCKET_NAME')
            
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return True

s3_settings = S3Settings()
