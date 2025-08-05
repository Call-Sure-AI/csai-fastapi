from typing import Dict, List, Optional, Tuple
from datetime import datetime

class DocumentQueries:
    """All SQL queries related to Document table"""
    
    GET_DOCUMENT_BY_ID = """
        SELECT * FROM "Document" WHERE id = $1
    """
    
    GET_DOCUMENTS_BY_COMPANY = """
        SELECT * FROM "Document" 
        WHERE "company_id" = $1 
        ORDER BY "created_at" DESC
    """
    
    GET_DOCUMENTS_BY_AGENT = """
        SELECT * FROM "Document" 
        WHERE "agent_id" = $1 
        ORDER BY "created_at" DESC
    """
    
    GET_IMAGE_DOCUMENTS = """
        SELECT * FROM "Document" 
        WHERE "is_image" = true AND "company_id" = $1
        ORDER BY "created_at" DESC
    """
    
    GET_DOCUMENTS_BY_TYPE = """
        SELECT * FROM "Document" 
        WHERE type = $1 AND "company_id" = $2
        ORDER BY "created_at" DESC
    """
    
    GET_DOCUMENTS_NEEDING_EMBEDDING = """
        SELECT * FROM "Document" 
        WHERE "embedding_id" IS NULL AND "company_id" = $1
        ORDER BY "created_at" ASC
        LIMIT $2
    """
    
    CREATE_DOCUMENT = """
        INSERT INTO "Document" (
            id, "company_id", "agent_id", name, type, content, 
            "file_type", "file_size", "original_filename"
        ) 
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) 
        RETURNING *
    """
    
    CREATE_IMAGE_DOCUMENT = """
        INSERT INTO "Document" (
            id, "company_id", "agent_id", name, type, content,
            "file_type", "file_size", "original_filename", width, height,
            "image_format", "is_image", "image_content", "image_metadata"
        ) 
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15) 
        RETURNING *
    """
    
    UPDATE_DOCUMENT_CONTENT = """
        UPDATE "Document" 
        SET content = $1, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = $2
        RETURNING *
    """
    
    UPDATE_DOCUMENT_EMBEDDING = """
        UPDATE "Document" 
        SET "embedding_id" = $1, "last_embedded" = CURRENT_TIMESTAMP, 
            "chunk_count" = $2, embedding = $3, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = $4
        RETURNING *
    """
    
    UPDATE_DOCUMENT_DESCRIPTIONS = """
        UPDATE "Document" 
        SET "user_description" = $1, "auto_description" = $2, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = $3
        RETURNING *
    """
    
    DELETE_DOCUMENT = """
        DELETE FROM "Document" WHERE id = $1
    """
    
    DELETE_DOCUMENTS_BY_COMPANY = """
        DELETE FROM "Document" WHERE "company_id" = $1
    """
    
    DELETE_DOCUMENTS_BY_AGENT = """
        DELETE FROM "Document" WHERE "agent_id" = $1
    """
    
    GET_COMPANY_STORAGE_USAGE = """
        SELECT 
            COUNT(*) as total_documents,
            SUM("file_size") as total_size,
            COUNT(*) FILTER (WHERE "is_image" = true) as image_count,
            SUM("file_size") FILTER (WHERE "is_image" = true) as image_storage
        FROM "Document" 
        WHERE "company_id" = $1
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