import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from app.db.postgres_client import get_db_connection
from app.models.schemas import (
    CalendarConnectRequest, CalendarConnectResponse, TimeSlot, 
    CalendarAvailabilityResponse, CalendarTestRequest, CalendarTestResponse,
    ConflictCheckRequest, ConflictCheckResponse, BlockTimeRequest, BlockTimeResponse,
    CreateEventRequest, CreateEventResponse, RescheduleEventRequest, RescheduleEventResponse,
    CancelEventRequest, CancelEventResponse, SyncCalendarRequest, SyncCalendarResponse,
    SyncStatusResponse
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

    async def check_conflicts(
        self, 
        company_id: str, 
        calendar_id: Optional[str], 
        start_time: datetime, 
        end_time: datetime
    ) -> ConflictCheckResponse:
        """Check for calendar conflicts in the specified time range"""
        
        calendar_integration = await self._get_calendar_integration(company_id, calendar_id)
        if not calendar_integration:
            raise HTTPException(404, "Calendar integration not found")
        
        # Get existing events in the time range
        conflicts = await self._get_events_in_range(
            calendar_integration, start_time, end_time
        )
        
        has_conflicts = len(conflicts) > 0
        
        # If conflicts exist, suggest alternative times
        suggested_times = []
        if has_conflicts:
            suggested_times = await self._suggest_alternative_times(
                calendar_integration, start_time, end_time
            )
        
        return ConflictCheckResponse(
            has_conflicts=has_conflicts,
            conflicts=conflicts,
            suggested_times=suggested_times
        )

    async def block_time(
        self, 
        company_id: str, 
        user_id: str, 
        request: BlockTimeRequest
    ) -> BlockTimeResponse:
        """Block time on calendar to prevent bookings"""
        
        calendar_integration = await self._get_calendar_integration(company_id, request.calendar_id)
        if not calendar_integration:
            raise HTTPException(404, "Calendar integration not found")
        
        block_id = f"BLOCK-{uuid.uuid4().hex[:8].upper()}"
        
        try:
            async with (await get_db_connection()) as conn:
                await conn.execute("""
                    INSERT INTO calendar_blocks 
                    (id, company_id, user_id, calendar_id, title, description, 
                    start_time, end_time, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """, block_id, company_id, user_id, calendar_integration["id"],
                    request.title, request.description, request.start_time, 
                    request.end_time, datetime.utcnow(), datetime.utcnow())
            
            # Create event in external calendar if needed
            await self._create_external_event(
                calendar_integration,
                title=request.title,
                start_time=request.start_time,
                end_time=request.end_time,
                description=request.description or "Blocked Time"
            )
            
            logger.info(f"Time blocked: {block_id} for {company_id}")
            
            return BlockTimeResponse(
                success=True,
                block_id=block_id,
                message="Time blocked successfully"
            )
            
        except Exception as e:
            logger.error(f"Failed to block time: {str(e)}")
            raise HTTPException(500, f"Failed to block time: {str(e)}")

    async def create_event(
        self, 
        company_id: str, 
        user_id: str, 
        request: CreateEventRequest
    ) -> CreateEventResponse:
        """Create a new calendar event"""
        
        calendar_integration = await self._get_calendar_integration(company_id, request.calendar_id)
        if not calendar_integration:
            raise HTTPException(404, "Calendar integration not found")
        
        event_id = f"EVENT-{uuid.uuid4().hex[:8].upper()}"
        
        try:
            # Check for conflicts first
            conflicts = await self._get_events_in_range(
                calendar_integration, request.start_time, request.end_time
            )
            
            if conflicts:
                raise HTTPException(409, "Time slot conflicts with existing events")
            
            async with (await get_db_connection()) as conn:
                await conn.execute("""
                    INSERT INTO calendar_events 
                    (id, company_id, user_id, calendar_id, title, description, 
                    start_time, end_time, location, attendees, meeting_url, 
                    created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """, event_id, company_id, user_id, calendar_integration["id"],
                    request.title, request.description, request.start_time, 
                    request.end_time, request.location, json.dumps(request.attendees),
                    request.meeting_url, datetime.utcnow(), datetime.utcnow())
            
            # Create event in external calendar
            external_event_id = await self._create_external_event(
                calendar_integration,
                title=request.title,
                start_time=request.start_time,
                end_time=request.end_time,
                description=request.description,
                attendees=request.attendees,
                location=request.location,
                meeting_url=request.meeting_url
            )
            
            logger.info(f"Event created: {event_id} for {company_id}")
            
            return CreateEventResponse(
                success=True,
                event_id=event_id,
                message="Event created successfully",
                meeting_link=request.meeting_url
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create event: {str(e)}")
            raise HTTPException(500, f"Failed to create event: {str(e)}")

    async def reschedule_event(
        self, 
        company_id: str, 
        user_id: str, 
        request: RescheduleEventRequest
    ) -> RescheduleEventResponse:
        """Reschedule an existing calendar event"""
        
        try:
            async with (await get_db_connection()) as conn:
                # Get existing event
                event = await conn.fetchrow("""
                    SELECT * FROM calendar_events 
                    WHERE id = $1 AND company_id = $2
                """, request.event_id, company_id)
                
                if not event:
                    raise HTTPException(404, "Event not found")
                
                # Check for conflicts in new time
                calendar_integration = await self._get_calendar_integration(
                    company_id, event["calendar_id"]
                )
                
                conflicts = await self._get_events_in_range(
                    calendar_integration, request.new_start_time, request.new_end_time,
                    exclude_event_id=request.event_id
                )
                
                if conflicts:
                    raise HTTPException(409, "New time slot conflicts with existing events")
                
                # Update event
                await conn.execute("""
                    UPDATE calendar_events 
                    SET start_time = $1, end_time = $2, updated_at = $3
                    WHERE id = $4 AND company_id = $5
                """, request.new_start_time, request.new_end_time, 
                    datetime.utcnow(), request.event_id, company_id)
            
            # Update external calendar
            await self._update_external_event(
                calendar_integration,
                event["id"],
                start_time=request.new_start_time,
                end_time=request.new_end_time
            )
            
            logger.info(f"Event rescheduled: {request.event_id}")
            
            return RescheduleEventResponse(
                success=True,
                event_id=request.event_id,
                message="Event rescheduled successfully"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to reschedule event: {str(e)}")
            raise HTTPException(500, f"Failed to reschedule event: {str(e)}")

    async def cancel_event(
        self, 
        company_id: str, 
        user_id: str, 
        request: CancelEventRequest
    ) -> CancelEventResponse:
        """Cancel a calendar event"""
        
        try:
            async with (await get_db_connection()) as conn:
                # Get existing event
                event = await conn.fetchrow("""
                    SELECT * FROM calendar_events 
                    WHERE id = $1 AND company_id = $2
                """, request.event_id, company_id)
                
                if not event:
                    raise HTTPException(404, "Event not found")
                
                # Soft delete - mark as cancelled
                await conn.execute("""
                    UPDATE calendar_events 
                    SET status = 'cancelled', cancellation_reason = $1, updated_at = $2
                    WHERE id = $3 AND company_id = $4
                """, request.reason, datetime.utcnow(), request.event_id, company_id)
            
            # Cancel external calendar event
            calendar_integration = await self._get_calendar_integration(
                company_id, event["calendar_id"]
            )
            
            await self._cancel_external_event(calendar_integration, event["id"])
            
            logger.info(f"Event cancelled: {request.event_id}")
            
            return CancelEventResponse(
                success=True,
                event_id=request.event_id,
                message="Event cancelled successfully"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to cancel event: {str(e)}")
            raise HTTPException(500, f"Failed to cancel event: {str(e)}")

    async def sync_google_calendar(
        self, 
        company_id: str, 
        user_id: str, 
        request: SyncCalendarRequest
    ) -> SyncCalendarResponse:
        """Sync with Google Calendar"""
        
        try:
            calendar_integration = await self._get_calendar_integration_by_type(
                company_id, "google"
            )
            
            if not calendar_integration:
                raise HTTPException(404, "Google Calendar not connected")
            
            # Perform sync (mock implementation)
            events_synced = await self._perform_google_sync(
                calendar_integration, request.date_range_days
            )
            
            # Update last sync time
            async with (await get_db_connection()) as conn:
                await conn.execute("""
                    UPDATE calendar_integrations 
                    SET last_sync = $1, updated_at = $1 
                    WHERE id = $2
                """, datetime.utcnow(), calendar_integration["id"])
            
            return SyncCalendarResponse(
                success=True,
                calendar_type="google",
                events_synced=events_synced,
                last_sync=datetime.utcnow(),
                message=f"Synced {events_synced} events from Google Calendar"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Google Calendar sync failed: {str(e)}")
            raise HTTPException(500, f"Google Calendar sync failed: {str(e)}")

    async def sync_outlook_calendar(
        self, 
        company_id: str, 
        user_id: str, 
        request: SyncCalendarRequest
    ) -> SyncCalendarResponse:
        """Sync with Outlook Calendar"""
        
        try:
            calendar_integration = await self._get_calendar_integration_by_type(
                company_id, "outlook"
            )
            
            if not calendar_integration:
                raise HTTPException(404, "Outlook Calendar not connected")
            
            # Perform sync (mock implementation)
            events_synced = await self._perform_outlook_sync(
                calendar_integration, request.date_range_days
            )
            
            # Update last sync time
            async with (await get_db_connection()) as conn:
                await conn.execute("""
                    UPDATE calendar_integrations 
                    SET last_sync = $1, updated_at = $1 
                    WHERE id = $2
                """, datetime.utcnow(), calendar_integration["id"])
            
            return SyncCalendarResponse(
                success=True,
                calendar_type="outlook",
                events_synced=events_synced,
                last_sync=datetime.utcnow(),
                message=f"Synced {events_synced} events from Outlook Calendar"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Outlook Calendar sync failed: {str(e)}")
            raise HTTPException(500, f"Outlook Calendar sync failed: {str(e)}")

    async def get_sync_status(self, company_id: str) -> SyncStatusResponse:
        """Get sync status for all connected calendars"""
        
        async with (await get_db_connection()) as conn:
            integrations = await conn.fetch("""
                SELECT calendar_type, last_sync, is_active
                FROM calendar_integrations 
                WHERE company_id = $1
            """, company_id)
        
        google_status = {}
        outlook_status = {}
        last_full_sync = None
        
        for integration in integrations:
            status_info = {
                "connected": integration["is_active"],
                "last_sync": integration["last_sync"],
                "status": "active" if integration["is_active"] else "inactive"
            }
            
            if integration["calendar_type"] == "google":
                google_status = status_info
            elif integration["calendar_type"] == "outlook":
                outlook_status = status_info
            
            if integration["last_sync"] and (not last_full_sync or integration["last_sync"] > last_full_sync):
                last_full_sync = integration["last_sync"]
        
        return SyncStatusResponse(
            google_calendar=google_status,
            outlook_calendar=outlook_status,
            last_full_sync=last_full_sync,
            sync_in_progress=False
        )

    # Helper methods

    async def _get_calendar_integration_by_type(self, company_id: str, calendar_type: str):
        async with (await get_db_connection()) as conn:
            row = await conn.fetchrow("""
                SELECT * FROM calendar_integrations 
                WHERE company_id = $1 AND calendar_type = $2 AND is_active = TRUE
            """, company_id, calendar_type)
        
        return dict(row) if row else None

    async def _get_events_in_range(
        self, 
        calendar_integration: Dict[str, Any], 
        start_time: datetime, 
        end_time: datetime,
        exclude_event_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get events in the specified time range"""
        
        async with (await get_db_connection()) as conn:
            query = """
                SELECT * FROM calendar_events 
                WHERE calendar_id = $1 
                AND NOT (end_time <= $2 OR start_time >= $3)
                AND status != 'cancelled'
            """
            params = [calendar_integration["id"], start_time, end_time]
            
            if exclude_event_id:
                query += " AND id != $4"
                params.append(exclude_event_id)
            
            events = await conn.fetch(query, *params)
        
        return [dict(event) for event in events]

    async def _suggest_alternative_times(
        self, 
        calendar_integration: Dict[str, Any], 
        start_time: datetime, 
        end_time: datetime
    ) -> List[TimeSlot]:
        """Suggest alternative available time slots"""
        
        duration = end_time - start_time
        suggestions = []
        
        # Look for slots within the next 7 days
        search_start = start_time.replace(hour=9, minute=0, second=0, microsecond=0)
        search_end = search_start + timedelta(days=7)
        
        current = search_start
        while current < search_end and len(suggestions) < 5:
            slot_end = current + duration
            
            # Skip weekends and non-business hours
            if current.weekday() < 5 and 9 <= current.hour < 17:
                conflicts = await self._get_events_in_range(
                    calendar_integration, current, slot_end
                )
                
                if not conflicts:
                    suggestions.append(TimeSlot(
                        start=current.isoformat(),
                        end=slot_end.isoformat(),
                        available=True
                    ))
            
            current += timedelta(minutes=30)  # Check every 30 minutes
        
        return suggestions

    async def _create_external_event(
        self, 
        calendar_integration: Dict[str, Any], 
        **event_data
    ) -> str:
        """Create event in external calendar (mock implementation)"""
        # This would integrate with actual calendar APIs
        logger.info(f"Creating external event in {calendar_integration['calendar_type']}")
        return f"ext_{uuid.uuid4().hex[:8]}"

    async def _update_external_event(
        self, 
        calendar_integration: Dict[str, Any], 
        event_id: str, 
        **update_data
    ):
        """Update event in external calendar (mock implementation)"""
        logger.info(f"Updating external event {event_id} in {calendar_integration['calendar_type']}")

    async def _cancel_external_event(
        self, 
        calendar_integration: Dict[str, Any], 
        event_id: str
    ):
        """Cancel event in external calendar (mock implementation)"""
        logger.info(f"Cancelling external event {event_id} in {calendar_integration['calendar_type']}")

    async def _perform_google_sync(
        self, 
        calendar_integration: Dict[str, Any], 
        days: int
    ) -> int:
        """Perform Google Calendar sync (mock implementation)"""
        # This would integrate with Google Calendar API
        logger.info(f"Syncing Google Calendar for {days} days")
        return 15  # Mock number of events synced

    async def _perform_outlook_sync(
        self, 
        calendar_integration: Dict[str, Any], 
        days: int
    ) -> int:
        """Perform Outlook Calendar sync (mock implementation)"""
        # This would integrate with Outlook Calendar API
        logger.info(f"Syncing Outlook Calendar for {days} days")
        return 12  # Mock number of events synced

    async def full_sync_google_calendar(
        self, 
        company_id: str, 
        user_id: str, 
        days: int
    ):
        """Background task for full Google Calendar sync"""
        try:
            calendar_integration = await self._get_calendar_integration_by_type(
                company_id, "google"
            )
            if calendar_integration:
                events_synced = await self._perform_google_sync(calendar_integration, days)
                logger.info(f"Full Google sync completed: {events_synced} events")
        except Exception as e:
            logger.error(f"Full Google sync failed: {str(e)}")

    async def full_sync_outlook_calendar(
        self, 
        company_id: str, 
        user_id: str, 
        days: int
    ):
        """Background task for full Outlook Calendar sync"""
        try:
            calendar_integration = await self._get_calendar_integration_by_type(
                company_id, "outlook"
            )
            if calendar_integration:
                events_synced = await self._perform_outlook_sync(calendar_integration, days)
                logger.info(f"Full Outlook sync completed: {events_synced} events")
        except Exception as e:
            logger.error(f"Full Outlook sync failed: {str(e)}")