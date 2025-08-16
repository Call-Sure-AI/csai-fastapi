import uuid
import json
import csv
import io
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.db.postgres_client import get_db_connection
from app.models.campaigns import (
    CreateCampaignRequest, CampaignResponse, CampaignLead,
    DataMapping, CalendarBooking, AutomationSettings, UpdateCampaignRequest, 
    AgentAssignRequest,
    AgentSettingsPayload,
)
from datetime import datetime, date
from app.models.schemas import AgentUpdate
import logging
from app.models.schemas import LeadCreate, LeadUpdate, Lead, LeadsBulkUpdate

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

    async def update_campaign(
        self,
        campaign_id: str,
        company_id: str,
        payload: UpdateCampaignRequest
    ) -> CampaignResponse | None:

        set_clauses: list[str] = []
        values: list[Any]      = []

        if payload.campaign_name is not None:
            set_clauses.append(f"campaign_name = ${len(values)+1}")
            values.append(payload.campaign_name)

        if payload.description is not None:
            set_clauses.append(f"description   = ${len(values)+1}")
            values.append(payload.description)

        if payload.data_mapping is not None:
            set_clauses.append(f"data_mapping   = ${len(values)+1}")
            values.append(json.dumps([m.dict() for m in payload.data_mapping]))

        if payload.booking is not None:
            set_clauses.append(f"booking_config = ${len(values)+1}")
            values.append(json.dumps(payload.booking.dict()))

        if payload.automation is not None:
            set_clauses.append(f"automation_config = ${len(values)+1}")
            values.append(json.dumps(payload.automation.dict()))

        if not set_clauses:
            return await self.get_campaign(campaign_id, company_id)

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")

        id_placeholder      = f"${len(values)+1}"
        company_placeholder = f"${len(values)+2}"
        values.extend([campaign_id, company_id])

        query = f"""
        UPDATE Campaign
        SET {', '.join(set_clauses)}
        WHERE id = {id_placeholder}
        AND company_id = {company_placeholder}
        RETURNING *;
        """

        async with await get_db_connection() as conn:
            row = await conn.fetchrow(query, *values)
            if not row:
                return None
            return self._to_campaign_response(dict(row))

    async def delete_campaign(self, campaign_id: str, company_id: str) -> bool:
        async with await get_db_connection() as conn:
            result = await conn.execute(
                "DELETE FROM Campaign WHERE id = $1 AND company_id = $2",
                campaign_id, company_id
            )
            return result.startswith("DELETE 1")

    async def get_agents(self, campaign_id: str) -> list[dict]:
        sql = """
            SELECT a.*
            FROM   campaign_agents ca
            JOIN   "Agent" a ON a.id = ca.agent_id
            WHERE  ca.campaign_id = $1
        """
        async with await get_db_connection() as conn:
            rows = await conn.fetch(sql, campaign_id)
        return [dict(r) for r in rows]

    async def assign_agents(self, campaign_id: str, agent_ids: list[str]) -> None:
        async with await get_db_connection() as conn:
            for aid in agent_ids:
                await conn.execute(
                    """INSERT INTO campaign_agents (campaign_id, agent_id)
                       VALUES ($1,$2)               ON CONFLICT DO NOTHING""",
                    campaign_id, aid
                )

    async def unassign_agent(self, campaign_id: str, agent_id: str) -> bool:
        async with await get_db_connection() as conn:
            res = await conn.execute(
                "DELETE FROM campaign_agents WHERE campaign_id=$1 AND agent_id=$2",
                campaign_id, agent_id
            )
        return res.startswith("DELETE 1")

    async def update_agent_settings(
        self,
        campaign_id: str,
        settings: AgentSettingsPayload,
        user_id: str,
        agent_handler,
    ) -> int:
        async with await get_db_connection() as conn:
            ids = await conn.fetch(
                "SELECT agent_id FROM campaign_agents WHERE campaign_id=$1",
                campaign_id,
            )
        agent_ids = [r["agent_id"] for r in ids]

        if not agent_ids:
            return 0

        patch = AgentUpdate(
            is_active=settings.is_active,
            max_response_tokens=settings.max_response_tokens,
            temperature=settings.temperature,
        )
        jobs = [
            agent_handler.update_agent(aid, patch, user_id)
            for aid in agent_ids
        ]
        await asyncio.gather(*jobs)
        return len(agent_ids)

    async def get_realtime_metrics(self, campaign_id: str) -> Dict[str, Any]:
        sql = "SELECT * FROM v_campaign_realtime WHERE campaign_id = $1"
        async with await get_db_connection() as conn:
            row = await conn.fetchrow(sql, campaign_id)
        return dict(row) if row else {}

    async def get_metrics_history(
        self, campaign_id: str, days_back: int = 30
    ) -> List[Dict[str, Any]]:
        sql = """
            SELECT *
            FROM   campaign_metrics_daily
            WHERE  campaign_id = $1
              AND  date >= $2
            ORDER  BY date
        """
        async with await get_db_connection() as conn:
            rows = await conn.fetch(sql, campaign_id, date.today().fromordinal(date.today().toordinal()-days_back))
        return [dict(r) for r in rows]

    async def get_overall_summary(self) -> List[Dict[str, Any]]:
        sql = """
            SELECT
              campaign_id,
              SUM(calls_handled)     AS calls,
              SUM(calls_success)     AS successes,
              SUM(bookings_made)     AS bookings,
              SUM(revenue_generated) AS revenue
            FROM campaign_metrics_daily
            GROUP BY campaign_id
        """
        async with await get_db_connection() as conn:
            rows = await conn.fetch(sql)
        return [dict(r) for r in rows]

    async def get_call_logs(self, campaign_id: str, limit: int = 100) -> List[Dict]:
        sql = """
            SELECT *
            FROM   call_log
            WHERE  campaign_id = $1
            ORDER  BY started_at DESC
            LIMIT  $2
        """
        async with await get_db_connection() as conn:
            rows = await conn.fetch(sql, campaign_id, limit)
        return [dict(r) for r in rows]

    async def get_bookings(self, campaign_id: str) -> List[Dict]:
        sql = """
            SELECT *
            FROM   booking
            WHERE  campaign_id = $1
            ORDER  BY slot_start DESC
        """
        async with await get_db_connection() as conn:
            rows = await conn.fetch(sql, campaign_id)
        return [dict(r) for r in rows]

    async def import_leads_csv(self, campaign_id: str, csv_content: str, user_id: str) -> int:
            reader = csv.DictReader(io.StringIO(csv_content))
            leads = []
            
            for row in reader:
                lead_id = f"LEAD-{uuid.uuid4().hex[:8].upper()}"
                leads.append((
                    lead_id,
                    campaign_id,
                    row.get('first_name', ''),
                    row.get('last_name', ''),
                    row.get('email', ''),
                    row.get('phone', ''),
                    row.get('company', ''),
                    '{}',
                    datetime.utcnow(),
                    datetime.utcnow()
                ))
            
            async with await get_db_connection() as conn:
                await conn.executemany("""
                    INSERT INTO Campaign_Lead 
                    (id, campaign_id, first_name, last_name, email, phone, company, custom_fields, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """, leads)
            
            return len(leads)
    
    async def get_leads(self, campaign_id: str, offset: int = 0, limit: int = 100) -> List[Dict]:
        async with await get_db_connection() as conn:
            rows = await conn.fetch("""
                SELECT * FROM Campaign_Lead 
                WHERE campaign_id = $1 
                ORDER BY created_at DESC 
                OFFSET $2 LIMIT $3
            """, campaign_id, offset, limit)
        return [dict(row) for row in rows]
    
    async def get_all_leads(self, campaign_id: str) -> List[Dict]:
        async with await get_db_connection() as conn:
            rows = await conn.fetch("""
                SELECT * FROM Campaign_Lead 
                WHERE campaign_id = $1 
                ORDER BY created_at DESC
            """, campaign_id)
        return [dict(row) for row in rows]
    
    async def add_lead(self, campaign_id: str, lead: LeadCreate, user_id: str) -> Dict:
        lead_id = f"LEAD-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow()
        
        async with await get_db_connection() as conn:
            row = await conn.fetchrow("""
                INSERT INTO Campaign_Lead 
                (id, campaign_id, first_name, last_name, email, phone, company, custom_fields, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING *
            """, lead_id, campaign_id, lead.first_name, lead.last_name, 
                 lead.email, lead.phone, lead.company, 
                 json.dumps(lead.custom_fields or {}), now, now)
        
        return dict(row)
    
    async def update_lead(self, campaign_id: str, lead_id: str, lead: LeadUpdate, user_id: str) -> Dict:
        set_clauses = []
        values = []
        
        updates = lead.dict(exclude_unset=True)
        for field, value in updates.items():
            if field == 'custom_fields':
                set_clauses.append(f"custom_fields = ${len(values)+1}::jsonb")
                values.append(json.dumps(value))
            else:
                set_clauses.append(f"{field} = ${len(values)+1}")
                values.append(value)
        
        if not set_clauses:
            async with await get_db_connection() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM Campaign_Lead WHERE id = $1 AND campaign_id = $2",
                    lead_id, campaign_id
                )
            return dict(row) if row else None
        
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        values.extend([lead_id, campaign_id])
        
        query = f"""
            UPDATE Campaign_Lead 
            SET {', '.join(set_clauses)}
            WHERE id = ${len(values)-1} AND campaign_id = ${len(values)}
            RETURNING *
        """
        
        async with await get_db_connection() as conn:
            row = await conn.fetchrow(query, *values)
        
        return dict(row) if row else None
    
    async def delete_lead(self, campaign_id: str, lead_id: str) -> bool:
        async with await get_db_connection() as conn:
            result = await conn.execute(
                "DELETE FROM Campaign_Lead WHERE id = $1 AND campaign_id = $2",
                lead_id, campaign_id
            )
        return result.startswith("DELETE 1")
    
    async def bulk_update_leads(self, campaign_id: str, bulk: LeadsBulkUpdate) -> int:
        if not bulk.lead_ids:
            return 0
        
        set_clauses = []
        values = []
        
        updates = bulk.updates.dict(exclude_unset=True)
        for field, value in updates.items():
            if field == 'custom_fields':
                set_clauses.append(f"{field} = ${len(values)+1}::jsonb")
                values.append(json.dumps(value))
            else:
                set_clauses.append(f"{field} = ${len(values)+1}")
                values.append(value)
        
        if not set_clauses:
            return 0
        
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")

        placeholders = ', '.join(f'${i}' for i in range(len(values)+1, len(values)+1+len(bulk.lead_ids)))
        values.extend(bulk.lead_ids)
        values.append(campaign_id)
        
        query = f"""
            UPDATE Campaign_Lead 
            SET {', '.join(set_clauses)}
            WHERE id IN ({placeholders}) AND campaign_id = ${len(values)}
        """
        
        async with await get_db_connection() as conn:
            result = await conn.execute(query, *values)
        
        return int(result.split()[-1]) if result.startswith("UPDATE") else 0
