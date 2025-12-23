# routes/phone_numbers.py
"""
Phone Number Management

Rules:
- One phone number per agent (DB-enforced)
- Numbers stored in AgentNumber table
- Regulated countries (UK, EU, etc.) require verified address bundle
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Literal
import base64
import httpx
import logging
import uuid

from middleware.auth_middleware import get_current_user
from config import Config
from app.db.queries.agent_number_queries import create_agent_number
from app.db.postgres_client import get_db_connection
from handlers.company_handler import CompanyHandler
from app.models.schemas import UserResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# -------------------------------------------------------------------
# Regulated Countries Configuration
# -------------------------------------------------------------------

# Countries that require regulatory bundle (address verification) for purchase
REGULATED_COUNTRIES = {
    "GB",  # United Kingdom
    "AU",  # Australia
    "DE",  # Germany
    "FR",  # France
    "IN",  # India
    "SG",  # Singapore
    "JP",  # Japan
    "BR",  # Brazil
    "NL",  # Netherlands
    "ES",  # Spain
    "IT",  # Italy
    "AT",  # Austria
    "BE",  # Belgium
    "CH",  # Switzerland
    "IE",  # Ireland
    "PL",  # Poland
    "SE",  # Sweden
    "NO",  # Norway
    "DK",  # Denmark
    "FI",  # Finland
    "PT",  # Portugal
}

# Countries with instant purchase (no bundle needed)
INSTANT_COUNTRIES = {"US", "CA", "MX"}

# Phone number prefix to country code mapping
PHONE_PREFIX_TO_COUNTRY = {
    "+1": "US",    # US/CA (default to US)
    "+44": "GB",   # United Kingdom
    "+61": "AU",   # Australia
    "+49": "DE",   # Germany
    "+33": "FR",   # France
    "+91": "IN",   # India
    "+65": "SG",   # Singapore
    "+81": "JP",   # Japan
    "+55": "BR",   # Brazil
    "+31": "NL",   # Netherlands
    "+34": "ES",   # Spain
    "+39": "IT",   # Italy
    "+52": "MX",   # Mexico
    "+43": "AT",   # Austria
    "+32": "BE",   # Belgium
    "+41": "CH",   # Switzerland
    "+353": "IE",  # Ireland
    "+48": "PL",   # Poland
    "+46": "SE",   # Sweden
    "+47": "NO",   # Norway
    "+45": "DK",   # Denmark
    "+358": "FI",  # Finland
    "+351": "PT",  # Portugal
}


# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------

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


def _get_country_from_phone(phone_number: str) -> str:
    """Extract country code from phone number prefix"""
    for prefix, country in sorted(PHONE_PREFIX_TO_COUNTRY.items(), key=lambda x: -len(x[0])):
        if phone_number.startswith(prefix):
            return country
    return "US"  # Default to US


async def _get_verified_bundle(company_id: str, country_code: str) -> Optional[str]:
    """Get verified regulatory bundle SID for a country"""
    try:
        conn = await get_db_connection()
        
        result = await conn.fetchrow(
            """
            SELECT twilio_bundle_sid
            FROM regulatory_addresses
            WHERE company_id = $1 AND country_code = $2 AND status = 'verified'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            uuid.UUID(company_id), country_code
        )
        return result['twilio_bundle_sid'] if result else None
        
    except Exception as e:
        logger.warning(f"Could not check for verified bundle: {e}")
        return None


async def _get_address_status(company_id: str, country_code: str) -> dict:
    """Get current address verification status for a country"""
    try:
        conn = await get_db_connection()
        
        result = await conn.fetchrow(
            """
            SELECT id, status, rejection_reason, twilio_bundle_sid
            FROM regulatory_addresses
            WHERE company_id = $1 AND country_code = $2
            ORDER BY created_at DESC
            LIMIT 1
            """,
            uuid.UUID(company_id), country_code
        )
        
        if not result:
            return {
                "has_address": False,
                "status": None,
                "message": f"No address submitted for {country_code}"
            }
        
        return {
            "has_address": True,
            "address_id": str(result['id']),
            "status": result['status'],
            "rejection_reason": result['rejection_reason'],
            "bundle_sid": result['twilio_bundle_sid']
        }
        
    except Exception as e:
        logger.warning(f"Could not check address status: {e}")
        return {"has_address": False, "status": None, "error": str(e)}


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
    agent_id: str,
    bundle_sid: Optional[str] = None
):
    """
    Purchase a Twilio phone number.
    
    Args:
        phone_number: The phone number to purchase
        company_id: Company ID for webhook
        agent_id: Agent ID for webhook
        bundle_sid: Regulatory bundle SID (required for regulated countries)
    """
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
    
    # Add bundle SID for regulated countries
    if bundle_sid:
        payload["BundleSid"] = bundle_sid

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
        error_data = response.json()
        error_message = error_data.get("message", "Purchase failed")
        
        # Check for address/bundle requirement error
        if "Address" in error_message or "bundle" in error_message.lower():
            raise HTTPException(
                400, 
                "This phone number requires address verification. "
                "Please submit and verify your business address first."
            )
        
        raise HTTPException(400, error_message)

    response.raise_for_status()
    
    return response.json()


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

@router.post("/twilio/search")
async def twilio_search_numbers(
    request: SearchNumbersRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Search for available Twilio phone numbers.
    Returns numbers along with regulatory requirements info.
    """
    numbers = await _search_twilio_numbers(request)
    
    requires_bundle = request.country.upper() in REGULATED_COUNTRIES
    
    return {
        "provider": "twilio",
        "country": request.country,
        "count": len(numbers),
        "requires_bundle": requires_bundle,
        "numbers": numbers
    }


@router.post("/twilio/purchase", status_code=status.HTTP_201_CREATED)
async def twilio_purchase_number(
    request: PurchaseNumberRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """
    Purchase a Twilio phone number.
    
    For regulated countries (UK, EU, etc.), automatically uses the verified bundle.
    If no verified bundle exists for a regulated country, returns an error.
    """
    company_id = await _ensure_user_access(current_user, company_handler)
    
    # Determine country from phone number
    country_code = _get_country_from_phone(request.phone_number)
    
    # Check if this country requires a regulatory bundle
    bundle_sid = None
    if country_code in REGULATED_COUNTRIES:
        bundle_sid = await _get_verified_bundle(company_id, country_code)
        
        if not bundle_sid:
            # Get current address status for better error message
            addr_status = await _get_address_status(company_id, country_code)
            
            if not addr_status.get("has_address"):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "address_required",
                        "message": f"Phone numbers in {country_code} require address verification. "
                                   f"Please submit your business address for {country_code} first.",
                        "country_code": country_code,
                        "action": "submit_address"
                    }
                )
            elif addr_status.get("status") == "pending":
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "address_pending",
                        "message": "Your address verification is being processed. Please wait.",
                        "country_code": country_code,
                        "status": "pending",
                        "action": "wait"
                    }
                )
            elif addr_status.get("status") == "in_review":
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "address_in_review",
                        "message": "Your address is being reviewed by Twilio. "
                                   "This typically takes 1-3 business days.",
                        "country_code": country_code,
                        "status": "in_review",
                        "action": "wait"
                    }
                )
            elif addr_status.get("status") == "rejected":
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "address_rejected",
                        "message": f"Your address was rejected: {addr_status.get('rejection_reason')}. "
                                   f"Please submit a new address.",
                        "country_code": country_code,
                        "status": "rejected",
                        "action": "resubmit_address"
                    }
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "verification_required",
                        "message": f"Address verification required for {country_code}.",
                        "country_code": country_code,
                        "action": "submit_address"
                    }
                )
    
    # Purchase the number with bundle (if required)
    await _purchase_twilio_number(
        phone_number=request.phone_number,
        company_id=company_id,
        agent_id=request.agent_id,
        bundle_sid=bundle_sid
    )

    return await create_agent_number(
        company_id=company_id,
        agent_id=request.agent_id,
        agent_name=request.agent_name,
        phone_number=request.phone_number,
        service_type="twilio"
    )


@router.get("/requirements/{country_code}")
async def check_country_requirements(
    country_code: str,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    """
    Check if a country requires address verification and current status.
    
    Returns:
    - requires_bundle: True if country needs address verification
    - can_purchase: True if user can purchase numbers now
    - address_status: Current verification status (if applicable)
    """
    company_id = await _ensure_user_access(current_user, company_handler)
    country_code = country_code.upper()
    
    requires_bundle = country_code in REGULATED_COUNTRIES
    
    if not requires_bundle:
        return {
            "country_code": country_code,
            "requires_bundle": False,
            "can_purchase": True,
            "message": "This country allows instant purchase without address verification."
        }
    
    # Check address status for regulated country
    addr_status = await _get_address_status(company_id, country_code)
    
    is_verified = addr_status.get("status") == "verified"
    
    status_messages = {
        None: f"No address submitted. Please submit your business address for {country_code}.",
        "pending": "Your address verification is being processed...",
        "in_review": "Your address is being reviewed by Twilio (1-3 business days).",
        "verified": "Your address is verified! You can purchase phone numbers.",
        "rejected": f"Address rejected: {addr_status.get('rejection_reason')}. Please resubmit.",
        "failed": "Address submission failed. Please try again."
    }
    
    return {
        "country_code": country_code,
        "requires_bundle": True,
        "can_purchase": is_verified,
        "has_address": addr_status.get("has_address", False),
        "address_status": addr_status.get("status"),
        "address_id": addr_status.get("address_id"),
        "bundle_sid": addr_status.get("bundle_sid") if is_verified else None,
        "message": status_messages.get(addr_status.get("status"), "Unknown status")
    }


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