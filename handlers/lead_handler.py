import csv
import io
import json
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import pandas as pd
from fastapi import HTTPException, UploadFile
import asyncio
import aiohttp
import logging
from app.db.postgres_client import get_db_connection
from app.db.queries.lead_queries import LeadQueries
from app.models.leads import (
    Lead, LeadImportRequest, LeadImportResponse,
    LeadEnrichmentRequest, LeadScoreRequest, LeadScoreResponse,
    LeadSegment, LeadDistributionRequest, LeadDistributionResponse,
    LeadNurturingRequest, LeadJourney, LeadFilter,
    BulkLeadUpdate, LeadMergeRequest, LeadStatus, LeadPriority
)

logger = logging.getLogger(__name__)

class LeadHandler:
    def __init__(self):
        self.queries = LeadQueries()
        
    async def import_leads(self, source: str, file: Optional[UploadFile] = None, 
                          request: Optional[LeadImportRequest] = None,
                          company_id: str = None, user_id: str = None) -> LeadImportResponse:
        """Import leads from various sources"""
        logger.info(f"Import leads called - source: {source}, company_id: {company_id}, user_id: {user_id}")
        
        if not company_id:
            raise HTTPException(status_code=400, detail="Company ID is required for lead import")
        
        leads_data = []
        
        if source == "csv" and file:
            leads_data = await self._parse_csv(file)
        elif source == "excel" and file:
            leads_data = await self._parse_excel(file)
        elif source == "api" and request and request.data:
            leads_data = request.data
        elif source == "crm" and request:
            leads_data = await self._sync_from_crm(request.options)
        else:
            raise HTTPException(status_code=400, detail="Invalid import source or missing data")
        
        logger.info(f"Parsed {len(leads_data)} leads from {source}")
        
        # Apply mapping if provided
        if request and request.mapping:
            leads_data = self._apply_mapping(leads_data, request.mapping)
        
        # Cleanse and validate data
        cleaned_leads = self._cleanse_leads(leads_data)
        logger.info(f"Cleaned {len(cleaned_leads)} leads")
        
        # Import to database with company_id
        result = await self._bulk_insert_leads(cleaned_leads, company_id, user_id)
        
        return result

    async def _parse_csv(self, file: UploadFile) -> List[Dict[str, Any]]:
        """Parse CSV file and return lead data"""
        try:
            content = await file.read()
            logger.info(f"CSV file size: {len(content)} bytes")
            
            # Reset file position for multiple reads if needed
            await file.seek(0)
            
            decoded = content.decode('utf-8')
            # Log first 500 chars to see the structure
            logger.info(f"CSV preview: {decoded[:500]}")
            
            reader = csv.DictReader(io.StringIO(decoded))
            leads = list(reader)
            
            logger.info(f"Parsed {len(leads)} leads from CSV")
            if leads:
                logger.info(f"First lead: {leads[0]}")
                logger.info(f"CSV headers: {list(leads[0].keys())}")
            
            return leads
            
        except Exception as e:
            logger.error(f"Error parsing CSV: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

    
    async def _parse_excel(self, file: UploadFile) -> List[Dict[str, Any]]:
        """Parse Excel file and return lead data"""
        content = await file.read()
        df = pd.read_excel(io.BytesIO(content))
        df = df.where(pd.notnull(df), None)
        return df.to_dict('records')
    
    async def _sync_from_crm(self, options: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Sync leads from external CRM"""
        crm_type = options.get('crm_type', 'salesforce')
        api_key = options.get('api_key')
        endpoint = options.get('endpoint')
        
        if not api_key or not endpoint:
            raise HTTPException(status_code=400, detail="CRM sync requires api_key and endpoint")
        
        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': f'Bearer {api_key}'}
            async with session.get(endpoint, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('leads', [])
                else:
                    raise HTTPException(status_code=500, detail="Failed to sync from CRM")
    
    def _apply_mapping(self, data: List[Dict], mapping: Dict[str, str]) -> List[Dict]:
        """Apply field mapping to imported data"""
        mapped_data = []
        for record in data:
            mapped_record = {}
            for target_field, source_field in mapping.items():
                if source_field in record:
                    mapped_record[target_field] = record[source_field]
            mapped_data.append(mapped_record)
        return mapped_data
    
    def _cleanse_leads(self, leads: List[Dict]) -> List[Dict]:
        """Cleanse and validate lead data"""
        cleaned = []
        for lead in leads:
            # Basic cleaning
            if 'email' in lead and lead['email']:
                # Handle email - convert to string and clean
                email_value = str(lead['email']).strip().lower()
                if email_value and '@' in email_value:
                    lead['email'] = email_value
                else:
                    continue  # Skip if no valid email
            else:
                continue  # Skip if no email field
            
            if 'first_name' in lead and lead['first_name']:
                # Convert to string and clean
                lead['first_name'] = str(lead['first_name']).strip().title()
            
            if 'last_name' in lead and lead['last_name']:
                # Convert to string and clean
                lead['last_name'] = str(lead['last_name']).strip().title()
            
            if 'phone' in lead and lead['phone'] is not None:
                # Handle phone - could be int, float, or string
                phone_value = lead['phone']
                
                # Convert to string first
                if isinstance(phone_value, (int, float)):
                    # Remove decimal point if it's a float
                    phone_str = str(int(phone_value))
                else:
                    phone_str = str(phone_value)
                
                # Clean the phone string - keep only digits and +
                cleaned_phone = ''.join(filter(lambda x: x.isdigit() or x == '+', phone_str))
                
                # If it's just digits and long enough, keep it
                if len(cleaned_phone) >= 7:  # Minimum phone number length
                    lead['phone'] = cleaned_phone
                else:
                    lead['phone'] = None
            
            # Handle company field (might be called 'company' in CSV/Excel)
            if 'company' in lead and lead['company']:
                lead['company'] = str(lead['company']).strip()
            
            # Handle other fields that might be numbers
            for field in ['job_title', 'industry', 'country', 'city', 'state']:
                if field in lead and lead[field] is not None:
                    lead[field] = str(lead[field]).strip()
            
            cleaned.append(lead)
        
        return cleaned
    
    async def _bulk_insert_leads(self, leads: List[Dict], company_id: str, user_id: str = None) -> LeadImportResponse:
        """Bulk insert leads into database"""
        logger.info(f"Starting bulk insert for {len(leads)} leads for company {company_id}")
        
        if not leads:
            return LeadImportResponse(
                imported=0,
                failed=0,
                duplicates=0,
                errors=[{"error": "No valid leads found in file", "details": "The file appears to be empty or contains no valid data"}],  # Changed to dict
                lead_ids=[]
            )
        
        imported = 0
        failed = 0
        duplicates = 0
        errors = []
        lead_ids = []
        
        async with await get_db_connection() as conn:
            for idx, lead in enumerate(leads):
                lead_id = f"LEAD-{str(uuid.uuid4())[:8].upper()}"
                now = datetime.utcnow()
                
                # Ensure email exists and is valid
                email = lead.get('email', '').strip()
                if not email:
                    logger.warning(f"Skipping lead {idx + 1}: No email provided")
                    failed += 1
                    errors.append({
                        "error": "Missing email",
                        "row": idx + 1,
                        "data": lead  # Include the problematic data for debugging
                    })
                    continue
                
                try:
                    # The query for PostgreSQL with proper parameter placeholders
                    query = """
                        INSERT INTO leads (
                            id, company_id, email, first_name, last_name, phone, 
                            lead_company, job_title, industry, country, city, state,
                            source, status, priority, score, tags, custom_fields, 
                            created_by, created_at, updated_at
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                            $13, $14, $15, $16, $17::jsonb, $18::jsonb, $19, $20, $21
                        ) ON CONFLICT (company_id, email) DO UPDATE SET
                            first_name = COALESCE(EXCLUDED.first_name, leads.first_name),
                            last_name = COALESCE(EXCLUDED.last_name, leads.last_name),
                            phone = COALESCE(EXCLUDED.phone, leads.phone),
                            lead_company = COALESCE(EXCLUDED.lead_company, leads.lead_company),
                            updated_at = EXCLUDED.updated_at
                        RETURNING id, email
                    """
                    
                    result = await conn.fetchrow(
                        query,
                        lead_id,                           # $1
                        company_id,                        # $2
                        email.lower(),                     # $3
                        lead.get('first_name', '').strip() or None,  # $4
                        lead.get('last_name', '').strip() or None,   # $5
                        lead.get('phone', '').strip() or None,       # $6
                        lead.get('company', '').strip() or None,     # $7 - maps to lead_company
                        lead.get('job_title', '').strip() or None,   # $8
                        lead.get('industry', '').strip() or None,    # $9
                        lead.get('country', '').strip() or None,     # $10
                        lead.get('city', '').strip() or None,        # $11
                        lead.get('state', '').strip() or None,       # $12
                        'csv_import',                      # $13 - source
                        'new',                             # $14 - status
                        'medium',                          # $15 - priority
                        0,                                 # $16 - score
                        json.dumps([]),                    # $17 - tags
                        json.dumps({}),                    # $18 - custom_fields
                        user_id,                           # $19 - created_by
                        now,                               # $20 - created_at
                        now                                # $21 - updated_at
                    )
                    
                    if result:
                        imported += 1
                        lead_ids.append(result['id'])
                        logger.info(f"Successfully imported lead {idx + 1}: {result['email']}")
                        
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error inserting lead {idx + 1} ({email}): {error_msg}")
                    
                    if 'duplicate' in error_msg.lower() or 'conflict' in error_msg.lower():
                        duplicates += 1
                        logger.info(f"Lead {email} already exists (duplicate)")
                    else:
                        failed += 1
                        errors.append({
                            "error": error_msg[:200],  # Truncate long error messages
                            "lead": email,
                            "row": idx + 1
                        })
        
        logger.info(f"Import complete - Imported: {imported}, Failed: {failed}, Duplicates: {duplicates}")
        
        return LeadImportResponse(
            imported=imported,
            failed=failed,
            duplicates=duplicates,
            errors=errors[:10],  # Return only first 10 errors to avoid huge responses
            lead_ids=lead_ids
        )
    
    async def get_leads(self, filters: LeadFilter, company_id: str) -> Dict[str, Any]:
        """Get filtered and paginated leads for a specific company"""
        async with await get_db_connection() as conn:
            # Build filter conditions - always filter by company_id
            filter_conditions = [f"company_id = $1"]
            params = [company_id]
            param_count = 2
            
            if filters.status:
                filter_conditions.append(f"status = ANY(${param_count})")
                params.append(filters.status)
                param_count += 1
            
            if filters.source:
                filter_conditions.append(f"source = ANY(${param_count})")
                params.append(filters.source)
                param_count += 1
            
            # ... rest of filters ...
            
            # Build query
            where_clause = " AND ".join(filter_conditions)
            
            # Get total count
            count_query = f"SELECT COUNT(*) as count FROM leads WHERE {where_clause}"
            total_result = await conn.fetchrow(count_query, *params)
            
            # Get paginated results
            offset = (filters.page - 1) * filters.page_size
            
            leads_query = f"""
                SELECT * FROM leads 
                WHERE {where_clause}
                ORDER BY {filters.sort_by} {filters.sort_order}
                LIMIT ${param_count} OFFSET ${param_count + 1}
            """
            
            params.extend([filters.page_size, offset])
            leads = await conn.fetch(leads_query, *params)
            
            return {
                "leads": [dict(lead) for lead in leads],
                "total": total_result['count'] if total_result else 0,
                "page": filters.page,
                "page_size": filters.page_size,
                "total_pages": (total_result['count'] + filters.page_size - 1) // filters.page_size if total_result else 0
            }
    
    async def get_lead_by_id(self, lead_id: str) -> Optional[Lead]:
        """Get a specific lead by ID"""
        async with await get_db_connection() as conn:
            result = await conn.fetchrow(
                self.queries.get_lead_by_id(),
                lead_id
            )
            
            if result:
                # Convert the result to a dictionary
                lead_data = dict(result)
                
                # Parse JSON fields if they're strings
                if isinstance(lead_data.get('tags'), str):
                    try:
                        lead_data['tags'] = json.loads(lead_data['tags'])
                    except (json.JSONDecodeError, TypeError):
                        lead_data['tags'] = []
                
                if isinstance(lead_data.get('custom_fields'), str):
                    try:
                        lead_data['custom_fields'] = json.loads(lead_data['custom_fields'])
                    except (json.JSONDecodeError, TypeError):
                        lead_data['custom_fields'] = {}
                
                # Ensure tags and custom_fields have default values if None
                if lead_data.get('tags') is None:
                    lead_data['tags'] = []
                if lead_data.get('custom_fields') is None:
                    lead_data['custom_fields'] = {}
                
                return Lead(**lead_data)
            return None
    
    async def update_lead(self, lead_id: str, updates: Dict[str, Any]) -> Lead:
        """Update a single lead"""
        async with await get_db_connection() as conn:
            # Build update query dynamically
            set_clauses = []
            values = []
            param_count = 1
            
            for field, value in updates.items():
                if field in ['tags', 'custom_fields']:
                    set_clauses.append(f"{field} = ${param_count}::jsonb")
                    values.append(json.dumps(value))
                else:
                    set_clauses.append(f"{field} = ${param_count}")
                    values.append(value)
                param_count += 1
            
            if not set_clauses:
                return await self.get_lead_by_id(lead_id)
            
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            values.append(lead_id)
            
            query = f"""
                UPDATE leads 
                SET {', '.join(set_clauses)}
                WHERE id = ${param_count}
                RETURNING *
            """
            
            result = await conn.fetchrow(query, *values)
            
            if result:
                # Convert the result to a dictionary
                lead_data = dict(result)
                
                # Parse JSON fields if they're strings
                if isinstance(lead_data.get('tags'), str):
                    try:
                        lead_data['tags'] = json.loads(lead_data['tags'])
                    except (json.JSONDecodeError, TypeError):
                        lead_data['tags'] = []
                
                if isinstance(lead_data.get('custom_fields'), str):
                    try:
                        lead_data['custom_fields'] = json.loads(lead_data['custom_fields'])
                    except (json.JSONDecodeError, TypeError):
                        lead_data['custom_fields'] = {}
                
                # Ensure tags and custom_fields have default values if None
                if lead_data.get('tags') is None:
                    lead_data['tags'] = []
                if lead_data.get('custom_fields') is None:
                    lead_data['custom_fields'] = {}
                
                return Lead(**lead_data)
            raise HTTPException(status_code=404, detail="Lead not found")

    async def delete_lead(self, lead_id: str) -> bool:
        """Delete a lead"""
        async with await get_db_connection() as conn:
            result = await conn.execute(
                "DELETE FROM leads WHERE id = $1",
                lead_id
            )
            return "DELETE 1" in result
    
    async def score_leads(self, request: LeadScoreRequest) -> List[LeadScoreResponse]:
        """Calculate and update lead scores"""
        lead_ids = request.lead_ids if request.lead_ids else [request.lead_id]
        
        async with await get_db_connection() as conn:
            # Get leads data
            leads = await conn.fetch(
                self.queries.get_leads_by_ids(),
                lead_ids
            )
            
            responses = []
            
            for lead in leads:
                # Calculate score based on factors
                score = self._calculate_lead_score(dict(lead), request.factors)
                
                # Update score
                await conn.execute(
                    self.queries.update_lead_score(),
                    score,
                    datetime.utcnow(),
                    lead['id']
                )
                
                responses.append(LeadScoreResponse(
                    lead_id=lead['id'],
                    previous_score=lead['score'],
                    new_score=score,
                    factors=request.factors or self._get_default_scoring_factors(),
                    updated_at=datetime.utcnow()
                ))
            
            # Record scoring events
            for response in responses:
                await self._record_lead_event(
                    conn,
                    response.lead_id,
                    'score_updated',
                    {
                        'previous_score': response.previous_score,
                        'new_score': response.new_score,
                        'factors': response.factors
                    }
                )
            
            return responses
    
    def _calculate_lead_score(self, lead: Dict, factors: Optional[Dict[str, float]]) -> int:
        """Calculate lead score based on various factors"""
        if not factors:
            factors = self._get_default_scoring_factors()
        
        score = 0
        
        # Email engagement
        if lead.get('email'):
            score += factors.get('has_email', 10)
        
        # Contact information completeness
        if lead.get('phone'):
            score += factors.get('has_phone', 5)
        if lead.get('lead_company') or lead.get('company'):
            score += factors.get('has_company', 15)
        if lead.get('job_title'):
            score += factors.get('has_job_title', 10)
        
        # Source quality
        source_scores = {
            'website': 10,
            'referral': 15,
            'event': 12,
            'paid_ad': 8,
            'csv_import': 5
        }
        score += source_scores.get(lead.get('source', ''), 0)
        
        # Cap at 100
        return min(score, 100)
    
    def _get_default_scoring_factors(self) -> Dict[str, float]:
        """Get default scoring factors"""
        return {
            'has_email': 10,
            'has_phone': 5,
            'has_company': 15,
            'has_job_title': 10,
            'recent_engagement': 10,
            'source_quality': 10
        }
    
    async def get_segments(self) -> List[LeadSegment]:
        """Get all lead segments"""
        async with await get_db_connection() as conn:
            segments = await conn.fetch(self.queries.get_segments())
            return [LeadSegment(**dict(segment)) for segment in segments]
    
    async def create_segment(self, segment: LeadSegment) -> LeadSegment:
        """Create a new lead segment"""
        segment_id = f"SEG-{str(uuid.uuid4())[:8].upper()}"
        now = datetime.utcnow()
        
        async with await get_db_connection() as conn:
            await conn.execute(
                self.queries.create_segment(),
                segment_id,
                segment.name,
                segment.description,
                json.dumps(segment.criteria),
                now,
                now
            )
        
        segment.id = segment_id
        segment.created_at = now
        segment.updated_at = now
        
        return segment
    
    async def distribute_leads(self, request: LeadDistributionRequest) -> LeadDistributionResponse:
        """Distribute leads to agents"""
        assignments = {}
        
        if request.distribution_method == "round_robin":
            assignments = self._round_robin_distribution(
                request.lead_ids,
                request.agent_ids
            )
        elif request.distribution_method == "load_balanced":
            assignments = await self._load_balanced_distribution(
                request.lead_ids,
                request.agent_ids
            )
        elif request.distribution_method == "skill_based":
            assignments = await self._skill_based_distribution(
                request.lead_ids,
                request.agent_ids,
                request.rules
            )
        elif request.distribution_method == "territory":
            assignments = await self._territory_based_distribution(
                request.lead_ids,
                request.rules
            )
        
        # Update lead assignments
        distributed = 0
        async with await get_db_connection() as conn:
            for agent_id, lead_ids in assignments.items():
                if lead_ids:
                    await conn.execute(
                        self.queries.assign_leads(),
                        agent_id,
                        datetime.utcnow(),
                        lead_ids
                    )
                    distributed += len(lead_ids)
                    
                    # Record assignment events
                    for lead_id in lead_ids:
                        await self._record_lead_event(
                            conn,
                            lead_id,
                            'assigned',
                            {'agent_id': agent_id, 'method': request.distribution_method}
                        )
        
        return LeadDistributionResponse(
            distributed=distributed,
            assignments=assignments
        )
    
    def _round_robin_distribution(self, lead_ids: List[str], 
                                 agent_ids: List[str]) -> Dict[str, List[str]]:
        """Round robin lead distribution"""
        assignments = {agent_id: [] for agent_id in agent_ids}
        
        for i, lead_id in enumerate(lead_ids):
            agent_id = agent_ids[i % len(agent_ids)]
            assignments[agent_id].append(lead_id)
        
        return assignments
    
    async def _load_balanced_distribution(self, lead_ids: List[str], 
                                         agent_ids: List[str]) -> Dict[str, List[str]]:
        """Load balanced lead distribution based on current workload"""
        return self._round_robin_distribution(lead_ids, agent_ids)
    
    async def _skill_based_distribution(self, lead_ids: List[str], 
                                       agent_ids: List[str],
                                       rules: Dict[str, Any]) -> Dict[str, List[str]]:
        """Skill-based lead distribution"""
        return self._round_robin_distribution(lead_ids, agent_ids)
    
    async def _territory_based_distribution(self, lead_ids: List[str],
                                          rules: Dict[str, Any]) -> Dict[str, List[str]]:
        """Territory-based lead distribution"""
        assignments = {}
        return assignments
    
    async def get_lead_journey(self, lead_id: str) -> LeadJourney:
        """Get complete journey for a lead"""
        async with await get_db_connection() as conn:
            # Get lead events
            events = await conn.fetch(
                self.queries.get_lead_journey(),
                lead_id
            )
            
            # Get lead details
            lead = await conn.fetchrow(
                self.queries.get_lead_by_id(),
                lead_id
            )
            
            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")
            
            # Process events
            events_list = [dict(e) for e in events]
            
            # Calculate engagement metrics
            engagement_metrics = self._calculate_engagement_metrics(events_list)
            
            # Get score history
            score_history = [
                e for e in events_list 
                if e.get('event_type') == 'score_updated'
            ]
            
            # Get touchpoints
            touchpoints = [
                e for e in events_list 
                if e.get('event_type') in ['contacted', 'email_sent', 'meeting_scheduled']
            ]
            
            return LeadJourney(
                lead_id=lead_id,
                events=events_list,
                current_stage=lead['status'],
                score_history=score_history,
                engagement_metrics=engagement_metrics,
                touchpoints=touchpoints
            )
    
    def _calculate_engagement_metrics(self, events: List[Dict]) -> Dict[str, Any]:
        """Calculate engagement metrics from events"""
        metrics = {
            'total_events': len(events),
            'email_opens': 0,
            'link_clicks': 0,
            'form_submissions': 0,
            'meetings_scheduled': 0,
            'last_engagement': None
        }
        
        for event in events:
            event_type = event.get('event_type')
            if event_type == 'email_opened':
                metrics['email_opens'] += 1
            elif event_type == 'link_clicked':
                metrics['link_clicks'] += 1
            elif event_type == 'form_submitted':
                metrics['form_submissions'] += 1
            elif event_type == 'meeting_scheduled':
                metrics['meetings_scheduled'] += 1
        
        if events:
            metrics['last_engagement'] = events[0].get('created_at')
        
        return metrics
    
    async def _record_lead_event(self, conn, lead_id: str, event_type: str, 
                                event_data: Dict[str, Any]):
        """Record a lead event using existing connection"""
        event_id = f"EVT-{str(uuid.uuid4())[:8].upper()}"
        await conn.execute(
            self.queries.record_lead_event(),
            event_id,
            lead_id,
            event_type,
            json.dumps(event_data),
            datetime.utcnow()
        )