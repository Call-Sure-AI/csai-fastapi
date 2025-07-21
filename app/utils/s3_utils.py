import mimetypes
from typing import List, Optional
from fastapi import UploadFile, HTTPException

class S3Utils:
    @staticmethod
    def validate_file_type(file: UploadFile, allowed_types: List[str] = None) -> bool:
        if not allowed_types:
            return True
            
        file_extension = file.filename.split('.')[-1].lower()
        return file_extension in [t.lower().strip('.') for t in allowed_types]
    
    @staticmethod
    def validate_file_size(file: UploadFile, max_size: int) -> bool:
        return True
    
    @staticmethod
    def get_content_type(filename: str) -> str:

        content_type, _ = mimetypes.guess_type(filename)
        return content_type or 'application/octet-stream'
    
    @staticmethod
    def sanitize_key(key: str) -> str:

        sanitized = key.replace(' ', '-').replace('..', '.')
        return sanitized
    
    @staticmethod
    def validate_files_before_upload(
        files: List[UploadFile], 
        allowed_types: List[str] = None,
        max_file_size: int = 10485760  # 10MB
    ) -> None:

        for file in files:
            if allowed_types and not S3Utils.validate_file_type(file, allowed_types):
                raise HTTPException(
                    status_code=400, 
                    detail=f"File type not allowed: {file.filename}"
                )
