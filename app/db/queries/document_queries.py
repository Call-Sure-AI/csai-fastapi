from typing import Dict, List, Optional, Tuple
from datetime import datetime

class DocumentQueries:
    """All SQL queries related to Document table"""
    
    GET_DOCUMENT_BY_ID = """
        SELECT * FROM "Document" WHERE id = %s
    """
    
    GET_DOCUMENTS_BY_COMPANY = """
        SELECT * FROM "Document" 
        WHERE "company_id" = %s 
        ORDER BY "created_at" DESC
    """
    
    GET_DOCUMENTS_BY_AGENT = """
        SELECT * FROM "Document" 
        WHERE "agent_id" = %s 
        ORDER BY "created_at" DESC
    """
    
    GET_IMAGE_DOCUMENTS = """
        SELECT * FROM "Document" 
        WHERE "is_image" = true AND "company_id" = %s
        ORDER BY "created_at" DESC
    """
    
    GET_DOCUMENTS_BY_TYPE = """
        SELECT * FROM "Document" 
        WHERE type = %s AND "company_id" = %s
        ORDER BY "created_at" DESC
    """
    
    GET_DOCUMENTS_NEEDING_EMBEDDING = """
        SELECT * FROM "Document" 
        WHERE "embedding_id" IS NULL AND "company_id" = %s
        ORDER BY "created_at" ASC
        LIMIT %s
    """
    
    CREATE_DOCUMENT = """
        INSERT INTO "Document" (
            id, "company_id", "agent_id", name, type, content, 
            "file_type", "file_size", "original_filename"
        ) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) 
        RETURNING *
    """
    
    CREATE_IMAGE_DOCUMENT = """
        INSERT INTO "Document" (
            id, "company_id", "agent_id", name, type, content,
            "file_type", "file_size", "original_filename", width, height,
            "image_format", "is_image", "image_content", "image_metadata"
        ) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
        RETURNING *
    """
    
    UPDATE_DOCUMENT_CONTENT = """
        UPDATE "Document" 
        SET content = %s, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    UPDATE_DOCUMENT_EMBEDDING = """
        UPDATE "Document" 
        SET "embedding_id" = %s, "last_embedded" = CURRENT_TIMESTAMP, 
            "chunk_count" = %s, embedding = %s, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    UPDATE_DOCUMENT_DESCRIPTIONS = """
        UPDATE "Document" 
        SET "user_description" = %s, "auto_description" = %s, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    DELETE_DOCUMENT = """
        DELETE FROM "Document" WHERE id = %s
    """
    
    DELETE_DOCUMENTS_BY_COMPANY = """
        DELETE FROM "Document" WHERE "company_id" = %s
    """
    
    DELETE_DOCUMENTS_BY_AGENT = """
        DELETE FROM "Document" WHERE "agent_id" = %s
    """
    
    GET_COMPANY_STORAGE_USAGE = """
        SELECT 
            COUNT(*) as total_documents,
            SUM("file_size") as total_size,
            COUNT(*) FILTER (WHERE "is_image" = true) as image_count,
            SUM("file_size") FILTER (WHERE "is_image" = true) as image_storage
        FROM "Document" 
        WHERE "company_id" = %s
    """

    @staticmethod
    def get_document_by_id_params(document_id: str) -> Tuple[str, tuple]:
        """Get document by ID parameters"""
        return DocumentQueries.GET_DOCUMENT_BY_ID, (document_id,)
    
    @staticmethod
    def get_documents_by_company_params(company_id: str) -> Tuple[str, tuple]:
        """Get documents by company parameters"""
        return DocumentQueries.GET_DOCUMENTS_BY_COMPANY, (company_id,)
    
    @staticmethod
    def create_document_params(document_id: str, company_id: str, name: str, doc_type: str, content: str) -> Tuple[str, tuple]:
        """Create document parameters"""
        return DocumentQueries.CREATE_DOCUMENT, (document_id, company_id, None, name, doc_type, content, None, None, None)