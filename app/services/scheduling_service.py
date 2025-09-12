import uuid
from datetime import datetime, date, time, timedelta, timezone
from typing import List, Dict, Any, Optional
from app.db.postgres_client import get_db_connection
from app.models.scheduling_schemas import (
    AvailabilityTemplateCreate, AvailabilityTemplateUpdate,
    BookingRuleCreate, BookingRuleUpdate,
    RecurringAvailabilityCreate, RecurringAvailabilityUpdate,
    ScheduleOverrideCreate, ScheduleOverrideUpdate,
    BufferRuleCreate, BufferRuleUpdate,
    TeamScheduleCreate, TeamScheduleUpdate,
    AvailabilityCheckRequest, AvailabilityCheckResponse,
    BulkAvailabilityRequest, BulkAvailabilityResponse,
    OptimalTimesRequest, OptimalTimesResponse,
    ScheduleConflictRequest, ScheduleConflictResponse,
    ResourceAllocationRequest, ResourceAllocationResponse,
    SchedulePolicyCreate, SchedulePolicyUpdate,
    TimeSlot, SuggestedTime, ConflictDetail, AllocatedResource,
    DayOfWeek, AssignmentMethod
)
import logging
from collections import defaultdict
import json

logger = logging.getLogger(__name__)

class SchedulingService:
    
    # ============== Availability Templates ==============
    
    async def create_availability_template(
        self, company_id: str, template: AvailabilityTemplateCreate, user_id: str
    ):
        template_id = f"TMPL-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow()
        
        async with await get_db_connection() as conn:
            # If this is marked as default, unset other defaults
            if template.is_default:
                await conn.execute("""
                    UPDATE availability_templates 
                    SET is_default = false, updated_at = $1
                    WHERE company_id = $2 AND is_default = true
                """, now, company_id)
            
            row = await conn.fetchrow("""
                INSERT INTO availability_templates (
                    id, company_id, name, description, schedule_type,
                    timezone, is_default, user_id, team_id,
                    monday, tuesday, wednesday, thursday, friday, saturday, sunday,
                    slot_duration_minutes, advance_booking_days, minimum_notice_hours,
                    created_by, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22)
                RETURNING *
            """, template_id, company_id, template.name, template.description,
                template.schedule_type, template.timezone, template.is_default,
                template.user_id, template.team_id,
                json.dumps([t.dict() for t in template.monday]),
                json.dumps([t.dict() for t in template.tuesday]),
                json.dumps([t.dict() for t in template.wednesday]),
                json.dumps([t.dict() for t in template.thursday]),
                json.dumps([t.dict() for t in template.friday]),
                json.dumps([t.dict() for t in template.saturday]),
                json.dumps([t.dict() for t in template.sunday]),
                template.slot_duration_minutes, template.advance_booking_days,
                template.minimum_notice_hours, user_id, now, now)
            
            logger.info(f"Created availability template: {template_id}")
            return dict(row)
    
    async def list_availability_templates(
        self, company_id: str, user_id: Optional[str], is_default: Optional[bool]
    ):
        conditions = ["company_id = $1"]
        params = [company_id]
        param_count = 2
        
        if user_id:
            conditions.append(f"user_id = ${param_count}")
            params.append(user_id)
            param_count += 1
        
        if is_default is not None:
            conditions.append(f"is_default = ${param_count}")
            params.append(is_default)
            param_count += 1
        
        where_clause = " AND ".join(conditions)
        
        async with await get_db_connection() as conn:
            rows = await conn.fetch(f"""
                SELECT * FROM availability_templates
                WHERE {where_clause}
                ORDER BY created_at DESC
            """, *params)
        
        return [dict(row) for row in rows]
    
    async def get_availability_template(self, template_id: str, company_id: str):
        async with await get_db_connection() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM availability_templates
                WHERE id = $1 AND company_id = $2
            """, template_id, company_id)
        
        return dict(row) if row else None
    
    async def update_availability_template(
        self, template_id: str, company_id: str, updates: AvailabilityTemplateUpdate
    ):
        update_fields = []
        values = []
        param_count = 1
        
        update_data = updates.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if field in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
                value = json.dumps([t.dict() for t in value]) if value else json.dumps([])
            
            update_fields.append(f"{field} = ${param_count}")
            values.append(value)
            param_count += 1
        
        if not update_fields:
            return await self.get_availability_template(template_id, company_id)
        
        update_fields.append(f"updated_at = ${param_count}")
        values.append(datetime.utcnow())
        param_count += 1
        
        values.extend([template_id, company_id])
        
        async with await get_db_connection() as conn:
            row = await conn.fetchrow(f"""
                UPDATE availability_templates
                SET {', '.join(update_fields)}
                WHERE id = ${param_count} AND company_id = ${param_count + 1}
                RETURNING *
            """, *values)
        
        return dict(row) if row else None
    
    async def delete_availability_template(self, template_id: str, company_id: str):
        async with await get_db_connection() as conn:
            result = await conn.execute("""
                DELETE FROM availability_templates
                WHERE id = $1 AND company_id = $2
            """, template_id, company_id)
        
        return result.startswith("DELETE 1")
    
    async def apply_template_to_users(
        self, template_id: str, company_id: str, user_ids: List[str]
    ):
        async with await get_db_connection() as conn:
            # Get the template
            template = await conn.fetchrow("""
                SELECT * FROM availability_templates
                WHERE id = $1 AND company_id = $2
            """, template_id, company_id)
            
            if not template:
                raise ValueError("Template not found")
            
            # Apply to each user
            applied_count = 0
            for user_id in user_ids:
                await conn.execute("""
                    UPDATE users 
                    SET availability_template_id = $1, updated_at = $2
                    WHERE id = $3 AND company_id = $4
                """, template_id, datetime.utcnow(), user_id, company_id)
                applied_count += 1
        
        return {"applied_count": applied_count}
    
    # ============== Booking Rules ==============
    
    async def create_booking_rule(
        self, company_id: str, rule: BookingRuleCreate, user_id: str
    ):
        rule_id = f"RULE-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow()
        
        async with await get_db_connection() as conn:
            row = await conn.fetchrow("""
                INSERT INTO booking_rules (
                    id, company_id, name, description, rule_type,
                    is_active, priority, parameters,
                    applies_to_all, user_ids, team_ids, meeting_type_ids,
                    created_by, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                RETURNING *
            """, rule_id, company_id, rule.name, rule.description, rule.rule_type,
                rule.is_active, rule.priority, json.dumps(rule.parameters),
                rule.applies_to_all, rule.user_ids, rule.team_ids, rule.meeting_type_ids,
                user_id, now, now)
            
            logger.info(f"Created booking rule: {rule_id}")
            return dict(row)
    
    async def list_booking_rules(
        self, company_id: str, rule_type: Optional[str], 
        applies_to: Optional[str], is_active: Optional[bool]
    ):
        conditions = ["company_id = $1"]
        params = [company_id]
        param_count = 2
        
        if rule_type:
            conditions.append(f"rule_type = ${param_count}")
            params.append(rule_type)
            param_count += 1
        
        if is_active is not None:
            conditions.append(f"is_active = ${param_count}")
            params.append(is_active)
            param_count += 1
        
        if applies_to:
            if applies_to == "global":
                conditions.append("applies_to_all = true")
            else:
                conditions.append(f"(${param_count} = ANY(user_ids) OR ${param_count} = ANY(team_ids))")
                params.append(applies_to)
                param_count += 1
        
        where_clause = " AND ".join(conditions)
        
        async with await get_db_connection() as conn:
            rows = await conn.fetch(f"""
                SELECT * FROM booking_rules
                WHERE {where_clause}
                ORDER BY priority DESC, created_at DESC
            """, *params)
        
        return [dict(row) for row in rows]
    
    async def update_booking_rule(
        self, rule_id: str, company_id: str, updates: BookingRuleUpdate
    ):
        update_fields = []
        values = []
        param_count = 1
        
        update_data = updates.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if field == "parameters":
                value = json.dumps(value)
            
            update_fields.append(f"{field} = ${param_count}")
            values.append(value)
            param_count += 1
        
        if not update_fields:
            return None
        
        update_fields.append(f"updated_at = ${param_count}")
        values.append(datetime.utcnow())
        param_count += 1
        
        values.extend([rule_id, company_id])
        
        async with await get_db_connection() as conn:
            row = await conn.fetchrow(f"""
                UPDATE booking_rules
                SET {', '.join(update_fields)}
                WHERE id = ${param_count} AND company_id = ${param_count + 1}
                RETURNING *
            """, *values)
        
        return dict(row) if row else None
    
    async def delete_booking_rule(self, rule_id: str, company_id: str):
        async with await get_db_connection() as conn:
            result = await conn.execute("""
                DELETE FROM booking_rules
                WHERE id = $1 AND company_id = $2
            """, rule_id, company_id)
        
        return result.startswith("DELETE 1")
    
    # ============== Recurring Availability ==============
    
    async def create_recurring_availability(
        self, company_id: str, availability: RecurringAvailabilityCreate, user_id: str
    ):
        pattern_id = f"RECUR-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow()
        
        async with await get_db_connection() as conn:
            row = await conn.fetchrow("""
                INSERT INTO recurring_availability (
                    id, company_id, name, user_id, day_of_week,
                    time_blocks, effective_from, effective_until,
                    is_active, repeat_pattern, exceptions,
                    created_by, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                RETURNING *
            """, pattern_id, company_id, availability.name, availability.user_id,
                availability.day_of_week, json.dumps([t.dict() for t in availability.time_blocks]),
                availability.effective_from, availability.effective_until,
                availability.is_active, availability.repeat_pattern,
                availability.exceptions, user_id, now, now)
            
            logger.info(f"Created recurring availability: {pattern_id}")
            return dict(row)
    
    async def list_recurring_availability(
        self, company_id: str, user_id: Optional[str], day_of_week: Optional[str]
    ):
        conditions = ["company_id = $1"]
        params = [company_id]
        param_count = 2
        
        if user_id:
            conditions.append(f"user_id = ${param_count}")
            params.append(user_id)
            param_count += 1
        
        if day_of_week:
            conditions.append(f"day_of_week = ${param_count}")
            params.append(day_of_week)
            param_count += 1
        
        where_clause = " AND ".join(conditions)
        
        async with await get_db_connection() as conn:
            rows = await conn.fetch(f"""
                SELECT * FROM recurring_availability
                WHERE {where_clause}
                ORDER BY day_of_week, created_at DESC
            """, *params)
        
        return [dict(row) for row in rows]
    
    async def update_recurring_availability(
        self, pattern_id: str, company_id: str, updates: RecurringAvailabilityUpdate
    ):
        update_fields = []
        values = []
        param_count = 1
        
        update_data = updates.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if field == "time_blocks":
                value = json.dumps([t.dict() for t in value])
            
            update_fields.append(f"{field} = ${param_count}")
            values.append(value)
            param_count += 1
        
        if not update_fields:
            return None
        
        update_fields.append(f"updated_at = ${param_count}")
        values.append(datetime.utcnow())
        param_count += 1
        
        values.extend([pattern_id, company_id])
        
        async with await get_db_connection() as conn:
            row = await conn.fetchrow(f"""
                UPDATE recurring_availability
                SET {', '.join(update_fields)}
                WHERE id = ${param_count} AND company_id = ${param_count + 1}
                RETURNING *
            """, *values)
        
        return dict(row) if row else None
    
    # ============== Schedule Overrides ==============
    
    async def create_schedule_override(
        self, company_id: str, override: ScheduleOverrideCreate, user_id: str
    ):
        override_id = f"OVER-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow()
        
        async with await get_db_connection() as conn:
            row = await conn.fetchrow("""
                INSERT INTO schedule_overrides (
                    id, company_id, user_id, override_type,
                    start_date, end_date, start_time, end_time,
                    reason, is_all_day, replacement_user_id,
                    created_by, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                RETURNING *
            """, override_id, company_id, override.user_id, override.override_type,
                override.start_date, override.end_date, override.start_time,
                override.end_time, override.reason, override.is_all_day,
                override.replacement_user_id, user_id, now, now)
            
            logger.info(f"Created schedule override: {override_id}")
            return dict(row)
    
    async def list_schedule_overrides(
        self, company_id: str, user_id: Optional[str],
        start_date: Optional[date], end_date: Optional[date],
        override_type: Optional[str]
    ):
        conditions = ["company_id = $1"]
        params = [company_id]
        param_count = 2
        
        if user_id:
            conditions.append(f"user_id = ${param_count}")
            params.append(user_id)
            param_count += 1
        
        if start_date:
            conditions.append(f"end_date >= ${param_count}")
            params.append(start_date)
            param_count += 1
        
        if end_date:
            conditions.append(f"start_date <= ${param_count}")
            params.append(end_date)
            param_count += 1
        
        if override_type:
            conditions.append(f"override_type = ${param_count}")
            params.append(override_type)
            param_count += 1
        
        where_clause = " AND ".join(conditions)
        
        async with await get_db_connection() as conn:
            rows = await conn.fetch(f"""
                SELECT * FROM schedule_overrides
                WHERE {where_clause}
                ORDER BY start_date DESC
            """, *params)
        
        return [dict(row) for row in rows]
    
    async def delete_schedule_override(self, override_id: str, company_id: str):
        async with await get_db_connection() as conn:
            result = await conn.execute("""
                DELETE FROM schedule_overrides
                WHERE id = $1 AND company_id = $2
            """, override_id, company_id)
        
        return result.startswith("DELETE 1")
    
    # ============== Buffer Rules ==============
    
    async def create_buffer_rule(
        self, company_id: str, buffer: BufferRuleCreate, user_id: str
    ):
        buffer_id = f"BUF-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow()
        
        async with await get_db_connection() as conn:
            row = await conn.fetchrow("""
                INSERT INTO buffer_rules (
                    id, company_id, name, user_id, team_id,
                    meeting_type, buffer_before_minutes, buffer_after_minutes,
                    applies_to_all_meetings, is_active,
                    created_by, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                RETURNING *
            """, buffer_id, company_id, buffer.name, buffer.user_id, buffer.team_id,
                buffer.meeting_type, buffer.buffer_before_minutes,
                buffer.buffer_after_minutes, buffer.applies_to_all_meetings,
                buffer.is_active, user_id, now, now)
            
            logger.info(f"Created buffer rule: {buffer_id}")
            return dict(row)
    
    async def list_buffer_rules(
        self, company_id: str, user_id: Optional[str], meeting_type: Optional[str]
    ):
        conditions = ["company_id = $1"]
        params = [company_id]
        param_count = 2
        
        if user_id:
            conditions.append(f"user_id = ${param_count}")
            params.append(user_id)
            param_count += 1
        
        if meeting_type:
            conditions.append(f"meeting_type = ${param_count}")
            params.append(meeting_type)
            param_count += 1
        
        where_clause = " AND ".join(conditions)
        
        async with await get_db_connection() as conn:
            rows = await conn.fetch(f"""
                SELECT * FROM buffer_rules
                WHERE {where_clause}
                ORDER BY created_at DESC
            """, *params)
        
        return [dict(row) for row in rows]
    
    # ============== Team Scheduling ==============
    
    async def create_team_schedule(
        self, company_id: str, schedule: TeamScheduleCreate, user_id: str
    ):
        schedule_id = f"TEAM-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow()
        
        async with await get_db_connection() as conn:
            row = await conn.fetchrow("""
                INSERT INTO team_schedules (
                    id, company_id, team_id, name, assignment_method,
                    allow_member_preference, collective_availability,
                    min_team_members_available, rotation_settings,
                    skill_requirements, member_ids,
                    created_by, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                RETURNING *
            """, schedule_id, company_id, schedule.team_id, schedule.name,
                schedule.assignment_method, schedule.allow_member_preference,
                schedule.collective_availability, schedule.min_team_members_available,
                json.dumps(schedule.rotation_settings) if schedule.rotation_settings else None,
                schedule.skill_requirements, schedule.member_ids,
                user_id, now, now)
            
            logger.info(f"Created team schedule: {schedule_id}")
            return dict(row)
    
    async def get_team_availability(
        self, team_id: str, company_id: str, start_date: date, 
        end_date: date, duration_minutes: int
    ):
        async with await get_db_connection() as conn:
            # Get team schedule configuration
            team_schedule = await conn.fetchrow("""
                SELECT * FROM team_schedules
                WHERE team_id = $1 AND company_id = $2
            """, team_id, company_id)
            
            if not team_schedule:
                return {"error": "Team schedule not found"}
            
            # Get member availability
            member_availability = {}
            for member_id in team_schedule['member_ids']:
                member_slots = await self._get_user_availability(
                    member_id, start_date, end_date, duration_minutes, conn
                )
                member_availability[member_id] = member_slots
            
            # Calculate collective availability based on team settings
            if team_schedule['collective_availability']:
                available_slots = self._calculate_collective_availability(
                    member_availability,
                    team_schedule['min_team_members_available']
                )
            else:
                available_slots = self._merge_all_availability(member_availability)
            
            return {
                "team_id": team_id,
                "available_slots": available_slots,
                "member_availability": member_availability,
                "total_slots": len(available_slots)
            }
    
    async def assign_team_member(
        self, team_id: str, booking_id: str, company_id: str,
        assignment_method: str, preferred_member_id: Optional[str]
    ):
        async with await get_db_connection() as conn:
            # Get team schedule
            team_schedule = await conn.fetchrow("""
                SELECT * FROM team_schedules
                WHERE team_id = $1 AND company_id = $2
            """, team_id, company_id)
            
            if not team_schedule:
                return {"error": "Team schedule not found"}
            
            # Get booking details
            booking = await conn.fetchrow("""
                SELECT * FROM booking WHERE id = $1
            """, booking_id)
            
            if not booking:
                return {"error": "Booking not found"}
            
            # Determine which member to assign
            if assignment_method == "manual" and preferred_member_id:
                assigned_member = preferred_member_id
            else:
                assigned_member = await self._select_team_member(
                    team_schedule['member_ids'],
                    assignment_method,
                    booking['slot_start'],
                    booking['slot_end'],
                    conn
                )
            
            # Update booking with assigned member
            await conn.execute("""
                UPDATE booking 
                SET assigned_user_id = $1, updated_at = $2
                WHERE id = $3
            """, assigned_member, datetime.utcnow(), booking_id)
            
            logger.info(f"Assigned member {assigned_member} to booking {booking_id}")
            
            return {
                "booking_id": booking_id,
                "assigned_member": assigned_member,
                "assignment_method": assignment_method
            }
    
    # ============== Availability Checking ==============
    
    async def check_availability(
        self, company_id: str, request: AvailabilityCheckRequest
    ):
        async with await get_db_connection() as conn:
            available_slots = []
            
            if request.user_id:
                slots = await self._get_user_availability(
                    request.user_id,
                    request.start_date,
                    request.end_date,
                    request.duration_minutes,
                    conn
                )
                available_slots.extend(slots)
            
            if request.team_id:
                team_slots = await self.get_team_availability(
                    request.team_id,
                    company_id,
                    request.start_date,
                    request.end_date,
                    request.duration_minutes
                )
                available_slots.extend(team_slots.get('available_slots', []))
            
            # Apply buffer rules if requested
            if request.include_buffer:
                available_slots = await self._apply_buffer_rules(
                    available_slots, request.user_id, company_id, conn
                )
            
            # Find next available slot
            next_available = None
            if available_slots:
                next_available = min(slot['start'] for slot in available_slots)
            
            return AvailabilityCheckResponse(
                available_slots=[TimeSlot(**slot) for slot in available_slots],
                total_slots=len(available_slots),
                timezone=request.timezone,
                next_available=next_available
            )
    
    async def check_bulk_availability(
        self, company_id: str, request: BulkAvailabilityRequest
    ):
        async with await get_db_connection() as conn:
            results = {}
            all_slots = []
            
            # Get availability for each user
            for user_id in request.user_ids or []:
                user_slots = await self._get_user_availability(
                    user_id,
                    request.start_date,
                    request.end_date,
                    request.duration_minutes,
                    conn
                )
                results[user_id] = user_slots
                all_slots.extend(user_slots)
            
            # Get availability for each team
            for team_id in request.team_ids or []:
                team_slots = await self.get_team_availability(
                    team_id,
                    company_id,
                    request.start_date,
                    request.end_date,
                    request.duration_minutes
                )
                results[team_id] = team_slots.get('available_slots', [])
                all_slots.extend(team_slots.get('available_slots', []))
            
            # Find common slots if requested
            common_slots = None
            if request.find_common_slots:
                common_slots = self._find_common_slots(
                    results, request.min_attendees
                )
            
            return BulkAvailabilityResponse(
                results=results,
                common_slots=[TimeSlot(**slot) for slot in common_slots] if common_slots else None,
                total_available_slots=len(all_slots)
            )
    
    # ============== Optimal Times ==============
    
    async def find_optimal_times(
        self, company_id: str, request: OptimalTimesRequest
    ):
        async with await get_db_connection() as conn:
            # Get availability for all participants
            participant_availability = {}
            for participant_id in request.participants:
                slots = await self._get_user_availability(
                    participant_id,
                    request.date_range_start,
                    request.date_range_end,
                    request.duration_minutes,
                    conn
                )
                participant_availability[participant_id] = slots
            
            # Score each potential time slot
            scored_times = []
            common_slots = self._find_common_slots(
                participant_availability,
                len(request.participants)
            )
            
            for slot in common_slots:
                score = self._score_time_slot(
                    slot,
                    request.preferred_times,
                    request.avoid_times,
                    request.urgency,
                    participant_availability
                )
                
                suggested_time = SuggestedTime(
                    start=slot['start'],
                    end=slot['end'],
                    score=score['total'],
                    attendee_availability={
                        p: True for p in request.participants
                    },
                    reasons=score['reasons']
                )
                scored_times.append(suggested_time)
            
            # Sort by score
            scored_times.sort(key=lambda x: x.score, reverse=True)
            
            return OptimalTimesResponse(
                suggested_times=scored_times[:10],  # Top 10 suggestions
                best_time=scored_times[0] if scored_times else None,
                analysis={
                    "total_common_slots": len(common_slots),
                    "scoring_factors": ["preference_match", "urgency", "time_of_day", "day_of_week"]
                }
            )
    
    # ============== Conflict Detection ==============
    
    async def check_conflicts(
        self, company_id: str, request: ScheduleConflictRequest
    ):
        async with await get_db_connection() as conn:
            conflicts = []
            
            for user_id in request.user_ids:
                # Check existing bookings
                user_bookings = await conn.fetch("""
                    SELECT * FROM booking
                    WHERE assigned_user_id = $1
                    AND status IN ('pending', 'confirmed')
                    AND NOT (slot_end <= $2 OR slot_start >= $3)
                    AND id != ANY($4::text[])
                """, user_id, request.start_time, request.end_time,
                    request.ignore_booking_ids or [])
                
                for booking in user_bookings:
                    conflicts.append(ConflictDetail(
                        user_id=user_id,
                        conflict_type="booking_overlap",
                        conflicting_booking_id=booking['id'],
                        description=f"Conflicts with existing booking from {booking['slot_start']} to {booking['slot_end']}",
                        severity="high"
                    ))
                
                # Check schedule overrides
                if request.check_policies:
                    overrides = await conn.fetch("""
                        SELECT * FROM schedule_overrides
                        WHERE user_id = $1
                        AND NOT (end_date < $2::date OR start_date > $3::date)
                        AND override_type IN ('time_off', 'blocked')
                    """, user_id, request.start_time.date(), request.end_time.date())
                    
                    for override in overrides:
                        conflicts.append(ConflictDetail(
                            user_id=user_id,
                            conflict_type="schedule_override",
                            conflicting_booking_id=None,
                            description=f"User has {override['override_type']}: {override['reason']}",
                            severity="high"
                        ))
                
                # Check buffer rules
                if request.check_buffers:
                    buffer_conflicts = await self._check_buffer_conflicts(
                        user_id, request.start_time, request.end_time, company_id, conn
                    )
                    conflicts.extend(buffer_conflicts)
            
            # Generate resolution suggestions
            suggestions = []
            if conflicts:
                suggestions = self._generate_conflict_resolutions(conflicts, request)
            
            return ScheduleConflictResponse(
                has_conflicts=len(conflicts) > 0,
                conflicts=conflicts,
                resolution_suggestions=suggestions
            )
    
    # ============== Resource Allocation ==============
    
    async def allocate_resources(
        self, company_id: str, request: ResourceAllocationRequest
    ):
        async with await get_db_connection() as conn:
            allocated_resources = []
            
            for resource_type in request.resource_types:
                # Get available resources of this type
                available = await conn.fetch("""
                    SELECT * FROM resources
                    WHERE company_id = $1
                    AND resource_type = $2
                    AND is_active = true
                    AND id NOT IN (
                        SELECT resource_id FROM resource_bookings
                        WHERE NOT (end_time <= $3 OR start_time >= $4)
                    )
                """, company_id, resource_type, request.start_time, request.end_time)
                
                # Select best resource based on preferences and capacity
                if available:
                    selected = self._select_best_resource(
                        available,
                        request.preferences,
                        request.required_capacity
                    )
                    
                    if selected:
                        # Book the resource
                        await conn.execute("""
                            INSERT INTO resource_bookings (
                                id, booking_id, resource_id, start_time, end_time,
                                created_at
                            ) VALUES ($1, $2, $3, $4, $5, $6)
                        """, f"RES-{uuid.uuid4().hex[:8].upper()}", request.booking_id,
                            selected['id'], request.start_time, request.end_time,
                            datetime.utcnow())
                        
                        allocated_resources.append(AllocatedResource(
                            resource_id=selected['id'],
                            resource_type=resource_type,
                            resource_name=selected['name'],
                            capacity=selected['capacity'],
                            location=selected.get('location'),
                            cost=selected.get('cost')
                        ))
            
            # Calculate total cost
            total_cost = sum(r.cost for r in allocated_resources if r.cost)
            
            return ResourceAllocationResponse(
                booking_id=request.booking_id,
                allocated_resources=allocated_resources,
                total_cost=total_cost if total_cost > 0 else None,
                alternatives=None
            )
    
    async def get_resource_availability(
        self, company_id: str, resource_type: str, start_date: date, end_date: date
    ):
        async with await get_db_connection() as conn:
            resources = await conn.fetch("""
                SELECT r.*, 
                    COUNT(rb.id) as booking_count,
                    ARRAY_AGG(rb.start_time || '-' || rb.end_time) as booked_times
                FROM resources r
                LEFT JOIN resource_bookings rb ON r.id = rb.resource_id
                    AND rb.start_time::date >= $2
                    AND rb.end_time::date <= $3
                WHERE r.company_id = $1 AND r.resource_type = $4
                GROUP BY r.id
            """, company_id, start_date, end_date, resource_type)
            
            return [dict(r) for r in resources]
    
    # ============== Schedule Policies ==============
    
    async def create_schedule_policy(
        self, company_id: str, policy: SchedulePolicyCreate, user_id: str
    ):
        policy_id = f"POL-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow()
        
        async with await get_db_connection() as conn:
            row = await conn.fetchrow("""
                INSERT INTO schedule_policies (
                    id, company_id, name, description, policy_type,
                    is_active, priority, rules,
                    applies_to_departments, applies_to_teams, applies_to_roles,
                    enforcement_level, exceptions,
                    created_by, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                RETURNING *
            """, policy_id, company_id, policy.name, policy.description,
                policy.policy_type, policy.is_active, policy.priority,
                json.dumps(policy.rules), policy.applies_to_departments,
                policy.applies_to_teams, policy.applies_to_roles,
                policy.enforcement_level, policy.exceptions,
                user_id, now, now)
            
            logger.info(f"Created schedule policy: {policy_id}")
            return dict(row)
    
    async def list_schedule_policies(
        self, company_id: str, policy_type: Optional[str], is_active: Optional[bool]
    ):
        conditions = ["company_id = $1"]
        params = [company_id]
        param_count = 2
        
        if policy_type:
            conditions.append(f"policy_type = ${param_count}")
            params.append(policy_type)
            param_count += 1
        
        if is_active is not None:
            conditions.append(f"is_active = ${param_count}")
            params.append(is_active)
            param_count += 1
        
        where_clause = " AND ".join(conditions)
        
        async with await get_db_connection() as conn:
            rows = await conn.fetch(f"""
                SELECT * FROM schedule_policies
                WHERE {where_clause}
                ORDER BY priority DESC, created_at DESC
            """, *params)
        
        return [dict(row) for row in rows]
    
    # ============== Analytics ==============
    
    async def get_schedule_analytics(
        self, company_id: str, start_date: date, end_date: date,
        user_id: Optional[str], team_id: Optional[str]
    ):
        async with await get_db_connection() as conn:
            # Base query conditions
            conditions = ["c.company_id = $1", "b.slot_start >= $2", "b.slot_end <= $3"]
            params = [company_id, start_date, end_date]
            param_count = 4
            
            if user_id:
                conditions.append(f"b.assigned_user_id = ${param_count}")
                params.append(user_id)
                param_count += 1
            
            where_clause = " AND ".join(conditions)
            
            # Get booking statistics
            stats = await conn.fetchrow(f"""
                SELECT 
                    COUNT(*) as total_bookings,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                    COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled,
                    COUNT(CASE WHEN status = 'rescheduled' THEN 1 END) as rescheduled,
                    COUNT(CASE WHEN status = 'no_show' THEN 1 END) as no_show,
                    AVG(EXTRACT(EPOCH FROM (slot_end - slot_start))/3600) as avg_duration_hours,
                    AVG(EXTRACT(EPOCH FROM (slot_start - created_at))/86400) as avg_lead_days
                FROM booking b
                JOIN Campaign c ON b.campaign_id = c.id
                WHERE {where_clause}
            """, *params)
            
            # Get utilization metrics
            utilization = await self._calculate_utilization(
                company_id, start_date, end_date, user_id, team_id, conn
            )
            
            # Get peak hours
            peak_hours = await conn.fetch(f"""
                SELECT 
                    EXTRACT(HOUR FROM slot_start) as hour,
                    COUNT(*) as booking_count
                FROM booking b
                JOIN Campaign c ON b.campaign_id = c.id
                WHERE {where_clause}
                GROUP BY hour
                ORDER BY booking_count DESC
                LIMIT 5
            """, *params)
            
            # Get day distribution
            day_distribution = await conn.fetch(f"""
                SELECT 
                    TO_CHAR(slot_start, 'Day') as day_name,
                    COUNT(*) as booking_count
                FROM booking b
                JOIN Campaign c ON b.campaign_id = c.id
                WHERE {where_clause}
                GROUP BY day_name
                ORDER BY booking_count DESC
            """, *params)
            
            # Generate recommendations
            recommendations = self._generate_analytics_recommendations(
                stats, utilization, peak_hours
            )
            
            return {
                "period_start": start_date,
                "period_end": end_date,
                "total_available_hours": utilization['total_available_hours'],
                "total_booked_hours": utilization['total_booked_hours'],
                "utilization_rate": utilization['utilization_rate'],
                "total_bookings": stats['total_bookings'],
                "cancelled_bookings": stats['cancelled'],
                "rescheduled_bookings": stats['rescheduled'],
                "no_show_bookings": stats['no_show'],
                "average_booking_duration": stats['avg_duration_hours'],
                "average_lead_time": stats['avg_lead_days'],
                "peak_hours": [dict(h) for h in peak_hours],
                "slow_hours": [],
                "busiest_users": [],
                "least_utilized_users": [],
                "team_distribution": {},
                "day_of_week_distribution": {d['day_name']: d['booking_count'] for d in day_distribution},
                "time_of_day_distribution": {str(h['hour']): h['booking_count'] for h in peak_hours},
                "meeting_type_distribution": {},
                "optimization_suggestions": recommendations
            }
    
    async def get_utilization_report(
        self, company_id: str, period: str, user_ids: Optional[List[str]]
    ):
        # Calculate date range based on period
        end_date = date.today()
        if period == "day":
            start_date = end_date
        elif period == "week":
            start_date = end_date - timedelta(days=7)
        elif period == "month":
            start_date = end_date - timedelta(days=30)
        else:
            start_date = end_date - timedelta(days=7)
        
        async with await get_db_connection() as conn:
            report = {}
            
            for user_id in user_ids or []:
                user_utilization = await self._calculate_utilization(
                    company_id, start_date, end_date, user_id, None, conn
                )
                report[user_id] = user_utilization
            
            return {
                "period": period,
                "start_date": start_date,
                "end_date": end_date,
                "user_utilization": report,
                "summary": self._summarize_utilization(report)
            }
    
    # ============== Helper Methods ==============
    
    async def _get_user_availability(
        self, user_id: str, start_date: date, end_date: date,
        duration_minutes: int, conn
    ):
        """Get available time slots for a user"""
        # Check for existing bookings
        existing_bookings = await conn.fetch("""
            SELECT slot_start, slot_end FROM booking
            WHERE assigned_user_id = $1
            AND status IN ('pending', 'confirmed')
            AND slot_start::date >= $2
            AND slot_end::date <= $3
            ORDER BY slot_start
        """, user_id, start_date, end_date)
        
        # Convert to busy periods
        busy_periods = [(b['slot_start'], b['slot_end']) for b in existing_bookings]
        
        # Generate available slots
        slots = []
        current_date = start_date
        
        while current_date <= end_date:
            # Skip weekends for now (can be made configurable)
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                # Default working hours: 9 AM to 5 PM
                start_time = datetime.combine(current_date, time(9, 0))
                end_time = datetime.combine(current_date, time(17, 0))
                
                # Generate slots for the day
                current_slot = start_time
                while current_slot + timedelta(minutes=duration_minutes) <= end_time:
                    slot_end = current_slot + timedelta(minutes=duration_minutes)
                    
                    # Check if slot overlaps with any busy period
                    is_available = True
                    for busy_start, busy_end in busy_periods:
                        if not (slot_end <= busy_start or current_slot >= busy_end):
                            is_available = False
                            break
                    
                    if is_available:
                        slots.append({
                            "start": current_slot,
                            "end": slot_end,
                            "available": True,
                            "capacity": 1,
                            "user_ids": [user_id]
                        })
                    
                    current_slot += timedelta(minutes=30)  # 30-minute intervals
            
            current_date += timedelta(days=1)
        
        return slots
    
    def _calculate_collective_availability(
        self, member_availability: Dict, min_members: int
    ):
        """Calculate slots where minimum team members are available"""
        if not member_availability:
            return []
        
        # Collect all unique time slots
        all_slots = set()
        for member_slots in member_availability.values():
            for slot in member_slots:
                all_slots.add((slot['start'], slot['end']))
        
        # Check each slot for minimum availability
        collective_slots = []
        for start, end in all_slots:
            available_members = []
            for member_id, member_slots in member_availability.items():
                for slot in member_slots:
                    if slot['start'] == start and slot['end'] == end:
                        available_members.append(member_id)
                        break
            
            if len(available_members) >= min_members:
                collective_slots.append({
                    "start": start,
                    "end": end,
                    "available": True,
                    "capacity": len(available_members),
                    "user_ids": available_members
                })
        
        return sorted(collective_slots, key=lambda x: x['start'])
    
    def _merge_all_availability(self, member_availability: Dict):
        """Merge all member availability into a single list"""
        all_slots = []
        for member_slots in member_availability.values():
            all_slots.extend(member_slots)
        
        # Remove duplicates and sort
        unique_slots = {}
        for slot in all_slots:
            key = (slot['start'], slot['end'])
            if key in unique_slots:
                unique_slots[key]['user_ids'].extend(slot.get('user_ids', []))
                unique_slots[key]['capacity'] += 1
            else:
                unique_slots[key] = slot.copy()
        
        return sorted(unique_slots.values(), key=lambda x: x['start'])
    
    async def _select_team_member(
        self, member_ids: List[str], method: str,
        start_time: datetime, end_time: datetime, conn
    ):
        """Select a team member based on assignment method"""
        if not member_ids:
            return None
        
        if method == AssignmentMethod.ROUND_ROBIN or method == "round_robin":
            # Get last assigned member and select next
            last_assigned = await conn.fetchval("""
                SELECT assigned_user_id FROM booking
                WHERE assigned_user_id = ANY($1::text[])
                ORDER BY created_at DESC
                LIMIT 1
            """, member_ids)
            
            if last_assigned and last_assigned in member_ids:
                idx = member_ids.index(last_assigned)
                return member_ids[(idx + 1) % len(member_ids)]
            return member_ids[0]
        
        elif method == AssignmentMethod.LEAST_BUSY or method == "least_busy":
            # Select member with fewest bookings
            booking_counts = await conn.fetch("""
                SELECT assigned_user_id, COUNT(*) as count
                FROM booking
                WHERE assigned_user_id = ANY($1::text[])
                AND slot_start >= $2 AND slot_end <= $3
                GROUP BY assigned_user_id
            """, member_ids, start_time.date(), end_time.date())
            
            counts = {r['assigned_user_id']: r['count'] for r in booking_counts}
            # Return member with least bookings (default to 0 for those not in counts)
            return min(member_ids, key=lambda x: counts.get(x, 0))
        
        elif method == AssignmentMethod.RANDOM or method == "random":
            return random.choice(member_ids)
        
        # Default to first member
        return member_ids[0]
    
    async def _apply_buffer_rules(
        self, slots: List, user_id: str, company_id: str, conn
    ):
        """Apply buffer rules to available slots"""
        if not user_id:
            return slots
        
        # Get buffer rules for the user
        buffer_rules = await conn.fetch("""
            SELECT * FROM buffer_rules
            WHERE company_id = $1
            AND (user_id = $2 OR applies_to_all_meetings = true)
            AND is_active = true
        """, company_id, user_id)
        
        if not buffer_rules:
            return slots
        
        # Get the most restrictive buffer rule
        max_before = max((r['buffer_before_minutes'] for r in buffer_rules), default=0)
        max_after = max((r['buffer_after_minutes'] for r in buffer_rules), default=0)
        
        # Filter slots based on buffer requirements
        filtered_slots = []
        for slot in slots:
            # Check if there's enough buffer before and after
            slot_start = slot['start']
            slot_end = slot['end']
            
            # This is a simplified check - in production, you'd check against actual bookings
            needs_buffer_before = slot_start - timedelta(minutes=max_before)
            needs_buffer_after = slot_end + timedelta(minutes=max_after)
            
            # For now, assume the slot is valid if it's within working hours
            if needs_buffer_before.time() >= time(9, 0) and needs_buffer_after.time() <= time(17, 0):
                filtered_slots.append(slot)
        
        return filtered_slots
    
    def _find_common_slots(
        self, availability: Dict, min_attendees: int
    ):
        """Find time slots where minimum attendees are available"""
        if not availability or min_attendees <= 0:
            return []
        
        # Flatten all slots with their owner IDs
        slot_map = defaultdict(list)
        for person_id, slots in availability.items():
            for slot in slots:
                key = (slot['start'], slot['end'])
                slot_map[key].append(person_id)
        
        # Find slots with minimum attendees
        common_slots = []
        for (start, end), attendees in slot_map.items():
            if len(attendees) >= min_attendees:
                common_slots.append({
                    'start': start,
                    'end': end,
                    'available': True,
                    'capacity': len(attendees),
                    'user_ids': attendees
                })
        
        return sorted(common_slots, key=lambda x: x['start'])
    
    def _score_time_slot(
        self, slot: Dict, preferred_times: List[str],
        avoid_times: List[str], urgency: str,
        participant_availability: Dict
    ):
        """Score a time slot based on various factors"""
        score = 0.5  # Base score
        reasons = []
        
        slot_hour = slot['start'].hour
        slot_day = slot['start'].weekday()
        
        # Check preferred times
        if preferred_times:
            for pref in preferred_times:
                if pref == "morning" and 9 <= slot_hour < 12:
                    score += 0.15
                    reasons.append("Morning slot (preferred)")
                elif pref == "afternoon" and 12 <= slot_hour < 17:
                    score += 0.15
                    reasons.append("Afternoon slot (preferred)")
                elif pref == "early" and slot_hour < 10:
                    score += 0.15
                    reasons.append("Early slot (preferred)")
        
        # Check times to avoid
        if avoid_times:
            for avoid in avoid_times:
                if avoid == "lunch" and 12 <= slot_hour < 13:
                    score -= 0.2
                    reasons.append("Lunch hour (avoided)")
                elif avoid == "late" and slot_hour >= 16:
                    score -= 0.15
                    reasons.append("Late afternoon (avoided)")
        
        # Factor in urgency
        if urgency == "high":
            days_out = (slot['start'].date() - date.today()).days
            if days_out <= 1:
                score += 0.25
                reasons.append("Available soon (high urgency)")
            elif days_out <= 3:
                score += 0.15
                reasons.append("Available within 3 days")
        elif urgency == "low":
            days_out = (slot['start'].date() - date.today()).days
            if days_out >= 7:
                score += 0.1
                reasons.append("Flexible scheduling")
        
        # Prefer mid-week
        if 1 <= slot_day <= 3:  # Tuesday to Thursday
            score += 0.1
            reasons.append("Mid-week slot")
        elif slot_day == 0:  # Monday
            score += 0.05
            reasons.append("Start of week")
        elif slot_day == 4:  # Friday
            score -= 0.05
            reasons.append("End of week")
        
        # Prefer mid-morning and mid-afternoon
        if slot_hour in [10, 11, 14, 15]:
            score += 0.1
            reasons.append("Optimal meeting time")
        
        # Ensure score is between 0 and 1
        score = max(0, min(1, score))
        
        return {"total": score, "reasons": reasons}
    
    async def _check_buffer_conflicts(
        self, user_id: str, start_time: datetime,
        end_time: datetime, company_id: str, conn
    ):
        """Check for buffer rule conflicts"""
        conflicts = []
        
        # Get buffer rules
        buffer_rules = await conn.fetch("""
            SELECT * FROM buffer_rules
            WHERE company_id = $1
            AND (user_id = $2 OR applies_to_all_meetings = true)
            AND is_active = true
        """, company_id, user_id)
        
        if not buffer_rules:
            return conflicts
        
        # Get adjacent bookings
        adjacent_bookings = await conn.fetch("""
            SELECT * FROM booking
            WHERE assigned_user_id = $1
            AND status IN ('pending', 'confirmed')
            AND (
                (slot_end BETWEEN $2 AND $3)
                OR (slot_start BETWEEN $2 AND $3)
                OR (slot_end = $2)
                OR (slot_start = $3)
            )
        """, user_id, start_time - timedelta(hours=2), end_time + timedelta(hours=2))
        
        for rule in buffer_rules:
            buffer_before = rule['buffer_before_minutes']
            buffer_after = rule['buffer_after_minutes']
            
            for booking in adjacent_bookings:
                # Check if buffer is violated
                if booking['slot_end'] == start_time:
                    # Booking ends right when new one starts
                    if buffer_after > 0:
                        conflicts.append(ConflictDetail(
                            user_id=user_id,
                            conflict_type="buffer_violation",
                            conflicting_booking_id=booking['id'],
                            description=f"Requires {buffer_after} minute buffer after previous meeting",
                            severity="medium"
                        ))
                
                elif booking['slot_start'] == end_time:
                    # Booking starts right when new one ends
                    if buffer_before > 0:
                        conflicts.append(ConflictDetail(
                            user_id=user_id,
                            conflict_type="buffer_violation",
                            conflicting_booking_id=booking['id'],
                            description=f"Requires {buffer_before} minute buffer before next meeting",
                            severity="medium"
                        ))
        
        return conflicts
    
    def _generate_conflict_resolutions(
        self, conflicts: List[ConflictDetail], request: ScheduleConflictRequest
    ):
        """Generate suggestions to resolve conflicts"""
        suggestions = []
        
        conflict_types = set(c.conflict_type for c in conflicts)
        
        if "booking_overlap" in conflict_types:
            suggestions.append("Consider rescheduling one of the conflicting bookings")
            suggestions.append("Look for alternative time slots with no conflicts")
            
            # Check if any users have no conflicts
            users_with_conflicts = set(c.user_id for c in conflicts)
            users_without_conflicts = set(request.user_ids) - users_with_conflicts
            if users_without_conflicts:
                suggestions.append(f"Users available: {', '.join(users_without_conflicts)}")
        
        if "schedule_override" in conflict_types:
            suggestions.append("Selected time falls during user's time off or blocked period")
            suggestions.append("Choose a different date when all users are available")
            
            # Find users with overrides
            users_with_overrides = [c.user_id for c in conflicts if c.conflict_type == "schedule_override"]
            if users_with_overrides:
                suggestions.append(f"Consider proceeding without: {', '.join(users_with_overrides)}")
        
        if "buffer_violation" in conflict_types:
            suggestions.append("Adjust timing to allow for required buffer between meetings")
            suggestions.append("Consider shortening the meeting duration")
            suggestions.append("Review and potentially adjust buffer rules if too restrictive")
        
        # Always suggest finding optimal times
        suggestions.append("Use the optimal times finder to locate the best available slot")
        
        return suggestions
    
    def _select_best_resource(
        self, available: List, preferences: Dict, required_capacity: Dict
    ):
        """Select the best resource based on criteria"""
        if not available:
            return None
        
        # Score each resource
        scored_resources = []
        for resource in available:
            score = 0
            
            # Check capacity requirements
            if required_capacity:
                resource_type = resource['resource_type']
                if resource_type in required_capacity:
                    if resource['capacity'] >= required_capacity[resource_type]:
                        score += 1
                    else:
                        continue  # Skip if capacity is insufficient
            
            # Check preferences
            if preferences:
                if 'location' in preferences and resource.get('location') == preferences['location']:
                    score += 0.5
                if 'max_cost' in preferences and resource.get('cost', 0) <= preferences['max_cost']:
                    score += 0.3
            
            # Prefer lower cost if all else equal
            if resource.get('cost'):
                score -= resource['cost'] / 1000  # Small penalty for cost
            
            scored_resources.append((score, resource))
        
        if scored_resources:
            # Return resource with highest score
            scored_resources.sort(key=lambda x: x[0], reverse=True)
            return dict(scored_resources[0][1])
        
        return None
    
    async def _calculate_utilization(
        self, company_id: str, start_date: date, end_date: date,
        user_id: Optional[str], team_id: Optional[str], conn
    ):
        """Calculate utilization metrics"""
        # Calculate total available hours
        total_days = (end_date - start_date).days + 1
        weekdays = sum(1 for i in range(total_days) 
                      if (start_date + timedelta(days=i)).weekday() < 5)
        total_available_hours = weekdays * 8  # 8 hours per weekday
        
        # Build query conditions
        conditions = ["c.company_id = $1", "b.slot_start >= $2", "b.slot_end <= $3"]
        params = [company_id, start_date, end_date]
        
        if user_id:
            conditions.append("b.assigned_user_id = $4")
            params.append(user_id)
        
        where_clause = " AND ".join(conditions)
        
        # Get booked hours
        booked_hours = await conn.fetchval(f"""
            SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (slot_end - slot_start))/3600), 0)
            FROM booking b
            JOIN Campaign c ON b.campaign_id = c.id
            WHERE {where_clause}
            AND b.status NOT IN ('cancelled')
        """, *params)
        
        utilization_rate = (booked_hours / total_available_hours) if total_available_hours > 0 else 0
        
        return {
            "total_available_hours": total_available_hours,
            "total_booked_hours": float(booked_hours),
            "utilization_rate": min(1.0, utilization_rate)  # Cap at 100%
        }
    
    def _generate_analytics_recommendations(
        self, stats: Dict, utilization: Dict, peak_hours: List
    ):
        """Generate recommendations based on analytics"""
        recommendations = []
        
        # Utilization-based recommendations
        if utilization['utilization_rate'] < 0.3:
            recommendations.append("Very low utilization - consider promotional campaigns or review pricing")
            recommendations.append("Analyze why bookings are low and address potential barriers")
        elif utilization['utilization_rate'] < 0.5:
            recommendations.append("Below-target utilization - increase marketing efforts")
            recommendations.append("Consider offering promotions during slow periods")
        elif utilization['utilization_rate'] > 0.85:
            recommendations.append("High utilization - consider adding capacity or staff")
            recommendations.append("Risk of burnout - monitor team wellbeing")
        elif utilization['utilization_rate'] > 0.95:
            recommendations.append("Over-utilized - urgent need for additional resources")
            recommendations.append("Consider raising prices to manage demand")
        
        # Cancellation rate recommendations
        if stats and stats['total_bookings'] > 0:
            cancel_rate = stats['cancelled'] / stats['total_bookings']
            if cancel_rate > 0.2:
                recommendations.append("High cancellation rate - implement confirmation reminders")
                recommendations.append("Consider requiring deposits or implementing cancellation fees")
            elif cancel_rate > 0.3:
                recommendations.append("Critical cancellation rate - investigate root causes immediately")
            
            # No-show recommendations
            no_show_rate = stats['no_show'] / stats['total_bookings'] if stats['total_bookings'] > 0 else 0
            if no_show_rate > 0.1:
                recommendations.append("Significant no-shows - implement SMS reminders")
                recommendations.append("Consider overbooking strategy or waitlist system")
        
        # Peak hours recommendations
        if peak_hours:
            peak_hour = peak_hours[0]['hour']
            recommendations.append(f"Peak demand at {peak_hour}:00 - ensure maximum availability")
            
            if len(peak_hours) > 1:
                secondary_peaks = [str(h['hour']) for h in peak_hours[1:3]]
                recommendations.append(f"Secondary peaks at {', '.join(secondary_peaks)}:00")
        
        # Lead time recommendations
        if stats and stats.get('avg_lead_days'):
            if stats['avg_lead_days'] < 1:
                recommendations.append("Very short lead times - customers booking last minute")
                recommendations.append("Consider instant booking confirmations")
            elif stats['avg_lead_days'] > 14:
                recommendations.append("Long lead times - enable advance booking incentives")
        
        # Duration recommendations
        if stats and stats.get('avg_duration_hours'):
            if stats['avg_duration_hours'] < 0.5:
                recommendations.append("Short meetings - consider grouping or minimum durations")
            elif stats['avg_duration_hours'] > 2:
                recommendations.append("Long meetings - ensure adequate breaks between bookings")
        
        return recommendations
    
    def _summarize_utilization(self, report: Dict):
        """Summarize utilization report"""
        if not report:
            return {
                "total_available_hours": 0,
                "total_booked_hours": 0,
                "overall_utilization": 0,
                "user_count": 0
            }
        
        total_available = sum(u.get('total_available_hours', 0) for u in report.values())
        total_booked = sum(u.get('total_booked_hours', 0) for u in report.values())
        
        # Identify best and worst performers
        user_utilizations = {
            user_id: util.get('utilization_rate', 0) 
            for user_id, util in report.items()
        }
        
        best_performers = sorted(
            user_utilizations.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:3]
        
        worst_performers = sorted(
            user_utilizations.items(), 
            key=lambda x: x[1]
        )[:3]
        
        return {
            "total_available_hours": total_available,
            "total_booked_hours": total_booked,
            "overall_utilization": (total_booked / total_available) if total_available > 0 else 0,
            "user_count": len(report),
            "best_performers": [
                {"user_id": uid, "utilization": rate} 
                for uid, rate in best_performers
            ],
            "worst_performers": [
                {"user_id": uid, "utilization": rate} 
                for uid, rate in worst_performers
            ],
            "average_utilization": sum(user_utilizations.values()) / len(user_utilizations) if user_utilizations else 0
        }