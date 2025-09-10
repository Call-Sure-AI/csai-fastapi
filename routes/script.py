from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from app.models.scripts import (
    Script, ScriptTemplate, ScriptVersion, ScriptValidation,
    ScriptValidationResult, ScriptAnalytics, ScriptPublishRequest,
    ScriptAnalyticsRequest, ScriptStatus
)
from handlers.script_handler import ScriptHandler
from middleware.auth_middleware import get_current_user
from handlers.company_handler import CompanyHandler

router = APIRouter(prefix="/scripts", tags=["Scripts"])
script_handler = ScriptHandler()

@router.get("/templates", response_model=List[ScriptTemplate])
async def get_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    current_user = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Get all available script templates
    """
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]
    return await script_handler.get_templates(category=category, tags=tags)

@router.post("/templates", response_model=ScriptTemplate)
async def create_template(
    template: ScriptTemplate,
    current_user = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Create a new script template
    """
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]
    return await script_handler.create_template(template, company_id)

@router.get("/", response_model=List[Script])
async def get_scripts(
    status: Optional[ScriptStatus] = Query(None, description="Filter by status"),
    current_user = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Get all scripts for the current company
    """
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]
    return await script_handler.get_scripts(company_id, status=status)

@router.post("/", response_model=Script)
async def create_script(
    script: Script,
    current_user = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Create a new script
    """
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]
    return await script_handler.create_script(
        script, 
        company_id, 
        getattr(current_user, 'id', None)
    )

@router.get("/{script_id}", response_model=Script)
async def get_script(
    script_id: str,
    current_user = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Get a specific script by ID
    """
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]
    return await script_handler.get_script(script_id, company_id)

@router.put("/{script_id}", response_model=Script)
async def update_script(
    script_id: str,
    updates: Dict[str, Any],
    current_user = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Update an existing script
    """
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]
    return await script_handler.update_script(
        script_id, 
        updates, 
        company_id, 
        getattr(current_user, 'id', None)
    )

@router.post("/{script_id}/publish", response_model=Dict[str, Any])
async def publish_script(
    script_id: str,
    request: ScriptPublishRequest = ScriptPublishRequest(),
    current_user = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Publish a script
    """
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]
    return await script_handler.publish_script(
        script_id, 
        request, 
        company_id, 
        getattr(current_user, 'id', None)
    )

@router.get("/{script_id}/versions", response_model=List[ScriptVersion])
async def get_script_versions(
    script_id: str,
    current_user = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Get all versions of a script
    """
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]
    return await script_handler.get_script_versions(script_id, company_id)

@router.post("/builder/validate", response_model=ScriptValidationResult)
async def validate_script(
    validation: ScriptValidation,
    current_user = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Validate a script flow
    """
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]
    return await script_handler.validate_script(validation)

@router.get("/{script_id}/analytics", response_model=ScriptAnalytics)
async def get_script_analytics(
    script_id: str,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    metrics: Optional[List[str]] = Query(
        None, 
        description="Metrics to include",
        example=["executions", "completions", "duration", "drop_offs"]
    ),
    current_user = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Get analytics for a script
    """
    from datetime import datetime
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]
    # Parse dates if provided
    request = ScriptAnalyticsRequest()
    if start_date:
        request.start_date = datetime.fromisoformat(start_date)
    if end_date:
        request.end_date = datetime.fromisoformat(end_date)
    if metrics:
        request.metrics = metrics
    
    return await script_handler.get_script_analytics(script_id, request, company_id)

# Additional endpoints for script management

@router.delete("/{script_id}", response_model=Dict[str, Any])
async def delete_script(
    script_id: str,
    current_user = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Delete a script (soft delete - moves to archived status)
    """
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]
    await script_handler.update_script(
        script_id,
        {"status": ScriptStatus.ARCHIVED},
        company_id,
        getattr(current_user, 'id', None)
    )
    return {"success": True, "message": f"Script {script_id} archived successfully"}

@router.post("/{script_id}/duplicate", response_model=Script)
async def duplicate_script(
    script_id: str,
    new_name: str = Query(..., description="Name for the duplicated script"),
    current_user = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Duplicate an existing script
    """
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]
    # Get original script
    original = await script_handler.get_script(script_id, company_id)
    
    # Create new script with same flow
    new_script = Script(
        name=new_name,
        description=f"Duplicated from {original.name}",
        template_id=original.template_id,
        flow=original.flow,
        tags=original.tags,
        metadata={**original.metadata, "duplicated_from": script_id}
    )
    
    return await script_handler.create_script(
        new_script, 
        company_id, 
        getattr(current_user, 'id', None)
    )

@router.post("/{script_id}/test", response_model=Dict[str, Any])
async def test_script(
    script_id: str,
    test_data: Optional[Dict[str, Any]] = None,
    current_user = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Test run a script with sample data
    """
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]
    # Get script
    script = await script_handler.get_script(script_id, company_id)
    
    # Validate script first
    validation = ScriptValidation(flow=script.flow)
    result = await script_handler.validate_script(validation)
    
    if not result.is_valid:
        return {
            "success": False,
            "message": "Script validation failed",
            "errors": result.errors
        }
    
    # Here you would implement actual test execution logic
    # This is a placeholder response
    return {
        "success": True,
        "message": "Script test completed successfully",
        "test_id": f"TEST-{script_id[:8]}",
        "results": {
            "nodes_executed": len(script.flow.nodes),
            "test_data_used": test_data or {},
            "validation": result.dict()
        }
    }

@router.get("/{script_id}/export", response_model=Dict[str, Any])
async def export_script(
    script_id: str,
    format: str = Query("json", description="Export format (json, yaml)"),
    current_user = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Export a script in specified format
    """
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]
    script = await script_handler.get_script(script_id, company_id)
    
    if format == "json":
        return {
            "format": "json",
            "data": script.dict()
        }
    elif format == "yaml":
        # You would need to install and import pyyaml for this
        # import yaml
        # return {
        #     "format": "yaml",
        #     "data": yaml.dump(script.dict())
        # }
        raise HTTPException(status_code=400, detail="YAML export not yet implemented")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

@router.post("/import", response_model=Script)
async def import_script(
    script_data: Dict[str, Any],
    current_user = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Import a script from exported data
    """
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]
    # Remove id and company-specific fields
    script_data.pop('id', None)
    script_data.pop('company_id', None)
    script_data.pop('created_at', None)
    script_data.pop('updated_at', None)
    script_data.pop('published_at', None)
    
    # Create new script from imported data
    script = Script(**script_data)
    script.status = ScriptStatus.DRAFT  # Always import as draft
    script.is_active = False
    
    return await script_handler.create_script(
        script,
        company_id,
        getattr(current_user, 'id', None)
    )