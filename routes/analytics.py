from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List
from datetime import date, datetime
import asyncpg

from app.db.postgres_client import get_db_pool
from handlers.analytics_handler import AnalyticsHandler
from app.models.analytics import (
    ConversationOutcome, AnalyticsDashboard, LeadDetail
)
from middleware.auth_middleware import verify_token

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.post("/record-outcome")
async def record_conversation_outcome(
    outcome_data: ConversationOutcome,
    db_pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(verify_token)
):
    try:
        handler = AnalyticsHandler(db_pool)
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
    db_pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(verify_token)
):
    try:
        handler = AnalyticsHandler(db_pool)
        dashboard_data = await handler.get_dashboard_data(start_date, end_date)
        return dashboard_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/leads", response_model=List[LeadDetail])
async def get_leads_for_followup(
    db_pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(verify_token)
):
    try:
        handler = AnalyticsHandler(db_pool)
        leads = await handler.get_leads_for_followup()
        return leads
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export/leads")
async def export_leads_csv(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db_pool: asyncpg.Pool = Depends(get_db_pool),
    current_user: dict = Depends(verify_token)
):
    """Export leads data as CSV"""
    # Implementation for CSV export
    pass
