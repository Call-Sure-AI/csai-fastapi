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
from datetime import datetime, date
from app.models.schemas import AgentUpdate
import logging
from app.models.schemas import LeadCreate, LeadUpdate, Lead, LeadsBulkUpdate
from app.models.schemas import (
    CSVParseResponse, CSVValidateRequest, CSVValidateResponse, 
    CSVValidationError, CSVMapFieldsRequest, CSVMapFieldsResponse, FieldMapping
)

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