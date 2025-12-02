# app\services\campaign_service.py
import uuid
import json
import csv
import io
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.db.postgres_client import get_db_connection
from app.models.campaigns import (
    CreateCampaignRequest, CampaignResponse, CampaignLead,
    DataMapping, CalendarBooking, AutomationSettings, UpdateCampaignRequest, 
    AgentAssignRequest,
    AgentSettingsPayload,
)
from app.models.schemas import (
    CampaignSettings, BookingSettings, EmailSettings, CallSettings, ScheduleSettings,
    BookingSettingsUpdate, EmailSettingsUpdate, CallSettingsUpdate, ScheduleSettingsUpdate
)
from app.models.schemas import CallInitiateRequest, CallStatusResponse
from datetime import datetime, date
from app.models.schemas import AgentUpdate
import logging
from app.models.schemas import LeadCreate, LeadUpdate, Lead, LeadsBulkUpdate
from app.models.schemas import (
    CSVParseResponse, CSVValidateRequest, CSVValidateResponse, 
    CSVValidationError, CSVMapFieldsRequest, CSVMapFieldsResponse, FieldMapping
)
import asyncio
import httpx

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

        row["agent_id"] = row.get("agent_id")

        return CampaignResponse(**row)


    async def create_campaign(
        self, 
        campaign_request: CreateCampaignRequest,
        company_id: str,
        created_by: str,
        csv_content: str,
        s3_url: str,
        agent_id: str | None = None
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
                    automation_config, leads_file_url, agent_id, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                RETURNING *
                """
                
                campaign_record = await conn.fetchrow(
                    campaign_query,
                    campaign_id,
                    campaign_request.campaign_name,
                    campaign_request.description,
                    company_id,
                    created_by,
                    'queued',
                    len(leads),
                    json.dumps([mapping.dict() for mapping in campaign_request.data_mapping]),
                    json.dumps(campaign_request.booking.dict()),
                    json.dumps(campaign_request.automation.dict()),
                    s3_url,
                    agent_id or campaign_request.agent_id,
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
                    'country_code': None,
                    'custom_fields': {},
                    'call_attempts': 0,
                    'last_call_at': None,
                    'status': 'pending'
                }

                for csv_col, mapped_field in column_mapping.items():
                    if csv_col in row and row[csv_col] and row[csv_col].strip() != "":
                        value = row[csv_col].strip()
                        if mapped_field in ['first_name', 'last_name', 'email', 'phone', 'company', 'country_code']:
                            lead[mapped_field] = value
                        else:
                            lead['custom_fields'][mapped_field] = value
                
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
        INSERT INTO campaign_lead (
            id,
            campaign_id,
            first_name,
            last_name,
            email,
            phone,
            company,
            custom_fields,
            call_attempts,
            last_call_at,
            status,
            created_at,
            updated_at,
            country_code
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10, $11, $12, $13, $14
        )
        ON CONFLICT (id) DO NOTHING
        """
        
        now = datetime.utcnow()
        for lead in leads:
            await conn.execute(
                lead_query,
                lead['id'],
                campaign_id,
                lead.get('first_name'),
                lead.get('last_name'),
                lead.get('email'),
                lead.get('phone'),
                lead.get('company'),
                json.dumps(lead.get('custom_fields', {})),
                lead.get('call_attempts', 0),
                lead.get('last_call_at'),
                lead.get('status', 'pending'),
                now,
                now,
                lead.get('country_code')
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
        values: list[Any] = []

        if payload.campaign_name is not None:
            set_clauses.append(f"campaign_name = ${len(values)+1}")
            values.append(payload.campaign_name)

        if payload.description is not None:
            set_clauses.append(f"description = ${len(values)+1}")
            values.append(payload.description)

        if payload.agent_id is not None:
            set_clauses.append(f"agent_id = ${len(values)+1}")
            values.append(payload.agent_id)

        if payload.data_mapping is not None:
            set_clauses.append(f"data_mapping = ${len(values)+1}")
            values.append(json.dumps([m.dict() for m in payload.data_mapping]))

        if payload.booking is not None:
            set_clauses.append(f"booking_config = ${len(values)+1}")
            values.append(json.dumps(payload.booking.dict()))
    
        if payload.status is not None:
            set_clauses.append(f"status = ${len(values)+1}")
            values.append(payload.status)

        if payload.automation is not None:
            set_clauses.append(f"automation_config = ${len(values)+1}")
            values.append(json.dumps(payload.automation.dict()))

        if not set_clauses:
            return await self.get_campaign(campaign_id, company_id)

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")

        id_placeholder = f"${len(values)+1}"
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
                lead = await self.get_or_create_lead(row)
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
                await self.add_lead_to_campaign(lead['id'], campaign_id)
            
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

    def _detect_csv_delimiter(self, content: str) -> str:
        sample = content[:1024]
        sniffer = csv.Sniffer()
        try:
            delimiter = sniffer.sniff(sample, delimiters=',;\t|').delimiter
            return delimiter
        except:
            return ','
    
    async def parse_csv_content(self, csv_content: str, preview_rows: int = 5) -> CSVParseResponse:
        delimiter = self._detect_csv_delimiter(csv_content)
        
        reader = csv.reader(io.StringIO(csv_content), delimiter=delimiter)
        rows = list(reader)
        
        if not rows:
            raise ValueError("CSV file is empty")
        
        headers = rows[0] if rows else []
        data_rows = rows[1:] if len(rows) > 1 else []
        preview = data_rows[:preview_rows]
        
        return CSVParseResponse(
            headers=headers,
            preview_rows=preview,
            total_rows=len(data_rows),
            detected_delimiter=delimiter
        )
    
    async def validate_csv_data(self, request: CSVValidateRequest) -> CSVValidateResponse:
        errors = []
        delimiter = self._detect_csv_delimiter(request.csv_content)
        
        reader = csv.DictReader(io.StringIO(request.csv_content), delimiter=delimiter)
        headers = reader.fieldnames or []

        if request.expected_headers:
            missing_headers = set(request.expected_headers) - set(headers)
            if missing_headers:
                errors.append(CSVValidationError(
                    row=0,
                    column="headers",
                    error=f"Missing expected headers: {', '.join(missing_headers)}",
                    value=str(headers)
                ))
        
        row_count = 0
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        phone_pattern = re.compile(r'^[\+]?[1-9]?[\d\s\-\(\)]{7,15}$')
        
        for row_num, row in enumerate(reader, start=2):
            row_count += 1

            if request.required_fields:
                for field in request.required_fields:
                    if field in row and not row[field].strip():
                        errors.append(CSVValidationError(
                            row=row_num,
                            column=field,
                            error="Required field is empty",
                            value=row[field]
                        ))
            
            if 'email' in row and row['email'].strip():
                if not email_pattern.match(row['email'].strip()):
                    errors.append(CSVValidationError(
                        row=row_num,
                        column='email',
                        error="Invalid email format",
                        value=row['email']
                    ))

            if 'phone' in row and row['phone'].strip():
                if not phone_pattern.match(row['phone'].strip()):
                    errors.append(CSVValidationError(
                        row=row_num,
                        column='phone',
                        error="Invalid phone format",
                        value=row['phone']
                    ))
        
        return CSVValidateResponse(
            is_valid=len(errors) == 0,
            errors=errors,
            summary={
                "total_rows": row_count,
                "total_errors": len(errors),
                "headers_found": headers,
                "delimiter_used": delimiter
            }
        )
    
    async def map_csv_fields(self, request: CSVMapFieldsRequest) -> CSVMapFieldsResponse:
        """Handle CSV field mapping logic"""
        mapped_fields = {}
        unmapped_columns = []
        missing_required = []

        mapping_dict = {m.csv_column: m.system_field for m in request.mappings}
        required_fields = {m.system_field for m in request.mappings if m.required}

        for header in request.csv_headers:
            if header in mapping_dict:
                mapped_fields[header] = mapping_dict[header]
            else:
                unmapped_columns.append(header)

        mapped_system_fields = set(mapped_fields.values())
        missing_required = list(required_fields - mapped_system_fields)

        preview_mapping = {}
        for mapping in request.mappings:
            if mapping.csv_column in request.csv_headers:
                preview_mapping[mapping.csv_column] = {
                    "maps_to": mapping.system_field,
                    "required": mapping.required,
                    "transform": mapping.transform,
                    "example_transform": self._apply_transform("Sample Value", mapping.transform)
                }
        
        return CSVMapFieldsResponse(
            mapped_fields=mapped_fields,
            unmapped_columns=unmapped_columns,
            missing_required=missing_required,
            preview_mapping=preview_mapping
        )
    
    def _apply_transform(self, value: str, transform: Optional[str]) -> str:
        if not transform or not value:
            return value
        
        if transform == "upper":
            return value.upper()
        elif transform == "lower":
            return value.lower()
        elif transform == "trim":
            return value.strip()
        elif transform == "title":
            return value.title()
        else:
            return value

    async def get_campaign_settings(self, campaign_id: str, company_id: str) -> Optional[CampaignSettings]:
        async with await get_db_connection() as conn:
            row = await conn.fetchrow("""
                SELECT booking_config, automation_config, 
                       email_settings, call_settings, schedule_settings
                FROM Campaign 
                WHERE id = $1 AND company_id = $2
            """, campaign_id, company_id)
        
        if not row:
            return None

        booking_data = json.loads(row['booking_config']) if row['booking_config'] else {}

        automation_data = json.loads(row['automation_config']) if row['automation_config'] else {}
        email_data = json.loads(row['email_settings']) if row.get('email_settings') else automation_data.get('email', {})
        call_data = json.loads(row['call_settings']) if row.get('call_settings') else automation_data.get('call', {})
        schedule_data = json.loads(row['schedule_settings']) if row.get('schedule_settings') else automation_data.get('schedule', {})

        booking_settings = BookingSettings(**self._apply_booking_defaults(booking_data))
        email_settings = EmailSettings(**self._apply_email_defaults(email_data))
        call_settings = CallSettings(**self._apply_call_defaults(call_data))
        schedule_settings = ScheduleSettings(**self._apply_schedule_defaults(schedule_data))
        
        return CampaignSettings(
            booking=booking_settings,
            email=email_settings,
            call=call_settings,
            schedule=schedule_settings
        )
    
    async def update_booking_settings(
        self, 
        campaign_id: str, 
        company_id: str, 
        settings: BookingSettingsUpdate
    ) -> Optional[BookingSettings]:

        current = await self.get_campaign_settings(campaign_id, company_id)
        if not current:
            return None

        updated_data = current.booking.dict()
        updates = settings.dict(exclude_unset=True)
        updated_data.update(updates)

        async with await get_db_connection() as conn:
            await conn.execute("""
                UPDATE Campaign 
                SET booking_config = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2 AND company_id = $3
            """, json.dumps(updated_data), campaign_id, company_id)
        
        return BookingSettings(**updated_data)
    
    async def update_email_settings(
        self, 
        campaign_id: str, 
        company_id: str, 
        settings: EmailSettingsUpdate
    ) -> Optional[EmailSettings]:

        current = await self.get_campaign_settings(campaign_id, company_id)
        if not current:
            return None
        
        updated_data = current.email.dict()
        updates = settings.dict(exclude_unset=True)
        updated_data.update(updates)
        
        async with await get_db_connection() as conn:
            await conn.execute("""
                UPDATE Campaign 
                SET email_settings = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2 AND company_id = $3
            """, json.dumps(updated_data), campaign_id, company_id)
        
        return EmailSettings(**updated_data)
    
    async def update_call_settings(
        self, 
        campaign_id: str, 
        company_id: str, 
        settings: CallSettingsUpdate
    ) -> Optional[CallSettings]:

        current = await self.get_campaign_settings(campaign_id, company_id)
        if not current:
            return None
        
        updated_data = current.call.dict()
        updates = settings.dict(exclude_unset=True)
        updated_data.update(updates)
        
        async with await get_db_connection() as conn:
            await conn.execute("""
                UPDATE Campaign 
                SET call_settings = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2 AND company_id = $3
            """, json.dumps(updated_data), campaign_id, company_id)
        
        return CallSettings(**updated_data)
    
    def _json_serialize(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: self._json_serialize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._json_serialize(i) for i in obj]
        elif hasattr(obj, 'isoformat'):
            return obj.isoformat()
        else:
            return obj
    
    async def update_schedule_settings(
        self, 
        campaign_id: str, 
        company_id: str, 
        settings: ScheduleSettingsUpdate
    ) -> Optional[ScheduleSettings]:
        current = await self.get_campaign_settings(campaign_id, company_id)
        if not current:
            return None

        updated_data = self._json_serialize(current.schedule.dict())

        updates = settings.dict(exclude_unset=True)
        serialized_updates = self._json_serialize(updates)

        updated_data.update(serialized_updates)
        
        async with await get_db_connection() as conn:
            await conn.execute("""
                UPDATE Campaign 
                SET schedule_settings = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2 AND company_id = $3
            """, json.dumps(updated_data), campaign_id, company_id)
        
        return ScheduleSettings(**updated_data)
    
    def _apply_booking_defaults(self, data: Dict[str, Any]) -> Dict[str, Any]:
        defaults = {
            "calendar_type": "google",
            "meeting_duration_minutes": 30,
            "buffer_time_minutes": 15,
            "send_invite_to_lead": True,
            "send_invite_to_team": True,
            "team_email_addresses": [],
            "booking_window_days": 30,
            "min_notice_hours": 2,
            "max_bookings_per_day": None
        }
        defaults.update(data)
        return defaults
    
    def _apply_email_defaults(self, data: Dict[str, Any]) -> Dict[str, Any]:
        defaults = {
            "template": "Hi {{first_name}}, let's connect!",
            "subject_line": "Quick chat about your business needs",
            "from_name": "Sales Team",
            "from_email": "sales@company.com",
            "enable_followup": True,
            "followup_delay_hours": 24,
            "max_followup_attempts": 3,
            "unsubscribe_link": True,
            "track_opens": True,
            "track_clicks": True
        }
        defaults.update(data)
        return defaults
    
    def _apply_call_defaults(self, data: Dict[str, Any]) -> Dict[str, Any]:
        defaults = {
            "script": "Hello {{first_name}}, this is {{agent_name}} calling about...",
            "max_call_attempts": 3,
            "call_interval_hours": 24,
            "preferred_calling_hours": {
                "start": "09:00",
                "end": "17:00", 
                "timezone": "UTC"
            },
            "voicemail_script": None,
            "call_recording_enabled": True,
            "auto_dial_enabled": False,
            "caller_id": None
        }
        defaults.update(data)
        return defaults
    
    def _apply_schedule_defaults(self, data: Dict[str, Any]) -> Dict[str, Any]:
        defaults = {
            "working_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "working_hours_start": "09:00:00",
            "working_hours_end": "17:00:00",
            "timezone": "UTC",
            "lunch_break_start": "12:00:00",
            "lunch_break_end": "13:00:00",
            "max_concurrent_calls": 5,
            "campaign_active_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "pause_on_holidays": True
        }
        defaults.update(data)
        return defaults

    async def get_callable_leads_count(self, campaign_id: str, filters: Dict[str, Any] = None) -> int:
        """Get count of leads that can be called"""
        async with (await get_db_connection()) as conn:
            query = """
                SELECT COUNT(*) as count
                FROM leads
                WHERE campaign_id = $1 
                AND status IN ('new', 'callback_requested', 'no_answer')
                AND call_attempts < 3
                AND phone IS NOT NULL
            """
            params = [campaign_id]
            
            # Add additional filters if provided
            if filters:
                if filters.get("max_call_attempts"):
                    query += " AND call_attempts <= $2"
                    params.append(filters["max_call_attempts"])
            
            result = await conn.fetchrow(query, *params)
            return result["count"] if result else 0

    async def get_callable_leads(self, campaign_id: str, filters: Dict[str, Any] = None) -> List[Dict]:
        """Get leads that can be called"""
        async with (await get_db_connection()) as conn:
            query = """
                SELECT id, first_name, last_name, email, phone, company, status, call_attempts
                FROM leads
                WHERE campaign_id = $1 
                AND status IN ('new', 'callback_requested', 'no_answer')
                AND call_attempts < 3
                AND phone IS NOT NULL
                ORDER BY created_at ASC
            """
            params = [campaign_id]
            
            if filters and filters.get("limit"):
                query += f" LIMIT ${len(params) + 1}"
                params.append(filters["limit"])
            
            results = await conn.fetch(query, *params)
            return [dict(row) for row in results]

    async def get_calling_status(self, campaign_id: str, company_id: str) -> Optional[CallStatusResponse]:
        """Get current calling status for campaign"""
        async with (await get_db_connection()) as conn:
            # Check for active calling session
            status_query = """
                SELECT * FROM campaign_call_status 
                WHERE campaign_id = $1 AND company_id = $2
            """
            status_result = await conn.fetchrow(status_query, campaign_id, company_id)
            
            if not status_result:
                return None
            
            # Get lead counts
            leads_query = """
                SELECT 
                    COUNT(*) as total_leads,
                    COUNT(CASE WHEN call_attempts > 0 THEN 1 END) as called_leads,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_calls,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_calls
                FROM leads
                WHERE campaign_id = $1
            """
            leads_result = await conn.fetchrow(leads_query, campaign_id)
            
            return CallStatusResponse(
                campaign_id=campaign_id,
                calling_active=status_result["status"] == "active",
                total_leads=leads_result["total_leads"] if leads_result else 0,
                called_leads=leads_result["called_leads"] if leads_result else 0,
                successful_calls=leads_result["successful_calls"] if leads_result else 0,
                failed_calls=leads_result["failed_calls"] if leads_result else 0,
                active_calls=status_result.get("active_calls", 0),
                queue_size=status_result.get("queue_size", 0),
                estimated_completion=status_result.get("estimated_completion"),
                last_call_at=status_result.get("last_call_at"),
                progress_percentage=status_result.get("progress_percentage", 0),
                current_lead_position=status_result.get("current_lead_position", 0)
            )

    async def set_calling_status(self, campaign_id: str, company_id: str, status: str):
        """Set calling status for campaign"""
        async with (await get_db_connection()) as conn:
            await conn.execute("""
                INSERT INTO campaign_call_status (campaign_id, company_id, status, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (campaign_id, company_id)
                DO UPDATE SET status = $3, updated_at = NOW()
            """, campaign_id, company_id, status)

    async def update_calling_progress(self, campaign_id: str, **kwargs):
        """Update calling progress"""
        async with (await get_db_connection()) as conn:
            set_clauses = []
            params = []
            param_idx = 1
            
            for key, value in kwargs.items():
                if key in ['current_lead', 'total_leads', 'successful_calls', 'failed_calls', 'progress_percentage', 'completed']:
                    if key == 'current_lead':
                        set_clauses.append(f"current_lead_position = ${param_idx}")
                    elif key == 'completed' and value:
                        set_clauses.append(f"status = 'completed'")
                        continue
                    else:
                        set_clauses.append(f"{key} = ${param_idx}")
                    params.append(value)
                    param_idx += 1
            
            if set_clauses:
                query = f"""
                    UPDATE campaign_call_status 
                    SET {', '.join(set_clauses)}, updated_at = NOW()
                    WHERE campaign_id = ${param_idx}
                """
                params.append(campaign_id)
                await conn.execute(query, *params)

    async def _initiate_lead_call(self, campaign_id: str, lead_id: str | None, to_number: str | None, call_sid: str | None, call_status: str | None):
        """
        Persist a call attempt for a lead in campaign_lead table.
        Writes: call_attempts, last_call_at, status, last_call_sid, updated_at.
        """
        try:
            async with await get_db_connection() as conn:
                if lead_id:
                    row = await conn.fetchrow(
                        """
                        UPDATE campaign_lead
                        SET call_attempts = COALESCE(call_attempts, 0) + 1,
                            last_call_at = NOW(),
                            status = $3,
                            last_call_sid = $4,
                            updated_at = NOW()
                        WHERE id = $1 AND campaign_id = $2
                        RETURNING id, campaign_id, phone, call_attempts, last_call_at, status, last_call_sid
                        """,
                        lead_id,
                        campaign_id,
                        call_status or 'no-answer',
                        call_sid
                    )
                else:
                    phone_norm = to_number.lstrip('+') if to_number else None
                    row = await conn.fetchrow(
                        """
                        UPDATE campaign_lead
                        SET call_attempts = COALESCE(call_attempts, 0) + 1,
                            last_call_at = NOW(),
                            status = $3,
                            last_call_sid = $4,
                            updated_at = NOW()
                        WHERE campaign_id = $1 AND (phone = $2 OR phone = $5)
                        RETURNING id, campaign_id, phone, call_attempts, last_call_at, status, last_call_sid
                        """,
                        campaign_id,
                        to_number,
                        call_status or 'no-answer',
                        call_sid,
                        phone_norm
                    )

                if row:
                    rd = dict(row)
                    logger.info("[activate] Persisted call attempt for lead %s phone=%s attempts=%s status=%s sid=%s",
                                rd.get("id"), rd.get("phone"), rd.get("call_attempts"), rd.get("status"), rd.get("last_call_sid"))
                    return rd
                else:
                    logger.warning("[activate] _initiate_lead_call: no matching campaign_lead row found for lead_id=%s phone=%s", lead_id, to_number)
                    return None

        except Exception as e:
            logger.exception("[activate] Error persisting call attempt for lead_id=%s phone=%s: %s", lead_id, to_number, e)
            raise

    async def get_leads_count(self, campaign_id: str) -> int:
        """Get total leads count for campaign"""
        async with (await get_db_connection()) as conn:
            result = await conn.fetchrow(
                "SELECT COUNT(*) as count FROM leads WHERE campaign_id = $1", 
                campaign_id
            )
            return result["count"] if result else 0

    async def get_called_leads_count(self, campaign_id: str) -> int:
        """Get called leads count for campaign"""
        async with (await get_db_connection()) as conn:
            result = await conn.fetchrow(
                "SELECT COUNT(*) as count FROM leads WHERE campaign_id = $1 AND call_attempts > 0", 
                campaign_id
            )
            return result["count"] if result else 0

    async def get_or_create_lead(self, lead_data: Dict[str, Any], company_id: str) -> Dict[str, Any]:
        """Get existing lead or create new one in master leads table"""
        
        email = lead_data.get('email', '').strip().lower()
        if not email:
            raise ValueError("Email is required for lead creation")
        
        async with await get_db_connection() as conn:
            # Check if lead exists for this company
            existing_lead = await conn.fetchrow("""
                SELECT * FROM leads 
                WHERE company_id = $1 AND LOWER(email) = $2
            """, uuid.UUID(company_id), email)
            
            if existing_lead:
                # Update existing lead with new data if provided
                update_fields = []
                update_values = []
                param_count = 1
                
                for field in ['first_name', 'last_name', 'phone', 'lead_company']:
                    if lead_data.get(field) and not existing_lead[field]:
                        update_fields.append(f"{field} = ${param_count}")
                        update_values.append(lead_data[field])
                        param_count += 1
                
                if update_fields:
                    update_fields.append("updated_at = CURRENT_TIMESTAMP")
                    update_values.extend([uuid.UUID(company_id), email])
                    
                    query = f"""
                        UPDATE leads 
                        SET {', '.join(update_fields)}
                        WHERE company_id = ${param_count} AND LOWER(email) = ${param_count + 1}
                        RETURNING *
                    """
                    result = await conn.fetchrow(query, *update_values)
                    return dict(result)
                
                return dict(existing_lead)
            
            else:
                # Create new lead
                lead_id = uuid.uuid4()
                now = datetime.utcnow()
                
                result = await conn.fetchrow("""
                    INSERT INTO leads (
                        id, company_id, email, first_name, last_name, 
                        phone, lead_company, custom_fields, source, 
                        created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
                    ) RETURNING *
                """,
                    lead_id,
                    uuid.UUID(company_id),
                    email,
                    lead_data.get('first_name'),
                    lead_data.get('last_name'),
                    lead_data.get('phone'),
                    lead_data.get('company'),  # Maps to lead_company column
                    json.dumps(lead_data.get('custom_fields', {})),
                    lead_data.get('source', 'csv_import'),
                    now,
                    now
                )
                
                return dict(result)
    
    async def add_lead_to_campaign(self, lead_id: str, campaign_id: str, lead_data: Dict[str, Any] = None) -> None:
        """Add a lead to a campaign (create association)"""
        
        async with await get_db_connection() as conn:
            # Check if association already exists
            existing = await conn.fetchrow("""
                SELECT id FROM campaign_leads 
                WHERE campaign_id = $1 AND lead_id = $2
            """, campaign_id, uuid.UUID(lead_id) if isinstance(lead_id, str) else lead_id)
            
            if not existing:
                await conn.execute("""
                    INSERT INTO campaign_leads (
                        campaign_id, lead_id, campaign_status, 
                        campaign_custom_fields, added_to_campaign_at
                    ) VALUES (
                        $1, $2, $3, $4, $5
                    )
                """,
                    campaign_id,
                    uuid.UUID(lead_id) if isinstance(lead_id, str) else lead_id,
                    'pending',
                    json.dumps(lead_data.get('custom_fields', {})) if lead_data else '{}',
                    datetime.utcnow()
                )
    
    async def import_leads_csv_v2(self, campaign_id: str, csv_content: str, user_id: str, company_id: str) -> Dict[str, Any]:
        """Import leads using new lead management system"""
        
        reader = csv.DictReader(io.StringIO(csv_content))
        
        imported = 0
        updated = 0
        failed = 0
        errors = []
        
        async with await get_db_connection() as conn:
            async with conn.transaction():
                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Prepare lead data
                        lead_data = {
                            'email': row.get('email', '').strip(),
                            'first_name': row.get('first_name', '').strip(),
                            'last_name': row.get('last_name', '').strip(),
                            'phone': row.get('phone', '').strip(),
                            'company': row.get('company', '').strip(),
                            'source': 'csv_import',
                            'custom_fields': {}
                        }
                        
                        # Add any extra fields to custom_fields
                        standard_fields = {'email', 'first_name', 'last_name', 'phone', 'company'}
                        for field, value in row.items():
                            if field not in standard_fields and value:
                                lead_data['custom_fields'][field] = value
                        
                        # Get or create lead in master table
                        lead = await self.get_or_create_lead(lead_data, company_id)
                        
                        if lead.get('created_at') == lead.get('updated_at'):
                            imported += 1
                        else:
                            updated += 1
                        
                        # Add to campaign
                        await self.add_lead_to_campaign(lead['id'], campaign_id, lead_data)
                        
                    except Exception as e:
                        failed += 1
                        errors.append({
                            'row': row_num,
                            'error': str(e),
                            'data': row
                        })
                        logger.error(f"Error importing row {row_num}: {e}")
        
        return {
            'imported': imported,
            'updated': updated,
            'failed': failed,
            'total': imported + updated + failed,
            'errors': errors[:10]
        }

    async def get_campaign_leads(self, campaign_id: str, status: str = "pending") -> list[dict]:
        """
        Fetch leads for a campaign from campaign_lead table.
        By default returns leads with status = 'pending'.
        """
        try:
            async with await get_db_connection() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, campaign_id, first_name, last_name, email, phone, company,
                           custom_fields, call_attempts, last_call_at, status, created_at, updated_at, country_code
                    FROM campaign_lead
                    WHERE campaign_id = $1 AND status = $2
                    ORDER BY created_at ASC
                    """,
                    campaign_id,
                    status
                )
                return [dict(r) for r in rows] if rows else []
        except Exception as e:
            logger.error(f"Error fetching campaign leads for {campaign_id}: {e}")
            raise

    async def log_campaign_status_change(self, campaign_id: str, status: str) -> dict | None:
        activity_id = f"ACT-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow()
        try:
            async with await get_db_connection() as conn:
                rec = await conn.fetchrow(
                    """
                    INSERT INTO campaign_status_history (id, campaign_id, status, changed_at)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id, campaign_id, status, changed_at
                    """,
                    activity_id,
                    campaign_id,
                    status,
                    now
                )
                return dict(rec) if rec else None
        except Exception as e:
            logger.exception("Failed to log campaign status change for %s -> %s: %s", campaign_id, status, e)
            return None

    async def mark_campaign_lead_call(self, campaign_id: str, lead_id: str | None, success: bool, phone: str | None = None):
        try:
            async with await get_db_connection() as conn:
                if lead_id:
                    row = await conn.fetchrow(
                        """
                        UPDATE campaign_lead
                        SET call_attempts = COALESCE(call_attempts, 0) + 1,
                            last_call_at = NOW(),
                            status = CASE WHEN $3 THEN 'contacted' ELSE COALESCE(status, 'no_answer') END,
                            updated_at = NOW()
                        WHERE id = $1 AND campaign_id = $2
                        RETURNING id, campaign_id, phone, call_attempts, last_call_at, status
                        """,
                        lead_id,
                        campaign_id,
                        success
                    )
                else:
                    phone_norm = None
                    if phone:
                        phone_norm = phone.lstrip('+')
                    row = await conn.fetchrow(
                        """
                        UPDATE campaign_lead
                        SET call_attempts = COALESCE(call_attempts, 0) + 1,
                            last_call_at = NOW(),
                            status = CASE WHEN $3 THEN 'contacted' ELSE COALESCE(status, 'no_answer') END,
                            updated_at = NOW()
                        WHERE campaign_id = $1 AND (phone = $2 OR phone = $4)
                        RETURNING id, campaign_id, phone, call_attempts, last_call_at, status
                        """,
                        campaign_id,
                        phone,
                        success,
                        phone_norm
                    )

                return dict(row) if row else None

        except Exception as e:
            logger.error(f"Error marking campaign lead call (campaign={campaign_id}, lead_id={lead_id}, phone={phone}): {e}")
            raise
 
    async def get_campaign_leads_v2(self, campaign_id: str, offset: int = 0, limit: int = 100) -> List[Dict]:
        """Get leads for a campaign using new structure"""
        
        async with await get_db_connection() as conn:
            rows = await conn.fetch("""
                SELECT 
                    l.*,
                    cl.campaign_status,
                    cl.call_attempts,
                    cl.last_call_at,
                    cl.email_attempts,
                    cl.campaign_custom_fields,
                    cl.added_to_campaign_at
                FROM campaign_leads cl
                JOIN leads l ON l.id = cl.lead_id
                WHERE cl.campaign_id = $1
                ORDER BY cl.added_to_campaign_at DESC
                OFFSET $2 LIMIT $3
            """, campaign_id, offset, limit)
            
            return [dict(row) for row in rows]
    
    async def update_campaign_lead_status(self, campaign_id: str, lead_id: str, status: str) -> bool:
        """Update lead status within a campaign"""
        
        async with await get_db_connection() as conn:
            result = await conn.execute("""
                UPDATE campaign_leads 
                SET campaign_status = $1, updated_at = CURRENT_TIMESTAMP
                WHERE campaign_id = $2 AND lead_id = $3
            """, status, campaign_id, uuid.UUID(lead_id) if isinstance(lead_id, str) else lead_id)
            
            return result.startswith("UPDATE 1")


    # ADD THESE METHODS TO CampaignService class

    async def get_slot_configuration(self, campaign_id: str, company_id: str) -> Optional[Dict]:
        """Get slot configuration for a campaign"""
        async with await get_db_connection() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM campaign_slot_configuration
                WHERE campaign_id = $1 AND company_id = $2
            """, campaign_id, company_id)
            
            if not row:
                # Return default configuration
                return {
                    "slot_mode": "dynamic",
                    "business_hours": {
                        "mon": {"start": "09:00", "end": "18:00"},
                        "tue": {"start": "09:00", "end": "18:00"},
                        "wed": {"start": "09:00", "end": "18:00"},
                        "thu": {"start": "09:00", "end": "18:00"},
                        "fri": {"start": "09:00", "end": "18:00"}
                    },
                    "timezone": "UTC",
                    "slot_duration_minutes": 30,
                    "buffer_minutes": 0,
                    "max_bookings_per_slot": 1,
                    "allow_overbooking": False,
                    "allow_custom_times": False,
                    "predefined_slots": [],
                    "closer_shifts": [],
                    "allow_multiple_bookings_per_customer": False
                }
            
            # Parse JSONB fields
            config = dict(row)
            if config.get('business_hours'):
                config['business_hours'] = json.loads(config['business_hours'])
            if config.get('predefined_slots'):
                config['predefined_slots'] = json.loads(config['predefined_slots'])
            if config.get('closer_shifts'):
                config['closer_shifts'] = json.loads(config['closer_shifts'])
            
            return config

    async def create_or_update_slot_configuration(
        self,
        campaign_id: str,
        company_id: str,
        config: Dict[str, Any]
    ) -> Dict:
        """Create or update slot configuration"""
        
        config_id = f"SLOT-{uuid.uuid4().hex[:8].upper()}"
        
        async with await get_db_connection() as conn:
            # Check if config exists
            existing = await conn.fetchrow("""
                SELECT id FROM campaign_slot_configuration
                WHERE campaign_id = $1
            """, campaign_id)
            
            # Prepare JSONB fields
            business_hours_json = json.dumps(config.get('business_hours', {}))
            predefined_slots_json = json.dumps(config.get('predefined_slots', []))
            closer_shifts_json = json.dumps(config.get('closer_shifts', []))
            
            if existing:
                # Update
                row = await conn.fetchrow("""
                    UPDATE campaign_slot_configuration
                    SET 
                        slot_mode = $1,
                        business_hours = $2::jsonb,
                        timezone = $3,
                        slot_duration_minutes = $4,
                        buffer_minutes = $5,
                        max_bookings_per_slot = $6,
                        allow_overbooking = $7,
                        allow_custom_times = $8,
                        predefined_slots = $9::jsonb,
                        closer_shifts = $10::jsonb,
                        allow_multiple_bookings_per_customer = $11,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE campaign_id = $12
                    RETURNING *
                """,
                    config.get('slot_mode', 'dynamic'),
                    business_hours_json,
                    config.get('timezone', 'UTC'),
                    config.get('slot_duration_minutes', 30),
                    config.get('buffer_minutes', 0),
                    config.get('max_bookings_per_slot', 1),
                    config.get('allow_overbooking', False),
                    config.get('allow_custom_times', False),
                    predefined_slots_json,
                    closer_shifts_json,
                    config.get('allow_multiple_bookings_per_customer', False),
                    campaign_id
                )
            else:
                # Insert
                row = await conn.fetchrow("""
                    INSERT INTO campaign_slot_configuration (
                        id, campaign_id, company_id, slot_mode, business_hours,
                        timezone, slot_duration_minutes, buffer_minutes,
                        max_bookings_per_slot, allow_overbooking, allow_custom_times,
                        predefined_slots, closer_shifts, allow_multiple_bookings_per_customer
                    ) VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9, $10, $11, $12::jsonb, $13::jsonb, $14)
                    RETURNING *
                """,
                    config_id, campaign_id, company_id,
                    config.get('slot_mode', 'dynamic'),
                    business_hours_json,
                    config.get('timezone', 'UTC'),
                    config.get('slot_duration_minutes', 30),
                    config.get('buffer_minutes', 0),
                    config.get('max_bookings_per_slot', 1),
                    config.get('allow_overbooking', False),
                    config.get('allow_custom_times', False),
                    predefined_slots_json,
                    closer_shifts_json,
                    config.get('allow_multiple_bookings_per_customer', False)
                )
            
            result = dict(row)
            # Parse JSONB fields for response
            result['business_hours'] = json.loads(result['business_hours'])
            result['predefined_slots'] = json.loads(result['predefined_slots'])
            result['closer_shifts'] = json.loads(result['closer_shifts'])
            
            return result

async def _process_campaign_on_activate(campaign_id: str, company_id: str, user_id: str):
    svc = CampaignService()
    try:
        campaign = await svc.get_campaign(campaign_id, company_id)
        if not campaign:
            logger.error(f"[activate] Campaign not found: {campaign_id}")
            return

        #automation = getattr(campaign, "automation", {}) or campaign.automation if hasattr(campaign, "automation") else {}
        agent_id = getattr(campaign, "agent_id", None) or (campaign.agent_id if hasattr(campaign, "agent_id") else None)

        automation_model = getattr(campaign, "automation", None)

        if automation_model is None:
            automation = {}
        else:
            try:
                automation = automation_model.dict()
            except Exception:
                automation = dict(automation_model) if isinstance(automation_model, dict) else {}

        max_call_attempts = int(automation.get("max_call_attempts", 3))
        call_interval_minutes = float(automation.get("call_interval_minutes", 5))
        max_concurrent_calls = int(automation.get("max_concurrent_calls", 5))
        delay_between_calls = float(automation.get("delay_between_calls", 2))
        call_script = automation.get("call_script", "")
        enable_followup = bool(automation.get("enable_followup_emails", False))

        leads = await svc.get_campaign_leads(campaign_id, status="pending")
        if not leads:
            logger.info(f"[activate] No pending leads found for campaign {campaign_id}")
            return

        sem = asyncio.Semaphore(max_concurrent_calls)

        async def dial_once_and_get_sid(lead: dict) -> dict:
            """
            Initiates a single outbound call attempt and returns:
            {"success": bool, "call_sid": str|None, "processor_status": str|None, "to_number": str, "lead_id": str}
            """
            lead_id = lead.get("id")
            phone_raw = (lead.get("phone") or "").strip()
            country_code_raw = str(lead.get("country_code") or "").strip()
            if not phone_raw:
                logger.warning("[activate] Skipping lead %s - no phone", lead_id)
                return {"success": False, "call_sid": None, "processor_status": None, "to_number": None, "lead_id": lead_id}

            phone_digits = re.sub(r'\D', '', phone_raw)
            cc_digits = re.sub(r'\D', '', country_code_raw)
            if phone_digits.startswith("0") and cc_digits:
                phone_digits = phone_digits.lstrip("0")

            if cc_digits:
                to_number = f"+{cc_digits}{phone_digits}"
            else:
                to_number = f"+{phone_digits}" if not phone_raw.startswith("+") else phone_raw

            customer_name = (lead.get("first_name") or "").strip()
            payload = {
                "to_number": to_number,
                "company_id": company_id,
                "agent_id": agent_id,
                "customer_name": customer_name,
                "campaign_id": campaign_id,
                "call_script": call_script
            }

            try:
                async with sem:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.post(
                            "https://processor.callsure.ai/api/v1/twilio-elevenlabs/initiate-outbound-call",
                            json=payload,
                            headers={"Content-Type": "application/json"}
                        )
                try:
                    j = resp.json()
                except Exception:
                    j = {}

                processor_status = j.get("status") or (j.get("success") and "queued") or None
                call_sid = j.get("call_sid")

                if resp.status_code in (200, 201, 202) and (processor_status or call_sid):
                    try:
                        await svc._initiate_lead_call(campaign_id=campaign_id, lead_id=lead_id, to_number=to_number, call_sid=call_sid, call_status=processor_status)
                    except Exception as e:
                        logger.warning("[activate] _initiate_lead_call failed (initial): %s", e)
                    logger.info("[activate] Call initiated for lead %s -> %s (campaign %s) sid=%s status=%s", lead_id, to_number, campaign_id, call_sid, processor_status)
                    return {"success": True, "call_sid": call_sid, "processor_status": processor_status, "to_number": to_number, "lead_id": lead_id}
                else:
                    try:
                        await svc._initiate_lead_call(campaign_id=campaign_id, lead_id=lead_id, to_number=to_number, call_sid=call_sid, call_status=processor_status or 'no-answer')
                    except Exception:
                        pass
                    logger.warning("[activate] Call API returned %s for %s: %s", resp.status_code, to_number, resp.text)
                    return {"success": False, "call_sid": call_sid, "processor_status": processor_status, "to_number": to_number, "lead_id": lead_id}
            except Exception as e:
                logger.exception("[activate] Error initiating call for lead %s to %s: %s", lead_id, to_number, e)
                try:
                    await svc._initiate_lead_call(campaign_id=campaign_id, lead_id=lead_id, to_number=to_number, call_sid=None, call_status='no-answer')
                except Exception:
                    pass
                return {"success": False, "call_sid": None, "processor_status": None, "to_number": to_number, "lead_id": lead_id}

        async def process_with_retries(lead: dict):
            lead_id = lead.get("id")
            attempts = 0
            remaining_attempts = max_call_attempts

            last_call_sid = None
            last_to_number = None
            last_processor_status = None

            while remaining_attempts > 0:
                attempts += 1
                remaining_attempts -= 1

                res = await dial_once_and_get_sid(lead)
                last_call_sid = res.get("call_sid")
                last_to_number = res.get("to_number")
                last_processor_status = res.get("processor_status")

                if not last_call_sid:
                    logger.warning("[activate] No call_sid for lead %s attempt %s; remaining=%s", lead_id, attempts, remaining_attempts)
                    if remaining_attempts <= 0:
                        logger.info("[activate] Exhausted attempts for lead %s without call_sid", lead_id)
                        break
                    await asyncio.sleep(call_interval_minutes * 60)
                    continue

                logger.info("[activate] Waiting %s minute(s) to check Call table for call_sid=%s (lead=%s)", call_interval_minutes, last_call_sid, lead_id)
                await asyncio.sleep(call_interval_minutes * 60)

                try:
                    async with await get_db_connection() as conn:
                        call_row = await conn.fetchrow('SELECT status FROM "Call" WHERE call_sid = $1', last_call_sid)
                        if call_row:
                            call_table_status = (call_row.get("status") or "").lower()
                        else:
                            logger.warning("[activate] No row in Call table for call_sid=%s; treating as no-answer for retry decision", last_call_sid)
                            call_table_status = "no-answer"
                except Exception as e:
                    logger.exception("[activate] Error querying Call table for call_sid=%s: %s", last_call_sid, e)
                    call_table_status = "no-answer"

                logger.info("[activate] Call table status for sid=%s -> %s (lead=%s)", last_call_sid, call_table_status, lead_id)

                if call_table_status == "no-answer":
                    if remaining_attempts <= 0:
                        logger.info("[activate] No remaining attempts for lead %s; stop retrying", lead_id)
                        break
                    logger.info("[activate] Retrying lead %s (attempts so far=%s)", lead_id, attempts)
                    continue
                else:
                    logger.info("[activate] Terminal/answered status for lead %s: %s — no retry", lead_id, call_table_status)
                    break

        tasks = [asyncio.create_task(process_with_retries(ld)) for ld in leads]
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"[activate] Completed dialing for campaign {campaign_id}")

    except Exception as e:
        logger.exception(f"[activate] Unhandled exception for campaign {campaign_id}: {e}")
