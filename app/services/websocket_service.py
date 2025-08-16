import json
import asyncio
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
from app.models.schemas import CampaignLiveStatus, CampaignMetrics, WebSocketMessage
from app.services.campaign_service import CampaignService
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.live_connections: Dict[str, Set[WebSocket]] = {}
        self.metrics_connections: Dict[str, Set[WebSocket]] = {}
        
    async def connect_live(self, websocket: WebSocket, campaign_id: str):
        await websocket.accept()
        if campaign_id not in self.live_connections:
            self.live_connections[campaign_id] = set()
        self.live_connections[campaign_id].add(websocket)
        logger.info(f"Live connection added for campaign {campaign_id}")
        
    async def connect_metrics(self, websocket: WebSocket, campaign_id: str):
        await websocket.accept()
        if campaign_id not in self.metrics_connections:
            self.metrics_connections[campaign_id] = set()
        self.metrics_connections[campaign_id].add(websocket)
        logger.info(f"Metrics connection added for campaign {campaign_id}")
        
    async def disconnect_live(self, websocket: WebSocket, campaign_id: str):
        if campaign_id in self.live_connections:
            self.live_connections[campaign_id].discard(websocket)
            if not self.live_connections[campaign_id]:
                del self.live_connections[campaign_id]
        logger.info(f"Live connection removed for campaign {campaign_id}")
        
    async def disconnect_metrics(self, websocket: WebSocket, campaign_id: str):
        if campaign_id in self.metrics_connections:
            self.metrics_connections[campaign_id].discard(websocket)
            if not self.metrics_connections[campaign_id]:
                del self.metrics_connections[campaign_id]
        logger.info(f"Metrics connection removed for campaign {campaign_id}")
        
    async def broadcast_live_status(self, campaign_id: str, status: CampaignLiveStatus):
        if campaign_id in self.live_connections:
            message = WebSocketMessage(type="status", data=status.dict())
            await self._broadcast_to_connections(
                self.live_connections[campaign_id], 
                message.dict()
            )
            
    async def broadcast_metrics(self, campaign_id: str, metrics: CampaignMetrics):
        if campaign_id in self.metrics_connections:
            message = WebSocketMessage(type="metrics", data=metrics.dict())
            await self._broadcast_to_connections(
                self.metrics_connections[campaign_id], 
                message.dict()
            )
            
    async def _broadcast_to_connections(self, connections: Set[WebSocket], data: dict):
        disconnected = set()
        for websocket in connections:
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.warning(f"Failed to send to websocket: {e}")
                disconnected.add(websocket)

        for ws in disconnected:
            connections.discard(ws)

manager = ConnectionManager()

class WebSocketService:
    def __init__(self):
        self.campaign_service = CampaignService()
        
    async def get_live_status(self, campaign_id: str, company_id: str) -> CampaignLiveStatus:

        campaign = await self.campaign_service.get_campaign(campaign_id, company_id)
        if not campaign:
            raise ValueError("Campaign not found")

        return CampaignLiveStatus(
            campaign_id=campaign_id,
            status=campaign.get("status", "active"),
            current_phase="calling",
            active_agents=2,
            queue_size=15,
            last_activity=datetime.utcnow().isoformat()
        )
        
    async def get_current_metrics(self, campaign_id: str, company_id: str) -> CampaignMetrics:
        try:
            metrics = await self.campaign_service.get_realtime_metrics(campaign_id)
            
            return CampaignMetrics(
                campaign_id=campaign_id,            
                calls_made=metrics.get("calls_handled", 0),
                calls_answered=metrics.get("calls_success", 0),
                calls_successful=metrics.get("calls_success", 0),
                bookings_scheduled=metrics.get("bookings_made", 0),
                leads_contacted=metrics.get("calls_handled", 0),
                conversion_rate=round(
                    (metrics.get("calls_success", 0) / max(metrics.get("calls_handled", 1), 1)) * 100, 2
                )
            )
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return CampaignMetrics(campaign_id=campaign_id)
            
    async def start_live_updates(self, campaign_id: str, company_id: str):
        asyncio.create_task(self._live_update_loop(campaign_id, company_id))
        
    async def start_metrics_updates(self, campaign_id: str, company_id: str):
        asyncio.create_task(self._metrics_update_loop(campaign_id, company_id))
        
    async def _live_update_loop(self, campaign_id: str, company_id: str):
        while campaign_id in manager.live_connections:
            try:
                status = await self.get_live_status(campaign_id, company_id)
                await manager.broadcast_live_status(campaign_id, status)
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Live update error: {e}")
                await asyncio.sleep(5)
                
    async def _metrics_update_loop(self, campaign_id: str, company_id: str):

        while campaign_id in manager.metrics_connections:          
            try:
                metrics = await self.get_current_metrics(campaign_id, company_id)
                await manager.broadcast_metrics(campaign_id, metrics)
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Metrics update error: {e}")
                await asyncio.sleep(10)
