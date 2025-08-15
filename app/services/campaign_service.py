import uuid
import json
import csv
import io
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.db.postgres_client import get_db_connection
from app.models.campaigns import (
    CreateCampaignRequest, CampaignResponse, CampaignLead,
    DataMapping, CalendarBooking, AutomationSettings
)
import logging

logger = logging.getLogger(__name__)

class CampaignService:
    def __init__(self):
        pass

    def _to_campaign_response(self, row: dict) -> CampaignResponse:

        raw_mapping = row.pop("data_mapping", "[]")
        if isinstance(raw_mapping, str):
            raw_mapping = json.loads(raw_mapping)
        row["data_mapping"] = [DataMapping(**m) for m in raw_mapping]

        raw_booking = row.pop("booking_config", "{}")
        if isinstance(raw_booking, str):
            raw_booking = json.loads(raw_booking)
        row["booking"] = CalendarBooking(**raw_booking)

        raw_auto = row.pop("automation_config", "{}")
        if isinstance(raw_auto, str):
            raw_auto = json.loads(raw_auto)
        row["automation"] = AutomationSettings(**raw_auto)

        return CampaignResponse(**row)

    async def create_campaign(
        self, 
        campaign_request: CreateCampaignRequest,
        company_id: str,
        created_by: str,
        csv_content: str
    ) -> CampaignResponse:
        
        try:
            campaign_id = f"CAMP-{str(uuid.uuid4())[:8].upper()}"
            now = datetime.utcnow()

            leads = await self._process_csv_leads(csv_content, campaign_request.data_mapping)
            
            async with await get_db_connection() as conn:
                campaign_query = """
                INSERT INTO Campaign (
                    id, campaign_name, description, company_id, created_by, 
                    status, leads_count, data_mapping, booking_config, 
                    automation_config, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING *
                """
                
                campaign_record = await conn.fetchrow(
                    campaign_query,
                    campaign_id,
                    campaign_request.campaign_name,
                    campaign_request.description,
                    company_id,
                    created_by,
                    'active',
                    len(leads),
                    json.dumps([mapping.dict() for mapping in campaign_request.data_mapping]),
                    json.dumps(campaign_request.booking.dict()),
                    json.dumps(campaign_request.automation.dict()),
                    now,
                    now
                )

                if leads:
                    await self._create_campaign_leads(conn, campaign_id, leads)
                
                return self._to_campaign_response(dict(campaign_record))
                
        except Exception as e:
            logger.error(f"Error creating campaign: {str(e)}")
            raise Exception(f"Failed to create campaign: {str(e)}")

    async def _process_csv_leads(
        self, 
        csv_content: str, 
        data_mapping: List[DataMapping]
    ) -> List[Dict[str, Any]]:
        
        leads = []
        try:
            csv_reader = csv.DictReader(io.StringIO(csv_content))

            column_mapping = {mapping.csv_column: mapping.mapped_to for mapping in data_mapping}
            
            for row in csv_reader:
                lead = {
                    'id': f"LEAD-{str(uuid.uuid4())[:8].upper()}",
                    'first_name': None,
                    'last_name': None,
                    'email': None,
                    'phone': None,
                    'company': None,
                    'custom_fields': {}
                }

                for csv_col, mapped_field in column_mapping.items():
                    if csv_col in row and row[csv_col]:
                        if mapped_field in ['first_name', 'last_name', 'email', 'phone', 'company']:
                            lead[mapped_field] = row[csv_col].strip()
                        else:
                            lead['custom_fields'][mapped_field] = row[csv_col].strip()
                
                leads.append(lead)
                
        except Exception as e:
            logger.error(f"Error processing CSV: {str(e)}")
            raise Exception(f"Failed to process CSV: {str(e)}")
        
        return leads

    async def _create_campaign_leads(
        self, 
        conn, 
        campaign_id: str, 
        leads: List[Dict[str, Any]]
    ):
        
        lead_query = """
        INSERT INTO Campaign_Lead (
            id, campaign_id, first_name, last_name, email, phone, 
            company, custom_fields, created_at, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """
        
        now = datetime.utcnow()
        for lead in leads:
            await conn.execute(
                lead_query,
                lead['id'],
                campaign_id,
                lead['first_name'],
                lead['last_name'],
                lead['email'],
                lead['phone'],
                lead['company'],
                json.dumps(lead['custom_fields']),
                now,
                now
            )

    async def get_campaign(self, campaign_id: str, company_id: str) -> Optional[CampaignResponse]:      
        try:
            async with await get_db_connection() as conn:
                query = """
                SELECT * FROM Campaign 
                WHERE id = $1 AND company_id = $2
                """
                
                campaign = await conn.fetchrow(query, campaign_id, company_id)
                
                if not campaign:
                    return None
                
                return self._to_campaign_response(dict(campaign))
                
        except Exception as e:
            logger.error(f"Error fetching campaign: {str(e)}")
            return None

    async def get_campaigns_by_company(
        self, 
        company_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[CampaignResponse]:

        try:
            async with await get_db_connection() as conn:
                query = """
                SELECT * FROM Campaign 
                WHERE company_id = $1 
                ORDER BY created_at DESC 
                LIMIT $2 OFFSET $3
                """
                
                campaigns = await conn.fetch(query, company_id, limit, offset)
                
                return [self._to_campaign_response(dict(campaign)) for campaign in campaigns]
                
        except Exception as e:
            logger.error(f"Error fetching campaigns: {str(e)}")
            return []
