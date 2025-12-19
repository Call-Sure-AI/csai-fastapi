# routes/phone_numbers.py
"""
Phone Number Management

Rules:
- One phone number per agent (DB-enforced)
- Numbers stored in AgentNumber table
"""


from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Literal
import base64
import httpx
import logging

from middleware.auth_middleware import get_current_user
from config import Config
from app.db.queries.agent_number_queries import create_agent_number
from handlers.company_handler import CompanyHandler
from app.models.schemas import UserResponse

logger = logging.getLogger(__name__)

router = APIRouter()

async def _ensure_user_access(
    current_user: UserResponse,
    company_handler: CompanyHandler
) -> str:
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(
            status_code=400,
            detail="User has no company"
        )
    return company["id"]

# -------------------------------------------------------------------
# Request Models
# -------------------------------------------------------------------

class SearchNumbersRequest(BaseModel):
    country: str = Field(..., description="ISO country code (US, IN, etc.)")
    type: Literal["local", "toll-free", "mobile"] = "local"
    area_code: Optional[str] = None
    contains: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=50)


class PurchaseNumberRequest(BaseModel):
    phone_number: str
    agent_id: str
    agent_name: Optional[str]


# -------------------------------------------------------------------
# Twilio Helpers
# -------------------------------------------------------------------

def _twilio_auth_headers():
    auth = f"{Config.TWILIO_SID}:{Config.TWILIO_AUTH_TOKEN}"
    encoded = base64.b64encode(auth.encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def _twilio_search_url(country: str, number_type: str) -> str:
    base = f"https://api.twilio.com/2010-04-01/Accounts/{Config.TWILIO_SID}"
    if number_type == "toll-free":
        return f"{base}/AvailablePhoneNumbers/{country}/TollFree.json"
    if number_type == "mobile":
        return f"{base}/AvailablePhoneNumbers/{country}/Mobile.json"
    return f"{base}/AvailablePhoneNumbers/{country}/Local.json"


async def _search_twilio_numbers(request: SearchNumbersRequest):
    url = _twilio_search_url(request.country, request.type)

    params = {
        "PageSize": request.limit,
        "VoiceEnabled": "true"
    }
    if request.area_code:
        params["AreaCode"] = request.area_code
    if request.contains:
        params["Contains"] = request.contains

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            url,
            headers=_twilio_auth_headers(),
            params=params
        )

    if response.status_code == 401:
        raise HTTPException(401, "Invalid Twilio credentials")

    if response.status_code == 404:
        return []

    response.raise_for_status()

    numbers = response.json().get("available_phone_numbers", [])
    return [
        {
            "phone_number": n["phone_number"],
            "friendly_name": n.get("friendly_name"),
            "region": n.get("region"),
            "locality": n.get("locality"),
            "capabilities": n.get("capabilities", {}),
            "provider": "twilio"
        }
        for n in numbers
    ]


async def _purchase_twilio_number(
    phone_number: str,
    company_id: str,
    agent_id: str
):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{Config.TWILIO_SID}/IncomingPhoneNumbers.json"

    webhook_url = (
        "https://processor.callsure.ai/api/v1/twilio-elevenlabs/incoming-call"
        f"?company_id={company_id}&agent_id={agent_id}"
    )

    payload = {
        "PhoneNumber": phone_number,
        "VoiceUrl": webhook_url,
        "VoiceMethod": "POST"
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            url,
            headers={
                **_twilio_auth_headers(),
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data=payload
        )

    if response.status_code == 401:
        raise HTTPException(401, "Invalid Twilio credentials")

    if response.status_code == 400:
        raise HTTPException(400, response.json().get("message"))

    response.raise_for_status()


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

@router.post("/twilio/search")
async def twilio_search_numbers(
    request: SearchNumbersRequest,
    current_user: dict = Depends(get_current_user)
):
    numbers = await _search_twilio_numbers(request)
    return {
        "provider": "twilio",
        "count": len(numbers),
        "numbers": numbers
    }


@router.post("/twilio/purchase", status_code=status.HTTP_201_CREATED)
async def twilio_purchase_number(
    request: PurchaseNumberRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)

    await _purchase_twilio_number(
        phone_number=request.phone_number,
        company_id=company_id,
        agent_id=request.agent_id
    )

    return await create_agent_number(
        company_id=company_id,
        agent_id=request.agent_id,
        agent_name=request.agent_name,
        phone_number=request.phone_number,
        service_type="twilio"
    )

@router.post("/exotel/purchase", status_code=status.HTTP_201_CREATED)
async def exotel_purchase_number(
    request: PurchaseNumberRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)

    return await create_agent_number(
        company_id=company_id,
        agent_id=request.agent_id,
        agent_name=request.agent_name,
        phone_number=request.phone_number,
        service_type="exotel"
    )

