from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
from app.db.queries.analytics_queries import AnalyticsQueries
from app.db.queries.conversation_queries import ConversationQueries
from app.models.analytics import (
    ConversationOutcome, DailyAnalytics, AgentPerformance, 
    LeadDetail, AnalyticsDashboard
)
import logging

logger = logging.getLogger(__name__)

class AnalyticsHandler:
    def __init__(self):
        self.queries = AnalyticsQueries()
        self.conversation_queries = ConversationQueries()

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
            await self._ensure_conversation_exists(call_id, user_phone, agent_id, conversation_duration, outcome)

            outcome_id = await self.queries.create_conversation_outcome(
                call_id, user_phone, conversation_duration,
                outcome, lead_score, extracted_details, agent_id
            )
            return str(outcome_id)
        except Exception as e:
            logger.error(f"Failed to record conversation outcome: {str(e)}")
            raise Exception(f"Failed to record conversation outcome: {str(e)}")

    async def _ensure_conversation_exists(self, call_id: str, user_phone: str, agent_id: str, duration: int, outcome: str):
        try:
            from app.db.postgres_client import get_db_connection
            
            async with await get_db_connection() as conn:
                existing = await conn.fetchrow(
                    "SELECT id FROM Conversation WHERE call_id = $1", call_id
                )
                
                if not existing:
                    await conn.execute("""
                        INSERT INTO Conversation (call_id, user_phone, agent_id, status, duration, outcome, created_at, updated_at)
                        VALUES ($1, $2, $3, 'completed', $4, $5, $6, $7)
                    """, call_id, user_phone, agent_id, duration, outcome, datetime.utcnow(), datetime.utcnow())
                else:
                    await conn.execute("""
                        UPDATE Conversation 
                        SET duration = $2, outcome = $3, status = 'completed', updated_at = $4
                        WHERE call_id = $1
                    """, call_id, duration, outcome, datetime.utcnow())
                    
        except Exception as e:
            logger.warning(f"Could not ensure conversation exists for {call_id}: {str(e)}")

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
            daily_stats = await self.queries.get_daily_analytics(start_date, end_date)
            agent_performance = await self.queries.get_agent_performance()

            try:
                recent_leads = await self.queries.get_lead_details('interested')
            except Exception as e:
                logger.error(f"Error getting recent leads: {str(e)}")
                recent_leads = []

            total_calls = sum(stat.get('total_calls', 0) for stat in daily_stats)
            total_interested = sum(stat.get('interested_leads', 0) for stat in daily_stats)
            total_callbacks = sum(stat.get('callback_requests', 0) for stat in daily_stats)
            
            total_metrics = {
                'total_calls': total_calls,
                'total_interested_leads': total_interested,
                'total_callback_requests': total_callbacks,
                'overall_conversion_rate': round(
                    (total_interested + total_callbacks) * 100.0 / total_calls, 2
                ) if total_calls > 0 else 0
            }

            try:
                daily_stats_models = [DailyAnalytics(**stat) for stat in daily_stats]
            except Exception as e:
                logger.error(f"Error creating daily stats models: {str(e)}")
                daily_stats_models = []

            try:
                agent_performance_models = [AgentPerformance(**perf) for perf in agent_performance]
            except Exception as e:
                logger.error(f"Error creating agent performance models: {str(e)}")
                agent_performance_models = []

            try:
                recent_leads_models = [LeadDetail(**lead) for lead in recent_leads[:50]]
            except Exception as e:
                logger.error(f"Error creating lead detail models: {str(e)}")
                logger.error(f"Lead data causing error: {recent_leads}")
                recent_leads_models = []

            return AnalyticsDashboard(
                daily_stats=daily_stats_models,
                agent_performance=agent_performance_models,
                recent_leads=recent_leads_models,
                total_metrics=total_metrics
            )
        except Exception as e:
            logger.error(f"Failed to get dashboard data: {str(e)}")
            raise Exception(f"Failed to get dashboard data: {str(e)}")

    async def get_leads_for_followup(self) -> List[LeadDetail]:
        try:
            interested_leads = await self.queries.get_lead_details('interested')
            callback_leads = await self.queries.get_lead_details('callback_requested')
            
            all_leads = interested_leads + callback_leads
            return [LeadDetail(**lead) for lead in all_leads]
        except Exception as e:
            logger.error(f"Failed to get leads for followup: {str(e)}")
            raise Exception(f"Failed to get leads for followup: {str(e)}")
