from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Body
from typing import List, Dict, Any, Optional
from datetime import datetime

from handlers.lead_handler import LeadHandler
from middleware.auth_middleware import get_current_user
from app.models.leads import (
    Lead, LeadImportRequest, LeadImportResponse,
    LeadEnrichmentRequest, LeadScoreRequest, LeadScoreResponse,
    LeadSegment, LeadDistributionRequest, LeadDistributionResponse,
    LeadNurturingRequest, LeadJourney, LeadFilter,
    BulkLeadUpdate, LeadMergeRequest, LeadStatus, LeadSource, LeadPriority
)

router = APIRouter(prefix="/leads", tags=["Lead Management"])
lead_handler = LeadHandler()

@router.post("/import/{source}", response_model=LeadImportResponse)
async def import_leads(
    source: str,
    file: Optional[UploadFile] = File(None),
    request_data: Optional[LeadImportRequest] = Body(None),
    current_user = Depends(get_current_user)  # This is a UserResponse object
):
    """
    Import leads from various sources
    
    Sources:
    - csv: Upload CSV file
    - excel: Upload Excel file
    - crm: Sync from CRM (requires API credentials in request)
    - api: Direct API import with data in request body
    """
    if source not in ["csv", "excel", "crm", "api"]:
        raise HTTPException(status_code=400, detail="Invalid import source")
    
    if source in ["csv", "excel"] and not file:
        raise HTTPException(status_code=400, detail=f"{source.upper()} file required")
    
    if source in ["crm", "api"] and not request_data:
        raise HTTPException(status_code=400, detail="Request data required for this source")
    
    # Get company_id from current_user - it's an object, not a dict
    # First, let's check what attributes the user object has
    try:
        # Try to get company_id from the user object
        company_id = getattr(current_user, 'company_id', None)
        user_id = getattr(current_user, 'id', None)
        
        # If company_id is not directly on user, check if there's a companies list
        if not company_id and hasattr(current_user, 'companies'):
            companies = getattr(current_user, 'companies', [])
            if companies and len(companies) > 0:
                # Use the first company
                company_id = companies[0].get('id') if isinstance(companies[0], dict) else getattr(companies[0], 'id', None)
        
        # If still no company_id, we need to get it from somewhere else
        # You might need to query the database to get the user's company
        if not company_id:
            # For now, we'll need to handle this based on your auth system
            # This is a temporary workaround - you should get the actual company_id
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"No company_id found for user {user_id}. User object type: {type(current_user)}")
            logger.warning(f"User attributes: {dir(current_user)}")
            
            # You might need to query the Company table to get the user's company
            from app.db.postgres_client import get_db_connection
            async with await get_db_connection() as conn:
                result = await conn.fetchrow(
                    'SELECT id FROM "Company" WHERE user_id = $1 LIMIT 1',
                    user_id
                )
                if result:
                    company_id = result['id']
                else:
                    raise HTTPException(status_code=400, detail="No company found for user")
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting company_id: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Could not determine company context: {str(e)}")
    
    if not company_id:
        raise HTTPException(status_code=400, detail="Company ID not found. Please ensure you have a company associated with your account.")
    
    # Call the handler with company_id
    return await lead_handler.import_leads(source, file, request_data, company_id, user_id)

@router.post("/import-json", response_model=LeadImportResponse)
async def import_leads_json(
    request: LeadImportRequest,  # Required, not optional
    current_user = Depends(get_current_user)
):
    """
    Import leads via JSON API
    
    Example request body:
    {
        "source": "api",
        "data": [
            {
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "phone": "1234567890",
                "company": "Test Corp"
            }
        ]
    }
    """
    # Get company_id
    user_id = getattr(current_user, 'id', None)
    company_id = getattr(current_user, 'company_id', None)
    
    if not company_id:
        from app.db.postgres_client import get_db_connection
        async with await get_db_connection() as conn:
            result = await conn.fetchrow(
                'SELECT id FROM "Company" WHERE user_id = $1 LIMIT 1',
                user_id
            )
            if result:
                company_id = result['id']
            else:
                raise HTTPException(status_code=400, detail="No company found for user")
    
    # Set source to 'api' if not provided
    if not request.source:
        request.source = "api"
    
    return await lead_handler.import_leads("api", None, request, company_id, user_id)

@router.get("/", response_model=Dict[str, Any])
async def get_leads(
    status: Optional[List[LeadStatus]] = Query(None),
    source: Optional[List[LeadSource]] = Query(None),
    priority: Optional[List[LeadPriority]] = Query(None),
    score_min: Optional[int] = Query(None, ge=0, le=100),
    score_max: Optional[int] = Query(None, ge=0, le=100),
    assigned_to: Optional[List[str]] = Query(None),
    tags: Optional[List[str]] = Query(None),
    created_after: Optional[datetime] = Query(None),
    created_before: Optional[datetime] = Query(None),
    search_query: Optional[str] = Query(None),
    segment_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    current_user = Depends(get_current_user)
):
    """
    Get filtered and paginated leads
    """
    # Get company_id for filtering
    company_id = getattr(current_user, 'company_id', None)
    if not company_id:
        # Get from database
        from app.db.postgres_client import get_db_connection
        async with await get_db_connection() as conn:
            result = await conn.fetchrow(
                'SELECT id FROM "Company" WHERE user_id = $1 LIMIT 1',
                getattr(current_user, 'id', None)
            )
            if result:
                company_id = result['id']
    
    filters = LeadFilter(
        status=status,
        source=source,
        priority=priority,
        score_min=score_min,
        score_max=score_max,
        assigned_to=assigned_to,
        tags=tags,
        created_after=created_after,
        created_before=created_before,
        search_query=search_query,
        segment_id=segment_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    return await lead_handler.get_leads(filters, company_id)

@router.get("/{lead_id}", response_model=Lead)
async def get_lead(
    lead_id: str,
    current_user: dict = Depends(get_current_user)
):

    lead = await lead_handler.get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead

@router.post("/score", response_model=List[LeadScoreResponse])
async def score_leads(
    request: LeadScoreRequest,
    current_user: dict = Depends(get_current_user)
):

    if not request.lead_id and not request.lead_ids:
        raise HTTPException(status_code=400, detail="Either lead_id or lead_ids required")
    
    return await lead_handler.score_leads(request)

@router.get("/segments", response_model=List[LeadSegment])
async def get_segments(
    current_user: dict = Depends(get_current_user)
):

    return await lead_handler.get_segments()

@router.post("/segments", response_model=LeadSegment)
async def create_segment(
    segment: LeadSegment,
    current_user: dict = Depends(get_current_user)
):

    return await lead_handler.create_segment(segment)

@router.get("/segments/{segment_id}/leads", response_model=List[Lead])
async def get_segment_leads(
    segment_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user)
):

    return await lead_handler.get_segment_leads(segment_id, page, page_size)

@router.post("/distribute", response_model=LeadDistributionResponse)
async def distribute_leads(
    request: LeadDistributionRequest,
    current_user: dict = Depends(get_current_user)
):

    if not request.lead_ids:
        raise HTTPException(status_code=400, detail="No leads to distribute")
    
    if request.distribution_method in ["round_robin", "load_balanced", "skill_based"] and not request.agent_ids:
        raise HTTPException(status_code=400, detail="Agent IDs required for this distribution method")
    
    return await lead_handler.distribute_leads(request)

@router.post("/nurture/run", response_model=Dict[str, Any])
async def run_nurturing_campaign(
    request: LeadNurturingRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Enroll leads in a nurturing campaign
    """
    if not request.lead_ids:
        raise HTTPException(status_code=400, detail="No leads specified")
    
    return await lead_handler.run_nurturing(request)

@router.get("/nurture/campaigns", response_model=List[Dict[str, Any]])
async def get_nurturing_campaigns(
    active_only: bool = Query(True),
    current_user: dict = Depends(get_current_user)
):
    """
    Get available nurturing campaigns
    """
    return await lead_handler.get_nurturing_campaigns(active_only)

@router.post("/nurture/campaigns", response_model=Dict[str, Any])
async def create_nurturing_campaign(
    campaign: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new nurturing campaign
    """
    return await lead_handler.create_nurturing_campaign(campaign)

@router.get("/{lead_id}/journey", response_model=LeadJourney)
async def get_lead_journey(
    lead_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get the complete journey/timeline for a lead
    
    Includes:
    - All events and interactions
    - Score history
    - Current stage
    - Engagement metrics
    - Touchpoints
    """
    return await lead_handler.get_lead_journey(lead_id)

@router.put("/{lead_id}", response_model=Lead)
async def update_lead(
    lead_id: str,
    updates: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Update a single lead
    """
    return await lead_handler.update_lead(lead_id, updates)

@router.patch("/bulk-update", response_model=Dict[str, Any])
async def bulk_update_leads(
    request: BulkLeadUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Bulk update multiple leads
    """
    if not request.lead_ids:
        raise HTTPException(status_code=400, detail="No leads specified")
    
    return await lead_handler.bulk_update_leads(request)

@router.post("/merge", response_model=Dict[str, Any])
async def merge_leads(
    request: LeadMergeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Merge duplicate leads
    
    Strategies:
    - keep_primary: Keep all data from primary lead
    - most_recent: Use most recently updated values
    - custom: Specify which fields to take from which lead
    """
    if not request.duplicate_lead_ids:
        raise HTTPException(status_code=400, detail="No duplicate leads specified")
    
    return await lead_handler.merge_leads(request)

@router.post("/enrich", response_model=Dict[str, Any])
async def enrich_leads(
    request: LeadEnrichmentRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Enrich lead data from external sources
    
    Fields that can be enriched:
    - company_info: Company details, size, industry
    - social_profiles: LinkedIn, Twitter, etc.
    - tech_stack: Technologies used by company
    """
    if not request.lead_ids:
        raise HTTPException(status_code=400, detail="No leads specified")
    
    return await lead_handler.enrich_leads(request)

@router.delete("/{lead_id}", response_model=Dict[str, str])
async def delete_lead(
    lead_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a lead
    """
    result = await lead_handler.delete_lead(lead_id)
    if not result:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return {"status": "deleted", "lead_id": lead_id}

@router.post("/cleanse", response_model=Dict[str, Any])
async def cleanse_leads(
    lead_ids: List[str] = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Cleanse and standardize lead data
    
    Operations:
    - Normalize email addresses
    - Format phone numbers
    - Capitalize names properly
    - Remove duplicates
    - Validate data formats
    """
    if not lead_ids:
        raise HTTPException(status_code=400, detail="No leads specified")
    
    return await lead_handler.cleanse_leads(lead_ids)

@router.get("/analytics/stats", response_model=Dict[str, Any])
async def get_lead_stats(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    group_by: str = Query("status", regex="^(status|source|priority|assigned_to)$"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get lead analytics and statistics
    """
    return await lead_handler.get_lead_stats(start_date, end_date, group_by)

@router.get("/export/{format}", response_model=Dict[str, Any])
async def export_leads(
    format: str,
    filters: Optional[LeadFilter] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Export leads to CSV or Excel
    
    Formats:
    - csv: Export as CSV file
    - excel: Export as Excel file
    """
    if format not in ["csv", "excel"]:
        raise HTTPException(status_code=400, detail="Invalid export format")
    
    return await lead_handler.export_leads(format, filters)

# Register routes in main.py
def register_lead_routes(app):
    """Register lead management routes with the app"""
    app.include_router(router)

@router.post("/debug/parse-csv")
async def debug_parse_csv(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """
    Debug endpoint to test CSV parsing without database operations
    """
    import csv
    import io
    
    try:
        content = await file.read()
        file_size = len(content)
        
        # Try to decode
        decoded = content.decode('utf-8')
        
        # Parse with csv.DictReader
        reader = csv.DictReader(io.StringIO(decoded))
        leads = list(reader)
        
        # Get headers
        headers = reader.fieldnames if reader.fieldnames else []
        
        return {
            "file_name": file.filename,
            "file_size": file_size,
            "content_preview": decoded[:500],  # First 500 chars
            "headers_found": headers,
            "total_rows": len(leads),
            "first_3_rows": leads[:3] if leads else [],
            "parsing_successful": True
        }
        
    except Exception as e:
        return {
            "file_name": file.filename,
            "parsing_successful": False,
            "error": str(e),
            "error_type": type(e).__name__
        }

@router.get("/debug/check-tables")
async def debug_check_tables(
    current_user = Depends(get_current_user)
):
    """
    Debug endpoint to check if lead tables exist and their structure
    """
    from app.db.postgres_client import get_db_connection
    
    async with await get_db_connection() as conn:
        # Check if leads table exists
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'leads'
            )
        """)
        
        structure = None
        sample_data = None
        
        if table_exists:
            # Get table structure
            columns = await conn.fetch("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'leads'
                ORDER BY ordinal_position
            """)
            
            structure = [dict(col) for col in columns]
            
            # Get sample data
            sample = await conn.fetch("""
                SELECT * FROM leads 
                LIMIT 5
            """)
            
            sample_data = [dict(row) for row in sample]
        
        # Get user's company
        user_id = getattr(current_user, 'id', None)
        company = await conn.fetchrow("""
            SELECT id, name FROM "Company" 
            WHERE user_id = $1 
            LIMIT 1
        """, user_id)
        
        return {
            "leads_table_exists": table_exists,
            "table_structure": structure,
            "sample_data": sample_data,
            "user_company": dict(company) if company else None
        }

@router.post("/debug/parse-excel")
async def debug_parse_excel(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """
    Debug endpoint to test Excel parsing without database operations
    """
    import pandas as pd
    import io
    
    try:
        content = await file.read()
        file_size = len(content)
        
        # Parse with pandas
        df = pd.read_excel(io.BytesIO(content))
        
        # Convert DataFrame to dict
        df = df.where(pd.notnull(df), None)  # Replace NaN with None
        leads = df.to_dict('records')
        
        # Get column info
        columns = list(df.columns)
        dtypes = {col: str(df[col].dtype) for col in columns}
        
        # Show first few rows with their types
        first_3_with_types = []
        for lead in leads[:3]:
            lead_with_types = {}
            for key, value in lead.items():
                lead_with_types[key] = {
                    "value": value,
                    "type": type(value).__name__,
                    "original": str(value) if value is not None else None
                }
            first_3_with_types.append(lead_with_types)
        
        return {
            "file_name": file.filename,
            "file_size": file_size,
            "columns_found": columns,
            "column_types": dtypes,
            "total_rows": len(leads),
            "first_3_rows": leads[:3],
            "first_3_rows_with_types": first_3_with_types,
            "parsing_successful": True
        }
        
    except Exception as e:
        return {
            "file_name": file.filename,
            "parsing_successful": False,
            "error": str(e),
            "error_type": type(e).__name__
        }