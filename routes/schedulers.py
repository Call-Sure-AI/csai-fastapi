from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, date, time
import uuid

from app.models.schemas import UserResponse
from middleware.auth_middleware import get_current_user
from handlers.company_handler import CompanyHandler
from app.services.scheduling_service import SchedulingService
from app.models.scheduling_schemas import (
    AvailabilityTemplateCreate,
    AvailabilityTemplateUpdate,
    AvailabilityTemplateResponse,
    BookingRuleCreate,
    BookingRuleUpdate,
    BookingRuleResponse,
    RecurringAvailabilityCreate,
    RecurringAvailabilityUpdate,
    RecurringAvailabilityResponse,
    ScheduleOverrideCreate,
    ScheduleOverrideUpdate,
    ScheduleOverrideResponse,
    BufferRuleCreate,
    BufferRuleUpdate,
    BufferRuleResponse,
    TeamScheduleCreate,
    TeamScheduleUpdate,
    TeamScheduleResponse,
    AvailabilityCheckRequest,
    AvailabilityCheckResponse,
    OptimalTimesRequest,
    OptimalTimesResponse,
    ScheduleConflictRequest,
    ScheduleConflictResponse,
    BulkAvailabilityRequest,
    BulkAvailabilityResponse,
    ScheduleAnalyticsResponse,
    ResourceAllocationRequest,
    ResourceAllocationResponse,
    SchedulePolicyCreate,
    SchedulePolicyUpdate,
    SchedulePolicyResponse
)

router = APIRouter(prefix="/scheduling", tags=["Scheduling"])

async def _ensure_user_access(current_user: UserResponse, company_handler: CompanyHandler):
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    return company["id"]

# ============== Availability Templates ==============

@router.post("/templates", response_model=AvailabilityTemplateResponse)
async def create_availability_template(
    template: AvailabilityTemplateCreate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Create a reusable availability template for users or teams"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    result = await service.create_availability_template(
        company_id, template, current_user.id
    )
    return result

@router.get("/templates", response_model=List[AvailabilityTemplateResponse])
async def list_availability_templates(
    user_id: Optional[str] = Query(None),
    is_default: Optional[bool] = Query(None),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """List all availability templates for the company"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    templates = await service.list_availability_templates(
        company_id, user_id, is_default
    )
    return templates

@router.get("/templates/{template_id}", response_model=AvailabilityTemplateResponse)
async def get_availability_template(
    template_id: str,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Get a specific availability template"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    template = await service.get_availability_template(template_id, company_id)
    
    if not template:
        raise HTTPException(404, "Template not found")
    
    return template

@router.put("/templates/{template_id}", response_model=AvailabilityTemplateResponse)
async def update_availability_template(
    template_id: str,
    updates: AvailabilityTemplateUpdate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Update an availability template"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    updated = await service.update_availability_template(
        template_id, company_id, updates
    )
    
    if not updated:
        raise HTTPException(404, "Template not found")
    
    return updated

@router.delete("/templates/{template_id}", status_code=204)
async def delete_availability_template(
    template_id: str,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Delete an availability template"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    deleted = await service.delete_availability_template(template_id, company_id)
    
    if not deleted:
        raise HTTPException(404, "Template not found")

@router.post("/templates/{template_id}/apply")
async def apply_template_to_users(
    template_id: str,
    user_ids: List[str],
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Apply an availability template to multiple users"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    result = await service.apply_template_to_users(
        template_id, company_id, user_ids
    )
    
    return {"message": f"Template applied to {result['applied_count']} users"}

# ============== Booking Rules ==============

@router.post("/rules", response_model=BookingRuleResponse)
async def create_booking_rule(
    rule: BookingRuleCreate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Create a booking rule (e.g., min notice, max per day, etc.)"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    result = await service.create_booking_rule(
        company_id, rule, current_user.id
    )
    return result

@router.get("/rules", response_model=List[BookingRuleResponse])
async def list_booking_rules(
    rule_type: Optional[str] = Query(None),
    applies_to: Optional[str] = Query(None, description="user_id, team_id, or 'global'"),
    is_active: Optional[bool] = Query(None),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """List all booking rules"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    rules = await service.list_booking_rules(
        company_id, rule_type, applies_to, is_active
    )
    return rules

@router.put("/rules/{rule_id}", response_model=BookingRuleResponse)
async def update_booking_rule(
    rule_id: str,
    updates: BookingRuleUpdate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Update a booking rule"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    updated = await service.update_booking_rule(rule_id, company_id, updates)
    
    if not updated:
        raise HTTPException(404, "Rule not found")
    
    return updated

@router.delete("/rules/{rule_id}", status_code=204)
async def delete_booking_rule(
    rule_id: str,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Delete a booking rule"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    deleted = await service.delete_booking_rule(rule_id, company_id)
    
    if not deleted:
        raise HTTPException(404, "Rule not found")

# ============== Recurring Availability ==============

@router.post("/recurring", response_model=RecurringAvailabilityResponse)
async def create_recurring_availability(
    availability: RecurringAvailabilityCreate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Set up recurring availability patterns"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    result = await service.create_recurring_availability(
        company_id, availability, current_user.id
    )
    return result

@router.get("/recurring", response_model=List[RecurringAvailabilityResponse])
async def list_recurring_availability(
    user_id: Optional[str] = Query(None),
    day_of_week: Optional[str] = Query(None),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """List recurring availability patterns"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    patterns = await service.list_recurring_availability(
        company_id, user_id, day_of_week
    )
    return patterns

@router.put("/recurring/{pattern_id}", response_model=RecurringAvailabilityResponse)
async def update_recurring_availability(
    pattern_id: str,
    updates: RecurringAvailabilityUpdate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Update a recurring availability pattern"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    updated = await service.update_recurring_availability(
        pattern_id, company_id, updates
    )
    
    if not updated:
        raise HTTPException(404, "Pattern not found")
    
    return updated

# ============== Schedule Overrides ==============

@router.post("/overrides", response_model=ScheduleOverrideResponse)
async def create_schedule_override(
    override: ScheduleOverrideCreate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Create a one-time schedule override (holidays, time off, etc.)"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    result = await service.create_schedule_override(
        company_id, override, current_user.id
    )
    return result

@router.get("/overrides", response_model=List[ScheduleOverrideResponse])
async def list_schedule_overrides(
    user_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    override_type: Optional[str] = Query(None),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """List schedule overrides"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    overrides = await service.list_schedule_overrides(
        company_id, user_id, start_date, end_date, override_type
    )
    return overrides

@router.delete("/overrides/{override_id}", status_code=204)
async def delete_schedule_override(
    override_id: str,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Delete a schedule override"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    deleted = await service.delete_schedule_override(override_id, company_id)
    
    if not deleted:
        raise HTTPException(404, "Override not found")

# ============== Buffer Rules ==============

@router.post("/buffers", response_model=BufferRuleResponse)
async def create_buffer_rule(
    buffer: BufferRuleCreate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Create buffer time rules between appointments"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    result = await service.create_buffer_rule(
        company_id, buffer, current_user.id
    )
    return result

@router.get("/buffers", response_model=List[BufferRuleResponse])
async def list_buffer_rules(
    user_id: Optional[str] = Query(None),
    meeting_type: Optional[str] = Query(None),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """List buffer time rules"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    buffers = await service.list_buffer_rules(
        company_id, user_id, meeting_type
    )
    return buffers

# ============== Team Scheduling ==============

@router.post("/teams", response_model=TeamScheduleResponse)
async def create_team_schedule(
    schedule: TeamScheduleCreate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Create team scheduling rules (round-robin, collective availability, etc.)"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    result = await service.create_team_schedule(
        company_id, schedule, current_user.id
    )
    return result

@router.get("/teams/{team_id}/availability")
async def get_team_availability(
    team_id: str,
    start_date: date = Query(...),
    end_date: date = Query(...),
    duration_minutes: int = Query(30),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Get collective team availability"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    availability = await service.get_team_availability(
        team_id, company_id, start_date, end_date, duration_minutes
    )
    return availability

@router.post("/teams/{team_id}/assign")
async def assign_team_member(
    team_id: str,
    booking_id: str,
    assignment_method: str = Query("round_robin", description="round_robin, least_busy, random, manual"),
    preferred_member_id: Optional[str] = Query(None),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Assign a team member to a booking"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    result = await service.assign_team_member(
        team_id, booking_id, company_id, assignment_method, preferred_member_id
    )
    return result

# ============== Availability Checking ==============

@router.post("/check-availability", response_model=AvailabilityCheckResponse)
async def check_availability(
    request: AvailabilityCheckRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Check availability for a specific user/team and time range"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    result = await service.check_availability(company_id, request)
    return result

@router.post("/bulk-availability", response_model=BulkAvailabilityResponse)
async def check_bulk_availability(
    request: BulkAvailabilityRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Check availability for multiple users/teams"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    result = await service.check_bulk_availability(company_id, request)
    return result

# ============== Optimal Times ==============

@router.post("/optimal-times", response_model=OptimalTimesResponse)
async def find_optimal_times(
    request: OptimalTimesRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Find optimal meeting times based on preferences and constraints"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    result = await service.find_optimal_times(company_id, request)
    return result

# ============== Conflict Detection ==============

@router.post("/conflicts", response_model=ScheduleConflictResponse)
async def check_conflicts(
    request: ScheduleConflictRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Check for scheduling conflicts"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    result = await service.check_conflicts(company_id, request)
    return result

# ============== Resource Allocation ==============

@router.post("/resources/allocate", response_model=ResourceAllocationResponse)
async def allocate_resources(
    request: ResourceAllocationRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Allocate resources (rooms, equipment, etc.) for bookings"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    result = await service.allocate_resources(company_id, request)
    return result

@router.get("/resources/availability")
async def get_resource_availability(
    resource_type: str = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Get availability of resources"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    availability = await service.get_resource_availability(
        company_id, resource_type, start_date, end_date
    )
    return availability

# ============== Schedule Policies ==============

@router.post("/policies", response_model=SchedulePolicyResponse)
async def create_schedule_policy(
    policy: SchedulePolicyCreate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Create company-wide scheduling policies"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    result = await service.create_schedule_policy(
        company_id, policy, current_user.id
    )
    return result

@router.get("/policies", response_model=List[SchedulePolicyResponse])
async def list_schedule_policies(
    policy_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """List scheduling policies"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    policies = await service.list_schedule_policies(
        company_id, policy_type, is_active
    )
    return policies

# ============== Analytics ==============

@router.get("/analytics", response_model=ScheduleAnalyticsResponse)
async def get_schedule_analytics(
    start_date: date = Query(...),
    end_date: date = Query(...),
    user_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Get scheduling analytics and insights"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    analytics = await service.get_schedule_analytics(
        company_id, start_date, end_date, user_id, team_id
    )
    return analytics

@router.get("/utilization")
async def get_utilization_report(
    period: str = Query("week", description="day, week, month"),
    user_ids: Optional[List[str]] = Query(None),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """Get resource utilization report"""
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = SchedulingService()
    report = await service.get_utilization_report(
        company_id, period, user_ids
    )
    return report