from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List
from datetime import date
from handlers.analytics_handler import AnalyticsHandler
from middleware.auth_middleware import get_current_user
from handlers.company_handler import CompanyHandler
from app.models.analytics import ConversationOutcome, AnalyticsDashboard, LeadDetail
from app.models.schemas import (
    UserResponse, BookingAnalytics, AIPerformanceMetrics, 
    CallInsights, ConversionFunnel, OptimalTimes
)
from app.services.analytics_service import AnalyticsService
from middleware.auth_middleware import verify_token

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.post("/record-outcome")
async def record_conversation_outcome(
    outcome_data: ConversationOutcome,
    current_user: dict = Depends(verify_token)
):

    try:
        handler = AnalyticsHandler()
        outcome_id = await handler.record_conversation_outcome(
            outcome_data.call_id,
            outcome_data.user_phone,
            outcome_data.conversation_duration,
            outcome_data.outcome,
            outcome_data.lead_score,
            outcome_data.extracted_details,
            outcome_data.agent_id
        )
        return {"success": True, "outcome_id": outcome_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard", response_model=AnalyticsDashboard)
async def get_analytics_dashboard(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: dict = Depends(verify_token)
):

    try:
        handler = AnalyticsHandler()
        dashboard_data = await handler.get_dashboard_data(start_date, end_date)
        return dashboard_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/leads", response_model=List[LeadDetail])
async def get_leads_for_followup(
    current_user: dict = Depends(verify_token)
):

    try:
        handler = AnalyticsHandler()
        leads = await handler.get_leads_for_followup()
        return leads
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def _ensure_user_access(current_user: UserResponse, company_handler: CompanyHandler):
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    return company["id"]

@router.get("/bookings", response_model=BookingAnalytics)
async def booking_analytics(
    start_date: Optional[date] = Query(None, description="Start date for analytics"),
    end_date: Optional[date] = Query(None, description="End date for analytics"),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = AnalyticsService()
    analytics = await service.get_booking_analytics(company_id, start_date, end_date)
    
    return analytics

@router.get("/ai-performance", response_model=AIPerformanceMetrics)
async def ai_performance_metrics(
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = AnalyticsService()
    metrics = await service.get_ai_performance_metrics(company_id)
    
    return metrics

@router.get("/call-insights", response_model=CallInsights)
async def call_pattern_insights(
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = AnalyticsService()
    insights = await service.get_call_insights(company_id)
    
    return insights

@router.get("/conversion-funnel", response_model=ConversionFunnel)
async def conversion_funnel_metrics(
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = AnalyticsService()
    funnel = await service.get_conversion_funnel(company_id)
    
    return funnel

@router.get("/optimal-times", response_model=OptimalTimes)
async def best_call_time_analysis(
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = AnalyticsService()
    optimal_times = await service.get_optimal_call_times(company_id)
    
    return optimal_times