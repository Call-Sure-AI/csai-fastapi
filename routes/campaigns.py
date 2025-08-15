from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from typing import List, Optional
import uuid
import logging
from datetime import datetime

from app.models.schemas import UserResponse
from app.models.campaigns import CreateCampaignRequest, CampaignResponse
from middleware.auth_middleware import get_current_user
from app.services.campaign_service import CampaignService

from routes.email import send_email_background
from handlers.company_handler import CompanyHandler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

@router.post("/create", response_model=CampaignResponse)
async def create_campaign(
    background_tasks: BackgroundTasks,
    campaign_name: str = Form(...),
    description: str | None = Form(None),
    data_mapping: str = Form(...),
    booking_config: str = Form(...),
    automation_config: str = Form(...),
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
            mapping_obj    = json.loads(data_mapping)
            booking_obj    = json.loads(booking_config)
            automation_obj = json.loads(automation_config)
        except json.JSONDecodeError as e:
            raise HTTPException(400, f"Bad JSON: {e}")

        req = CreateCampaignRequest(
            campaign_name = campaign_name,
            description   = description,
            data_mapping  = mapping_obj,
            booking       = booking_obj,
            automation    = automation_obj,
        )

        service  = CampaignService()
        campaign = await service.create_campaign(
            campaign_request = req,
            company_id       = company_id,
            created_by       = current_user.id,
            csv_content      = csv_text,
        )

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
