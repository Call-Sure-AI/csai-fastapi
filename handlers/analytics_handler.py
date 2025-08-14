from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
import asyncpg
from app.db.queries.analytics_queries import AnalyticsQueries
from app.models.analytics import (
    ConversationOutcome, DailyAnalytics, AgentPerformance, 
    LeadDetail, AnalyticsDashboard
)

class AnalyticsHandler:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.queries = AnalyticsQueries()

    async def record_conversation_outcome(
        self, 
        call_id: str,
        user_phone: str,
        conversation_duration: int,
        outcome: str,
        lead_score: int,
        extracted_details: Dict[str, Any],
        agent_id: str
    ) -> str:

        try:
            outcome_id = await self.queries.create_conversation_outcome(
                self.db_pool, call_id, user_phone, conversation_duration,
                outcome, lead_score, extracted_details, agent_id
            )
            return outcome_id
        except Exception as e:
            raise Exception(f"Failed to record conversation outcome: {str(e)}")

    async def get_dashboard_data(
        self, 
        start_date: Optional[date] = None, 
        end_date: Optional[date] = None
    ) -> AnalyticsDashboard:

        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        try:
            daily_stats = await self.queries.get_daily_analytics(
                self.db_pool, start_date, end_date
            )

            agent_performance = await self.queries.get_agent_performance(self.db_pool)

            recent_leads = await self.queries.get_lead_details(
                self.db_pool, 'interested'
            )

            total_calls = sum(stat['total_calls'] for stat in daily_stats)
            total_interested = sum(stat['interested_leads'] for stat in daily_stats)
            total_callbacks = sum(stat['callback_requests'] for stat in daily_stats)
            
            total_metrics = {
                'total_calls': total_calls,
                'total_interested_leads': total_interested,
                'total_callback_requests': total_callbacks,
                'overall_conversion_rate': round(
                    (total_interested + total_callbacks) * 100.0 / total_calls, 2
                ) if total_calls > 0 else 0
            }

            return AnalyticsDashboard(
                daily_stats=[DailyAnalytics(**stat) for stat in daily_stats],
                agent_performance=[AgentPerformance(**perf) for perf in agent_performance],
                recent_leads=[LeadDetail(**lead) for lead in recent_leads[:50]],
                total_metrics=total_metrics
            )
        except Exception as e:
            raise Exception(f"Failed to get dashboard data: {str(e)}")

    async def get_leads_for_followup(self) -> List[LeadDetail]:
        try:
            interested_leads = await self.queries.get_lead_details(
                self.db_pool, 'interested'
            )
            callback_leads = await self.queries.get_lead_details(
                self.db_pool, 'callback_requested'
            )
            
            all_leads = interested_leads + callback_leads
            return [LeadDetail(**lead) for lead in all_leads]
        except Exception as e:
            raise Exception(f"Failed to get leads for followup: {str(e)}")
