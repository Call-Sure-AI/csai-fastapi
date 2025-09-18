from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, JSONResponse
from typing import List, Optional
import uuid
import asyncio
import logging
from datetime import datetime
from middleware.auth_middleware import get_current_user_ws

from app.models.schemas import CallInitiateRequest, CallStatusResponse
from app.models.schemas import UserResponse, AgentCreate, LeadCreate, LeadUpdate, Lead, LeadsBulkUpdate
from app.models.schemas import (
    UserResponse, CSVParseResponse, CSVValidateRequest, CSVValidateResponse,
    CSVMapFieldsRequest, CSVMapFieldsResponse
)

from app.models.schemas import (
    UserResponse, CampaignSettings, BookingSettingsUpdate, 
    EmailSettingsUpdate, CallSettingsUpdate, ScheduleSettingsUpdate
)

from app.models.campaigns import CreateCampaignRequest, CampaignResponse, UpdateCampaignRequest
from middleware.auth_middleware import get_current_user
from app.services.campaign_service import CampaignService
from app.services.websocket_service import manager, WebSocketService
import io, csv

from routes.email import send_email_background
from handlers.company_handler import CompanyHandler
from handlers.agent_handler import AgentHandler
from app.models.schemas import AgentUpdate
from app.models.campaigns import AgentAssignRequest, AgentSettingsPayload
from app.db.postgres_client import get_db_connection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

svc  = CampaignService()

@router.post("/{campaign_id}/start", status_code=200)
async def start_campaign(
    campaign_id: str,
    background_tasks: BackgroundTasks,
    current_user:    UserResponse   = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):

    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]

    #svc  = CampaignService()
    camp = await svc.get_campaign(campaign_id, company_id)
    if not camp:
        raise HTTPException(404, "Campaign not found")

    if camp.status == "active":
        return {"message": f"Campaign {campaign_id} is already active"}

    payload  = UpdateCampaignRequest(status="active")
    updated  = await svc.update_campaign(campaign_id, company_id, payload)
    if not updated:
        raise HTTPException(500, "Failed to activate campaign")

    background_tasks.add_task(
        _activate_ai_agents,
        campaign_id,
        company_id,
        current_user.id
    )

    return {"message": f"Campaign {campaign_id} started – AI agents launching"}

async def _activate_ai_agents(
    campaign_id: str,
    company_id: str,
    user_id:    str,
    agent_handler: AgentHandler = Depends(AgentHandler)
):

    log.info("AI-bootstrap: scanning agents for user=%s company=%s", user_id, company_id)

    agents = await agent_handler.get_agents_by_user_id(user_id)
    if agents:
        update_req = AgentUpdate(is_active=True)
        for a in agents:
            try:
                await agent_handler.update_agent(a["id"], update_req, user_id)
                log.info("Activated agent %s", a["id"])
            except Exception as e:
                log.warning("Agent %s activation failed: %s", a["id"], e)
    else:
        new_agent = AgentCreate(
            name           = f"{campaign_id}-agent",
            type           = "campaign",
            is_active      = True,
            company_id     = company_id,
            prompt         = f"Handle outreach for campaign {campaign_id}",
            additional_context = {"campaign_id": campaign_id},
        )
        try:
            created = await agent_handler.create_agent(new_agent, user_id)
            log.info("Created & activated default agent %s for campaign %s", created["id"], campaign_id)
        except Exception as e:
            log.error("Could not create default agent for campaign %s: %s", campaign_id, e)

@router.post("/create", response_model=CampaignResponse)
async def create_campaign(
    background_tasks: BackgroundTasks,
    campaign_name: str = Form(...),
    description: str | None = Form(None),
    data_mapping: str = Form(...),
    booking_config: str = Form(...),
    automation_config: str = Form(...),
    agent_id: str | None = Form(None),  # Optional agent ID to assign to campaign
    leads_csv: UploadFile = File(...),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    try:
        company = await company_handler.get_company_by_user(current_user.id)
        if not company:
            raise HTTPException(400, "User does not belong to any company")
        company_id = company["id"]

        if not leads_csv.filename.lower().endswith(".csv"):
            raise HTTPException(400, "File must be a CSV")
        csv_text = (await leads_csv.read()).decode("utf-8")

        import json
        try:
            mapping_obj = json.loads(data_mapping)
            booking_obj = json.loads(booking_config)
            automation_obj = json.loads(automation_config)
        except json.JSONDecodeError as e:
            raise HTTPException(400, f"Bad JSON: {e}")

        req = CreateCampaignRequest(
            campaign_name=campaign_name,
            description=description,
            data_mapping=mapping_obj,
            booking=booking_obj,
            automation=automation_obj,
        )

        service = CampaignService()
        campaign = await service.create_campaign(
            campaign_request=req,
            company_id=company_id,
            created_by=current_user.id,
            csv_content=csv_text,
        )

        # Assign agent if agent_id is provided
        if agent_id:
            try:
                await service.assign_agents(campaign.id, [agent_id])
                logger.info(f"Assigned agent {agent_id} to campaign {campaign.id}")
                campaign = campaign.model_copy(update={"agent_id": agent_id})

            except Exception as e:
                logger.error(f"Error assigning agent {agent_id} to campaign {campaign.id}: {e}")
                # Continue without agent assignment - not a critical failure

        background_tasks.add_task(
            setup_campaign_automation,
            campaign.id, booking_obj, automation_obj, current_user.id
        )
        return campaign

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        raise HTTPException(500, f"Failed to create campaign: {e}")



@router.get("/company/{company_id}", response_model=List[CampaignResponse])
async def get_company_campaigns(
    company_id: str,
    limit: int = 50,
    offset: int = 0,
    current_user: UserResponse = Depends(get_current_user),
):

    try:
        campaign_service = CampaignService()
        campaigns = await campaign_service.get_campaigns_by_company(
            company_id=company_id,
            limit=limit,
            offset=offset
        )
        
        return campaigns
        
    except Exception as e:
        logger.error(f"Error fetching campaigns: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch campaigns")

@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: str,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):

    try:
        campaign_service = CampaignService()
        company = await company_handler.get_company_by_user(current_user.id)
        if not company:
            raise HTTPException(400, "User does not belong to any company")
        company_id = company["id"]
        
        campaign = await campaign_service.get_campaign(campaign_id, company_id)
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        return campaign
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching campaign: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch campaign")

async def setup_campaign_automation(
    campaign_id: str,
    booking_config: dict,
    automation_config: dict,
    user_id: str
):

    try:
        logger.info(f"Setting up automation for campaign {campaign_id}")

        if booking_config.get('send_invite_to_team'):
            team_emails = booking_config.get('team_email_addresses', [])
            
            for email in team_emails:
                email_data = {
                    "to": email,
                    "subject": f"New Campaign Created: {campaign_id}",
                    "body": f"A new campaign has been created and you're part of the team.",
                    "html": f"""
                    <h2>New Campaign Created</h2>
                    <p>Campaign ID: {campaign_id}</p>
                    <p>You have been added to the team for this campaign.</p>
                    """
                }

                await send_email_background(email_data, user_id)
        
        # Here you can add more automation setup like:
        # - Schedule initial calls
        # - Setup calendar integrations
        # - Initialize email templates
        
        logger.info(f"Campaign automation setup completed for {campaign_id}")
        
    except Exception as e:
        logger.error(f"Error setting up campaign automation: {str(e)}")

@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: str,
    payload: UpdateCampaignRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]

    svc = CampaignService()
    updated = await svc.update_campaign(campaign_id, company_id, payload)
    if not updated:
        raise HTTPException(404, "Campaign not found")
    return updated


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: str,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    company_id = company["id"]

    svc = CampaignService()
    deleted = await svc.delete_campaign(campaign_id, company_id)
    if not deleted:
        raise HTTPException(404, "Campaign not found")

async def _set_status(
    campaign_id: str,
    company_id: str,
    status: str,
    svc: CampaignService
):
    camp = await svc.get_campaign(campaign_id, company_id)
    if not camp:
        raise HTTPException(404, "Campaign not found")

    if camp.status == status:
        return {"message": f"Campaign {campaign_id} is already {status}"}

    payload = UpdateCampaignRequest(status=status)
    if not await svc.update_campaign(campaign_id, company_id, payload):
        raise HTTPException(500, f"Could not set status to {status}")

    return {"message": f"Campaign {campaign_id} marked {status}"}

@router.post("/{campaign_id}/pause", status_code=200)
async def pause_campaign(
    campaign_id: str,
    current_user:    UserResponse   = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = (await company_handler.get_company_by_user(current_user.id))["id"]
    return await _set_status(campaign_id, company_id, "paused", CampaignService())

@router.post("/{campaign_id}/resume", status_code=200)
async def resume_campaign(
    campaign_id: str,
    current_user:    UserResponse   = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = (await company_handler.get_company_by_user(current_user.id))["id"]
    return await _set_status(campaign_id, company_id, "active", CampaignService())

@router.post("/{campaign_id}/complete", status_code=200)
async def complete_campaign(
    campaign_id: str,
    current_user:    UserResponse   = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = (await company_handler.get_company_by_user(current_user.id))["id"]
    return await _set_status(campaign_id, company_id, "completed", CampaignService())

@router.post("/{campaign_id}/duplicate", status_code=201)
async def duplicate_campaign(
    campaign_id: str,
    current_user:    UserResponse   = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = (await company_handler.get_company_by_user(current_user.id))["id"]
    svc        = CampaignService()

    orig = await svc.get_campaign(campaign_id, company_id)
    if not orig:
        raise HTTPException(404, "Campaign not found")

    new_id = f"CAMP-{uuid.uuid4().hex[:8].upper()}"
    now    = datetime.utcnow()

    req = CreateCampaignRequest(
        campaign_name = f"Copy of {orig.campaign_name}",
        description   = orig.description,
        data_mapping  = orig.data_mapping,
        booking       = orig.booking,
        automation    = orig.automation,
    )

    clone = await svc.create_campaign(
        campaign_request = req,
        company_id       = company_id,
        created_by       = current_user.id,
        csv_content      = "",
    )

    await svc.update_campaign(
        clone.id, company_id,
        UpdateCampaignRequest(
            campaign_name = req.campaign_name,
            status        = "draft",
        )
    )

    return {"message": "Campaign duplicated", "new_campaign": clone}

async def _ensure_campaign(c_id: str, comp_id: str):
    if not await svc.get_campaign(c_id, comp_id):
        raise HTTPException(404, "Campaign not found")

@router.get("/{campaign_id}/agents")
async def list_agents(
    campaign_id: str,
    current: UserResponse = Depends(get_current_user),
    ch: CompanyHandler    = Depends(CompanyHandler),
):
    comp_id = (await ch.get_company_by_user(current.id))["id"]
    await _ensure_campaign(campaign_id, comp_id)
    return await svc.get_agents(campaign_id)

@router.post("/{campaign_id}/agents/assign", status_code=201)
async def assign_agents(
    campaign_id: str,
    body: AgentAssignRequest,
    current: UserResponse = Depends(get_current_user),
    ch: CompanyHandler    = Depends(CompanyHandler),
):
    comp_id = (await ch.get_company_by_user(current.id))["id"]
    await _ensure_campaign(campaign_id, comp_id)
    await svc.assign_agents(campaign_id, body.agent_ids)
    return {"message": f"{len(body.agent_ids)} agent(s) assigned"}

@router.delete("/{campaign_id}/agents/{agent_id}", status_code=204)
async def remove_agent(
    campaign_id: str, agent_id: str,
    current: UserResponse = Depends(get_current_user),
    ch: CompanyHandler    = Depends(CompanyHandler),
):
    comp_id = (await ch.get_company_by_user(current.id))["id"]
    await _ensure_campaign(campaign_id, comp_id)
    if not await svc.unassign_agent(campaign_id, agent_id):
        raise HTTPException(404, "Agent not assigned to this campaign")

@router.put("/{campaign_id}/agents/settings")
async def bulk_update_settings(
    campaign_id: str,
    body: AgentSettingsPayload,
    current: UserResponse = Depends(get_current_user),
    ch: CompanyHandler    = Depends(CompanyHandler),
    agent_handler: AgentHandler = Depends(AgentHandler)
):
    if body.model_dump(exclude_none=True) == {}:
        raise HTTPException(400, "No settings provided")

    comp_id = (await ch.get_company_by_user(current.id))["id"]
    await _ensure_campaign(campaign_id, comp_id)

    updated = await svc.update_agent_settings(
        campaign_id, body, current.id, agent_handler
    )
    return {"message": f"Updated {updated} agent(s)"}

async def _check_owner(c_id: str, user: UserResponse, ch: CompanyHandler):
    comp = await ch.get_company_by_user(user.id)
    if not comp:
        raise HTTPException(400, "User has no company")
    if not await svc.get_campaign(c_id, comp["id"]):
        raise HTTPException(404, "Campaign not found")

@router.get("/{campaign_id}/metrics")
async def realtime_metrics(
    campaign_id: str,
    current: UserResponse = Depends(get_current_user),
    ch: CompanyHandler    = Depends(CompanyHandler),
):
    await _check_owner(campaign_id, current, ch)
    return await svc.get_realtime_metrics(campaign_id)

@router.get("/{campaign_id}/metrics/history")
async def metrics_history(
    campaign_id: str,
    days: int = Query(30, ge=1, le=180),
    current: UserResponse = Depends(get_current_user),
    ch: CompanyHandler    = Depends(CompanyHandler),
):
    await _check_owner(campaign_id, current, ch)
    return await svc.get_metrics_history(campaign_id, days_back=days)

@router.get("/{campaign_id}/call-logs")
async def call_logs(
    campaign_id: str,
    limit: int = Query(100, ge=1, le=1000),
    current: UserResponse = Depends(get_current_user),
    ch: CompanyHandler    = Depends(CompanyHandler),
):
    await _check_owner(campaign_id, current, ch)
    return await svc.get_call_logs(campaign_id, limit)

@router.get("/{campaign_id}/bookings")
async def campaign_bookings(
    campaign_id: str,
    current: UserResponse = Depends(get_current_user),
    ch: CompanyHandler    = Depends(CompanyHandler),
):
    await _check_owner(campaign_id, current, ch)
    return await svc.get_bookings(campaign_id)

@router.get("/analytics/summary")
async def analytics_summary(
    current: UserResponse = Depends(get_current_user),
    ch: CompanyHandler    = Depends(CompanyHandler),
):
    return await svc.get_overall_summary()

async def _ensure_campaign_access(campaign_id: str, user: UserResponse, ch: CompanyHandler):
    comp = await ch.get_company_by_user(user.id)
    if not comp:
        raise HTTPException(400, "User has no company")
    svc = CampaignService()
    if not await svc.get_campaign(campaign_id, comp["id"]):
        raise HTTPException(404, "Campaign not found")
    return comp["id"]

@router.post("/{campaign_id}/leads/upload")
async def upload_leads_csv(
    campaign_id: str,
    leads_csv: UploadFile = File(...),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    await _ensure_campaign_access(campaign_id, current_user, company_handler)
    
    if not leads_csv.filename.lower().endswith('.csv'):
        raise HTTPException(400, "File must be a CSV")
    
    content = await leads_csv.read()
    content_str = content.decode('utf-8')
    
    svc = CampaignService()
    count = await svc.import_leads_csv(campaign_id, content_str, current_user.id)
    
    return {"message": f"Successfully imported {count} leads"}

@router.get("/{campaign_id}/leads")
async def get_leads(
    campaign_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    await _ensure_campaign_access(campaign_id, current_user, company_handler)
    
    svc = CampaignService()
    leads = await svc.get_leads(campaign_id, offset, limit)
    
    return leads

@router.post("/{campaign_id}/leads", status_code=201)
async def add_lead(
    campaign_id: str,
    lead: LeadCreate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    await _ensure_campaign_access(campaign_id, current_user, company_handler)
    
    svc = CampaignService()
    new_lead = await svc.add_lead(campaign_id, lead, current_user.id)
    
    return new_lead

@router.put("/{campaign_id}/leads/{lead_id}")
async def update_lead(
    campaign_id: str,
    lead_id: str,
    lead: LeadUpdate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    await _ensure_campaign_access(campaign_id, current_user, company_handler)
    
    svc = CampaignService()
    updated = await svc.update_lead(campaign_id, lead_id, lead, current_user.id)
    
    if not updated:
        raise HTTPException(404, "Lead not found")
    
    return updated

@router.delete("/{campaign_id}/leads/{lead_id}", status_code=204)
async def delete_lead(
    campaign_id: str,
    lead_id: str,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    await _ensure_campaign_access(campaign_id, current_user, company_handler)
    
    svc = CampaignService()
    deleted = await svc.delete_lead(campaign_id, lead_id)
    
    if not deleted:
        raise HTTPException(404, "Lead not found")

@router.post("/{campaign_id}/leads/bulk")
async def bulk_update_leads(
    campaign_id: str,
    bulk: LeadsBulkUpdate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    await _ensure_campaign_access(campaign_id, current_user, company_handler)
    
    svc = CampaignService()
    updated_count = await svc.bulk_update_leads(campaign_id, bulk)
    
    return {"message": f"Updated {updated_count} lead(s)"}

@router.get("/{campaign_id}/leads/export")
async def export_leads(
    campaign_id: str,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    await _ensure_campaign_access(campaign_id, current_user, company_handler)
    
    svc = CampaignService()
    leads = await svc.get_all_leads(campaign_id)
    
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['id', 'first_name', 'last_name', 'email', 'phone', 'company', 'status', 'call_attempts'])

    for lead in leads:
        writer.writerow([
            lead.get('id'), lead.get('first_name'), lead.get('last_name'),
            lead.get('email'), lead.get('phone'), lead.get('company'),
            lead.get('status'), lead.get('call_attempts', 0)
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={campaign_id}_leads.csv"}
    )

async def _ensure_user_authenticated(current_user: UserResponse, company_handler: CompanyHandler):
    """Helper to ensure user has valid company access"""
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    return company["id"]

@router.post("/csv/parse", response_model=CSVParseResponse)
async def parse_csv(
    csv_file: UploadFile = File(None),
    csv_content: str = Form(None),
    preview_rows: int = Form(5),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    await _ensure_user_authenticated(current_user, company_handler)
    
    if not csv_file and not csv_content:
        raise HTTPException(400, "Either csv_file or csv_content must be provided")
    
    try:
        if csv_file:
            if not csv_file.filename.lower().endswith('.csv'):
                raise HTTPException(400, "File must be a CSV")
            content = (await csv_file.read()).decode('utf-8')
        else:
            content = csv_content
        
        svc = CampaignService()
        result = await svc.parse_csv_content(content, preview_rows)
        
        logger.info(f"CSV parsed successfully: {len(result.headers)} headers, {result.total_rows} rows")
        return result
        
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error parsing CSV: {str(e)}")
        raise HTTPException(500, f"Failed to parse CSV: {str(e)}")

@router.post("/csv/validate", response_model=CSVValidateResponse)
async def validate_csv(
    request: CSVValidateRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    await _ensure_user_authenticated(current_user, company_handler)
    
    try:
        svc = CampaignService()
        result = await svc.validate_csv_data(request)
        
        logger.info(f"CSV validation completed: {result.summary}")
        return result
        
    except Exception as e:
        logger.error(f"Error validating CSV: {str(e)}")
        raise HTTPException(500, f"Failed to validate CSV: {str(e)}")

@router.post("/csv/map-fields", response_model=CSVMapFieldsResponse)
async def map_csv_fields(
    request: CSVMapFieldsRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    await _ensure_user_authenticated(current_user, company_handler)
    
    try:
        svc = CampaignService()
        result = await svc.map_csv_fields(request)
        
        logger.info(f"CSV field mapping completed: {len(result.mapped_fields)} mapped")
        return result
        
    except Exception as e:
        logger.error(f"Error mapping CSV fields: {str(e)}")
        raise HTTPException(500, f"Failed to map CSV fields: {str(e)}")

async def _ensure_campaign_access(campaign_id: str, user: UserResponse, ch: CompanyHandler):
    comp = await ch.get_company_by_user(user.id)
    if not comp:
        raise HTTPException(400, "User has no company")
    svc = CampaignService()
    if not await svc.get_campaign(campaign_id, comp["id"]):
        raise HTTPException(404, "Campaign not found")
    return comp["id"]

@router.get("/{campaign_id}/settings", response_model=CampaignSettings)
async def get_campaign_settings(
    campaign_id: str,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_campaign_access(campaign_id, current_user, company_handler)
    
    svc = CampaignService()
    settings = await svc.get_campaign_settings(campaign_id, company_id)
    
    if not settings:
        raise HTTPException(404, "Campaign settings not found")
    
    return settings

@router.put("/{campaign_id}/settings/booking")
async def update_booking_settings(
    campaign_id: str,
    settings: BookingSettingsUpdate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_campaign_access(campaign_id, current_user, company_handler)
    
    svc = CampaignService()
    updated = await svc.update_booking_settings(campaign_id, company_id, settings)
    
    if not updated:
        raise HTTPException(404, "Failed to update booking settings")
    
    return {"message": "Booking settings updated successfully", "settings": updated}

@router.put("/{campaign_id}/settings/email")
async def update_email_settings(
    campaign_id: str,
    settings: EmailSettingsUpdate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_campaign_access(campaign_id, current_user, company_handler)
    
    svc = CampaignService()
    updated = await svc.update_email_settings(campaign_id, company_id, settings)
    
    if not updated:
        raise HTTPException(404, "Failed to update email settings")
    
    return {"message": "Email settings updated successfully", "settings": updated}

@router.put("/{campaign_id}/settings/call")
async def update_call_settings(
    campaign_id: str,
    settings: CallSettingsUpdate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Update call settings for campaign"""
    company_id = await _ensure_campaign_access(campaign_id, current_user, company_handler)
    
    svc = CampaignService()
    updated = await svc.update_call_settings(campaign_id, company_id, settings)
    
    if not updated:
        raise HTTPException(404, "Failed to update call settings")
    
    return {"message": "Call settings updated successfully", "settings": updated}

@router.put("/{campaign_id}/settings/schedule")
async def update_schedule_settings(
    campaign_id: str,
    settings: ScheduleSettingsUpdate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_campaign_access(campaign_id, current_user, company_handler)
    
    svc = CampaignService()
    updated = await svc.update_schedule_settings(campaign_id, company_id, settings)
    
    if not updated:
        raise HTTPException(404, "Failed to update schedule settings")
    
    return {"message": "Schedule settings updated successfully", "settings": updated}

async def get_current_user_ws(websocket: WebSocket, token: str = Query(...)):
    try:
        from middleware.auth_middleware import verify_token
        user = await verify_token(token)
        return user
    except Exception as e:
        await websocket.close(code=1008, reason="Authentication failed")
        raise

@router.websocket("/{campaign_id}/live")
async def websocket_live_status(
    websocket: WebSocket,
    campaign_id: str,
    token: str = Query(..., description="JWT authentication token"),
):
    try:
        current_user = await get_current_user_ws(websocket, token)

        company_handler = CompanyHandler()
        company = await company_handler.get_company_by_user(current_user.id)
        if not company:
            await websocket.close(code=1008, reason="User has no company")
            return

        ws_service = WebSocketService()
        await manager.connect_live(websocket, campaign_id)

        await ws_service.start_live_updates(campaign_id, company["id"])

        status = await ws_service.get_live_status(campaign_id, company["id"])
        await manager.broadcast_live_status(campaign_id, status)

        while True:
            try:
                message = await websocket.receive_json()
                if message.get("type") == "heartbeat":
                    await websocket.send_json({"type": "heartbeat_ack", "timestamp": datetime.utcnow().isoformat()})
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket live status error: {e}")
        await websocket.close(code=1011, reason="Internal server error")
    finally:
        await manager.disconnect_live(websocket, campaign_id)

@router.websocket("/{campaign_id}/metrics")
async def websocket_metrics(
    websocket: WebSocket,
    campaign_id: str,
    token: str = Query(..., description="JWT authentication token"),
):
    try:
        current_user = await get_current_user_ws(websocket, token)

        company_handler = CompanyHandler()
        company = await company_handler.get_company_by_user(current_user.id)
        if not company:
            await websocket.close(code=1008, reason="User has no company")
            return

        ws_service = WebSocketService()
        await manager.connect_metrics(websocket, campaign_id)

        await ws_service.start_metrics_updates(campaign_id, company["id"])

        metrics = await ws_service.get_current_metrics(campaign_id, company["id"])
        await manager.broadcast_metrics(campaign_id, metrics)

        while True:
            try:
                message = await websocket.receive_json()
                if message.get("type") == "heartbeat":
                    await websocket.send_json({"type": "heartbeat_ack", "timestamp": datetime.utcnow().isoformat()})
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket metrics error: {e}")
        await websocket.close(code=1011, reason="Internal server error")
    finally:
        await manager.disconnect_metrics(websocket, campaign_id)

@router.post("/{campaign_id}/leads/call", status_code=202)
async def initiate_ai_calls(
    campaign_id: str,
    call_request: CallInitiateRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Initiate AI calls for campaign leads"""
    try:
        company_id = await _ensure_campaign_access(campaign_id, current_user, company_handler)
        
        # Validate campaign exists and is callable
        campaign = await svc.get_campaign(campaign_id, company_id)
        if not campaign:
            raise HTTPException(404, "Campaign not found")
            
        if campaign.status not in ["active", "paused"]:
            raise HTTPException(400, f"Campaign must be active or paused to initiate calls, current status: {campaign.status}")
        
        # Get leads to call
        leads_count = await svc.get_callable_leads_count(campaign_id, call_request.lead_filters)
        
        if leads_count == 0:
            raise HTTPException(400, "No callable leads found for this campaign")
        
        # Start calling process in background
        background_tasks.add_task(
            _process_ai_calls,
            campaign_id,
            company_id,
            call_request,
            current_user.id
        )
        
        return {
            "message": f"AI calling initiated for {leads_count} leads",
            "campaign_id": campaign_id,
            "leads_count": leads_count,
            "status": "initiated"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating AI calls for campaign {campaign_id}: {e}")
        raise HTTPException(500, f"Failed to initiate AI calls: {str(e)}")

@router.get("/{campaign_id}/call-status", response_model=CallStatusResponse)
async def get_calling_status(
    campaign_id: str,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Get current calling status for campaign"""
    try:
        company_id = await _ensure_campaign_access(campaign_id, current_user, company_handler)
        
        # Get calling status from service
        status = await svc.get_calling_status(campaign_id, company_id)
        
        if not status:
            # Return default status if no active calling
            return CallStatusResponse(
                campaign_id=campaign_id,
                calling_active=False,
                total_leads=await svc.get_leads_count(campaign_id),
                called_leads=await svc.get_called_leads_count(campaign_id),
                successful_calls=0,
                failed_calls=0,
                active_calls=0,
                queue_size=0,
                estimated_completion=None,
                last_call_at=None
            )
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call status for campaign {campaign_id}: {e}")
        raise HTTPException(500, f"Failed to get call status: {str(e)}")

# Background task for processing AI calls
async def _process_ai_calls(
    campaign_id: str,
    company_id: str,
    call_request: CallInitiateRequest,
    user_id: str
):
    """Background task to process AI calls"""
    try:
        logger.info(f"Starting AI calls for campaign {campaign_id}")
        
        # Update calling status to active
        await svc.set_calling_status(campaign_id, company_id, "active")
        
        # Get leads to call based on filters
        leads = await svc.get_callable_leads(campaign_id, call_request.lead_filters)
        
        total_leads = len(leads)
        successful_calls = 0
        failed_calls = 0
        
        for i, lead in enumerate(leads):
            try:
                # Check if calling should continue (campaign might be paused/stopped)
                campaign = await svc.get_campaign(campaign_id, company_id)
                if campaign.status not in ["active"]:
                    logger.info(f"Stopping calls for campaign {campaign_id}, status: {campaign.status}")
                    break
                
                # Update progress
                await svc.update_calling_progress(
                    campaign_id, 
                    current_lead=i + 1,
                    total_leads=total_leads,
                    successful_calls=successful_calls,
                    failed_calls=failed_calls,
                    progress_percentage=((i + 1) / total_leads) * 100
                )
                
                # Initiate call for lead
                call_result = await svc.initiate_lead_call(
                    campaign_id=campaign_id,
                    lead_id=lead["id"],
                    call_settings=call_request.call_settings,
                    user_id=user_id
                )
                
                if call_result.get("success"):
                    successful_calls += 1
                    logger.info(f"Call successful for lead {lead['id']}")
                else:
                    failed_calls += 1
                    logger.warning(f"Call failed for lead {lead['id']}: {call_result.get('error')}")
                
                # Rate limiting - wait between calls if specified
                if call_request.rate_limit_seconds:
                    await asyncio.sleep(call_request.rate_limit_seconds)
                    
            except Exception as e:
                failed_calls += 1
                logger.error(f"Error calling lead {lead.get('id', 'unknown')}: {e}")
                continue
        
        # Update final status
        await svc.set_calling_status(campaign_id, company_id, "completed")
        await svc.update_calling_progress(
            campaign_id,
            current_lead=total_leads,
            total_leads=total_leads,
            successful_calls=successful_calls,
            failed_calls=failed_calls,
            completed=True,
            progress_percentage=100.0
        )
        
        logger.info(f"AI calling completed for campaign {campaign_id}: {successful_calls}/{total_leads} successful")
        
    except Exception as e:
        logger.error(f"Error in AI calling background task for campaign {campaign_id}: {e}")
        # Mark calling as failed
        await svc.set_calling_status(campaign_id, company_id, "failed")