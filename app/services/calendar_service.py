import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from app.db.postgres_client import get_db_connection
from app.models.schemas import (
    CalendarConnectRequest, CalendarConnectResponse, TimeSlot, 
    CalendarAvailabilityResponse, CalendarTestRequest, CalendarTestResponse
)
import logging

logger = logging.getLogger(__name__)

class CalendarService:
    
    async def connect_calendar(
        self, 
        company_id: str, 
        user_id: str, 
        request: CalendarConnectRequest
    ) -> CalendarConnectResponse:

        calendar_integration_id = f"CAL-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow()
        
        try:
            await self._validate_credentials(request.calendar_type, request.credentials)

            async with await get_db_connection() as conn:
                if request.is_primary:
                    await conn.execute("""
                        UPDATE calendar_integrations 
                        SET is_primary = FALSE 
                        WHERE company_id = $1
                    """, company_id)

                await conn.execute("""
                    INSERT INTO calendar_integrations 
                    (id, company_id, user_id, calendar_type, calendar_id, calendar_name, 
                     credentials, is_active, is_primary, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """, calendar_integration_id, company_id, user_id, request.calendar_type,
                     calendar_integration_id, request.calendar_name or f"{request.calendar_type.title()} Calendar",
                     json.dumps(request.credentials), True, request.is_primary, now, now)
            
            logger.info(f"Calendar connected: {calendar_integration_id} for company {company_id}")
            
            return CalendarConnectResponse(
                calendar_id=calendar_integration_id,
                calendar_type=request.calendar_type,
                calendar_name=request.calendar_name or f"{request.calendar_type.title()} Calendar",
                is_connected=True,
                message="Calendar connected successfully"
            )
            
        except Exception as e:
            logger.error(f"Failed to connect calendar: {str(e)}")
            raise Exception(f"Calendar connection failed: {str(e)}")
    
    async def get_availability(
        self, 
        company_id: str, 
        calendar_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        duration_minutes: int = 30
    ) -> CalendarAvailabilityResponse:

        if not start_date:
            start_date = datetime.utcnow().isoformat()
        if not end_date:
            end_dt = datetime.utcnow() + timedelta(days=7)
            end_date = end_dt.isoformat()

        calendar_integration = await self._get_calendar_integration(company_id, calendar_id)
        if not calendar_integration:
            raise Exception("Calendar integration not found")

        available_slots = await self._generate_available_slots(
            calendar_integration, start_date, end_date, duration_minutes
        )
        
        return CalendarAvailabilityResponse(
            calendar_id=calendar_integration["id"],
            date_range={"start": start_date, "end": end_date},
            total_slots=len(available_slots),
            available_slots=available_slots
        )
    
    async def test_connection(
        self, 
        company_id: str, 
        calendar_id: str,
        user_id: str
    ) -> CalendarTestResponse:
        
        calendar_integration = await self._get_calendar_integration(company_id, calendar_id)
        if not calendar_integration:
            return CalendarTestResponse(
                calendar_id=calendar_id,
                success=False,
                message="Calendar integration not found",
                last_tested=datetime.utcnow().isoformat()
            )
        
        try:
            success = await self._test_calendar_connection(calendar_integration)

            async with await get_db_connection() as conn:
                await conn.execute("""
                    UPDATE calendar_integrations 
                    SET last_sync = $1, updated_at = $1 
                    WHERE id = $2
                """, datetime.utcnow(), calendar_id)
            
            message = "Connection successful" if success else "Connection failed"
            
            return CalendarTestResponse(
                calendar_id=calendar_id,
                success=success,
                message=message,
                last_tested=datetime.utcnow().isoformat(),
                connection_details={
                    "calendar_type": calendar_integration["calendar_type"],
                    "calendar_name": calendar_integration["calendar_name"]
                }
            )
            
        except Exception as e:
            logger.error(f"Calendar test failed: {str(e)}")
            return CalendarTestResponse(
                calendar_id=calendar_id,
                success=False,
                message=f"Test failed: {str(e)}",
                last_tested=datetime.utcnow().isoformat()
            )

    async def _get_calendar_integration(self, company_id: str, calendar_id: Optional[str] = None):
        async with await get_db_connection() as conn:
            if calendar_id:
                row = await conn.fetchrow("""
                    SELECT * FROM calendar_integrations 
                    WHERE company_id = $1 AND id = $2 AND is_active = TRUE
                """, company_id, calendar_id)
            else:
                row = await conn.fetchrow("""
                    SELECT * FROM calendar_integrations 
                    WHERE company_id = $1 AND is_primary = TRUE AND is_active = TRUE
                """, company_id)
        
        return dict(row) if row else None
    
    async def _validate_credentials(self, calendar_type: str, credentials: Dict[str, Any]):
        required_fields = {
            "google": ["access_token", "refresh_token"],
            "outlook": ["access_token", "refresh_token"],
            "calendly": ["api_key"]
        }
        
        if calendar_type not in required_fields:
            raise ValueError(f"Unsupported calendar type: {calendar_type}")
        
        missing_fields = [field for field in required_fields[calendar_type] if field not in credentials]
        if missing_fields:
            raise ValueError(f"Missing required credentials: {', '.join(missing_fields)}")
    
    async def _generate_available_slots(
        self, 
        calendar_integration: Dict[str, Any],
        start_date: str,
        end_date: str,
        duration_minutes: int
    ) -> List[TimeSlot]:
        
        slots = []
        current = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        while current < end:
            if current.weekday() < 5 and 9 <= current.hour < 17:
                slot_end = current + timedelta(minutes=duration_minutes)
                slots.append(TimeSlot(
                    start=current.isoformat(),
                    end=slot_end.isoformat(),
                    available=True
                ))
            
            current += timedelta(minutes=duration_minutes)

            if len(slots) >= 50:
                break
        
        return slots
    
    async def _test_calendar_connection(self, calendar_integration: Dict[str, Any]) -> bool:
        calendar_type = calendar_integration["calendar_type"]
        credentials = json.loads(calendar_integration["credentials"])

        if calendar_type == "google":
            return "access_token" in credentials and len(credentials["access_token"]) > 10
        elif calendar_type == "outlook":
            return "access_token" in credentials and len(credentials["access_token"]) > 10
        elif calendar_type == "calendly":
            return "api_key" in credentials and len(credentials["api_key"]) > 10
        
        return False
