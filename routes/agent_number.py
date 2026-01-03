# routes\agent_number.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from app.db.postgres_client import get_db_connection
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-numbers")


def serialize_agent_number(row_dict: dict) -> dict:
    """Convert database row to JSON-serializable dict with UUID handling"""
    result = {}
    for key, value in row_dict.items():
        if hasattr(value, 'hex'):  # UUID object
            result[key] = str(value)
        else:
            result[key] = value
    return result


class AgentNumberCreate(BaseModel):
    company_id: str = Field(..., description="Company ID")
    agent_id: str = Field(..., description="Agent ID")
    phone_number: str = Field(..., max_length=20, description="Phone number")
    provider: Optional[str] = Field("twilio", max_length=20, description="Provider (twilio/exotel)")  # ✅ ADD THIS
    account_sid: Optional[str] = Field(None, max_length=255, description="Twilio Account SID")
    auth_token: Optional[str] = Field(None, max_length=255, description="Twilio Auth Token")
    messaging_service_sid: Optional[str] = Field(None, max_length=255, description="Twilio Messaging Service SID")
    agent_name: Optional[str] = Field(None, max_length=255, description="Agent Name")


class AgentNumberUpdate(BaseModel):
    agent_id: Optional[str] = None
    phone_number: Optional[str] = None
    provider: Optional[str] = None
    account_sid: Optional[str] = None
    auth_token: Optional[str] = None
    messaging_service_sid: Optional[str] = None
    agent_name: Optional[str] = None


class AgentNumberResponse(BaseModel):
    id: str
    company_id: str
    agent_id: Optional[str]
    phone_number: str
    provider: Optional[str]
    account_sid: Optional[str]
    auth_token: Optional[str]
    messaging_service_sid: Optional[str]
    agent_name: Optional[str]


@router.post("/", response_model=AgentNumberResponse)
async def create_agent_number(payload: AgentNumberCreate):
    """
    Create a new agent number with Twilio credentials
    """
    try:
        async with await get_db_connection() as conn:
            # Check if company exists
            company_check = await conn.fetchrow(
                'SELECT id FROM public."Company" WHERE id = $1',
                payload.company_id
            )
            if not company_check:
                raise HTTPException(status_code=404, detail="Company not found")
            
            # Check if agent exists
            if payload.agent_id:
                agent_check = await conn.fetchrow(
                    'SELECT id FROM public."Agent" WHERE id = $1',
                    payload.agent_id
                )
                if not agent_check:
                    raise HTTPException(status_code=404, detail="Agent not found")
            
            # Check if phone number already exists for this company
            existing = await conn.fetchrow(
                'SELECT id FROM public."AgentNumber" WHERE company_id = $1 AND phone_number = $2',
                payload.company_id, payload.phone_number
            )
            if existing:
                raise HTTPException(
                    status_code=400, 
                    detail="Phone number already exists for this company"
                )
            
            # Insert new agent number
            row = await conn.fetchrow("""
                INSERT INTO public."AgentNumber" (
                    company_id, agent_id, phone_number, provider, account_sid,   # ✅ ADD provider
                    auth_token, messaging_service_sid, agent_name
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id, company_id, agent_id, phone_number, provider, account_sid,  # ✅ ADD provider
                        auth_token, messaging_service_sid, agent_name
            """, 
                payload.company_id,
                payload.agent_id,
                payload.phone_number,
                payload.provider or "twilio",  # ✅ ADD THIS
                payload.account_sid,
                payload.auth_token,
                payload.messaging_service_sid,
                payload.agent_name
            )

            row_dict = serialize_agent_number(dict(row))
            
            logger.info(f"Created agent number {row_dict['id']} for company {payload.company_id}")
            return AgentNumberResponse(**row_dict)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating agent number: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create agent number: {str(e)}")


@router.get("/{agent_number_id}", response_model=AgentNumberResponse)
async def get_agent_number(agent_number_id: str):
    """
    Get a specific agent number by ID
    """
    try:
        async with await get_db_connection() as conn:
            row = await conn.fetchrow("""
                SELECT id, company_id, agent_id, phone_number, provider, account_sid,  # ✅ ADD provider
                    auth_token, messaging_service_sid, agent_name
                FROM public."AgentNumber"
                WHERE id = $1
            """, agent_number_id)
            
            if not row:
                raise HTTPException(status_code=404, detail="Agent number not found")
            
            return AgentNumberResponse(**serialize_agent_number(dict(row)))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching agent number: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch agent number")


@router.get("/company/{company_id}")
async def get_company_agent_numbers(company_id: str):
    """
    Get all agent numbers for a company
    """
    try:
        async with await get_db_connection() as conn:
            rows = await conn.fetch("""
                SELECT id, company_id, agent_id, phone_number, provider, account_sid,  # ✅ ADD provider
                    auth_token, messaging_service_sid, agent_name
                FROM public."AgentNumber"
                WHERE company_id = $1
                ORDER BY phone_number
            """, company_id)
            
            return {
                "company_id": company_id,
                "agent_numbers": [serialize_agent_number(dict(row)) for row in rows],
                "count": len(rows)
            }
            
    except Exception as e:
        logger.error(f"Error fetching company agent numbers: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch agent numbers")


@router.put("/{agent_number_id}", response_model=AgentNumberResponse)
async def update_agent_number(agent_number_id: str, payload: AgentNumberUpdate):
    """
    Update an existing agent number
    """
    try:
        async with await get_db_connection() as conn:
            # Check if agent number exists
            existing = await conn.fetchrow(
                'SELECT id FROM public."AgentNumber" WHERE id = $1',
                agent_number_id
            )
            if not existing:
                raise HTTPException(status_code=404, detail="Agent number not found")
            
            # Build update query dynamically
            updates = []
            values = []
            param_count = 1
            
            if payload.agent_id is not None:
                updates.append(f"agent_id = ${param_count}")
                values.append(payload.agent_id)
                param_count += 1
            
            if payload.phone_number is not None:
                updates.append(f"phone_number = ${param_count}")
                values.append(payload.phone_number)
                param_count += 1
            
            if payload.account_sid is not None:
                updates.append(f"account_sid = ${param_count}")
                values.append(payload.account_sid)
                param_count += 1
            
            if payload.auth_token is not None:
                updates.append(f"auth_token = ${param_count}")
                values.append(payload.auth_token)
                param_count += 1
            
            if payload.messaging_service_sid is not None:
                updates.append(f"messaging_service_sid = ${param_count}")
                values.append(payload.messaging_service_sid)
                param_count += 1
            
            if payload.agent_name is not None:
                updates.append(f"agent_name = ${param_count}")
                values.append(payload.agent_name)
                param_count += 1

            if payload.provider is not None:
                updates.append(f"provider = ${param_count}")
                values.append(payload.provider)
                param_count += 1
            
            if not updates:
                raise HTTPException(status_code=400, detail="No fields to update")
            
            values.append(agent_number_id)
            
            query = f"""
                UPDATE public."AgentNumber"
                SET {', '.join(updates)}
                WHERE id = ${param_count}
                RETURNING id, company_id, agent_id, phone_number, account_sid, 
                          auth_token, messaging_service_sid, agent_name
            """
            
            row = await conn.fetchrow(query, *values)
            
            logger.info(f"Updated agent number {agent_number_id}")
            return AgentNumberResponse(**serialize_agent_number(dict(row)))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating agent number: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update agent number")


@router.delete("/{agent_number_id}")
async def delete_agent_number(agent_number_id: str):
    """
    Delete an agent number
    """
    try:
        async with await get_db_connection() as conn:
            result = await conn.execute(
                'DELETE FROM public."AgentNumber" WHERE id = $1',
                agent_number_id
            )
            
            if result == "DELETE 0":
                raise HTTPException(status_code=404, detail="Agent number not found")
            
            logger.info(f"Deleted agent number {agent_number_id}")
            return {"message": "Agent number deleted successfully", "id": agent_number_id}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent number: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete agent number")