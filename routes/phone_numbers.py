# routes/phone_numbers.py
"""
Phone Number Management Routes
Handles searching and purchasing phone numbers from Twilio and Exotel
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime, timedelta
import httpx
import base64
import logging

from middleware.auth_middleware import get_current_user
from app.db.postgres_client import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/phone-numbers", tags=["Phone Numbers"])


# ============== Pydantic Models ==============

class TwilioCredentials(BaseModel):
    account_sid: str = Field(..., description="Twilio Account SID (starts with AC)")
    auth_token: str = Field(..., description="Twilio Auth Token")


class ExotelCredentials(BaseModel):
    api_key: str = Field(..., description="Exotel API Key")
    api_token: str = Field(..., description="Exotel API Token")
    subdomain: str = Field(..., description="Exotel subdomain (e.g., 'yourcompany' from yourcompany.exotel.com)")


class SearchNumbersRequest(BaseModel):
    country: str = Field(..., description="ISO country code (e.g., 'US', 'IN', 'GB')")
    type: Literal["local", "toll-free", "mobile"] = Field(default="local")
    area_code: Optional[str] = Field(default=None, description="Area code filter")
    contains: Optional[str] = Field(default=None, description="Pattern to search for")
    limit: int = Field(default=20, ge=1, le=50)


class TwilioSearchRequest(TwilioCredentials, SearchNumbersRequest):
    pass


class ExotelSearchRequest(ExotelCredentials, SearchNumbersRequest):
    pass


class AvailableNumber(BaseModel):
    phone_number: str
    friendly_name: str
    country: str
    country_code: str
    region: Optional[str] = None
    locality: Optional[str] = None
    capabilities: dict = {"voice": True, "sms": False, "mms": False}
    monthly_cost: float
    setup_cost: float = 0.0
    type: str = "local"


class PurchaseNumberRequest(BaseModel):
    phone_number: str = Field(..., description="Phone number to purchase (E.164 format)")
    agent_id: str = Field(..., description="Agent ID to connect to this number")
    agent_name: Optional[str] = Field(default=None)


class TwilioPurchaseRequest(TwilioCredentials, PurchaseNumberRequest):
    messaging_service_sid: Optional[str] = None


class ExotelPurchaseRequest(ExotelCredentials, PurchaseNumberRequest):
    pass


class PhoneNumberResponse(BaseModel):
    id: str
    phone_number: str
    provider: str
    agent_id: Optional[str]
    agent_name: Optional[str]
    company_id: str
    status: str
    monthly_cost: float
    country: Optional[str]
    region: Optional[str]
    purchased_at: datetime
    renews_at: datetime
    created_at: datetime


# ============== Country Data ==============

COUNTRIES = {
    # Twilio supported countries (subset)
    "US": {"name": "United States", "flag": "🇺🇸", "code": "+1", "providers": ["twilio", "plivo"]},
    "GB": {"name": "United Kingdom", "flag": "🇬🇧", "code": "+44", "providers": ["twilio", "plivo"]},
    "CA": {"name": "Canada", "flag": "🇨🇦", "code": "+1", "providers": ["twilio", "plivo"]},
    "AU": {"name": "Australia", "flag": "🇦🇺", "code": "+61", "providers": ["twilio", "plivo"]},
    "DE": {"name": "Germany", "flag": "🇩🇪", "code": "+49", "providers": ["twilio", "plivo"]},
    "FR": {"name": "France", "flag": "🇫🇷", "code": "+33", "providers": ["twilio", "plivo"]},
    "JP": {"name": "Japan", "flag": "🇯🇵", "code": "+81", "providers": ["twilio"]},
    "SG": {"name": "Singapore", "flag": "🇸🇬", "code": "+65", "providers": ["twilio", "exotel"]},
    "BR": {"name": "Brazil", "flag": "🇧🇷", "code": "+55", "providers": ["twilio"]},
    "MX": {"name": "Mexico", "flag": "🇲🇽", "code": "+52", "providers": ["twilio"]},
    "ES": {"name": "Spain", "flag": "🇪🇸", "code": "+34", "providers": ["twilio"]},
    "IT": {"name": "Italy", "flag": "🇮🇹", "code": "+39", "providers": ["twilio"]},
    "NL": {"name": "Netherlands", "flag": "🇳🇱", "code": "+31", "providers": ["twilio"]},
    "SE": {"name": "Sweden", "flag": "🇸🇪", "code": "+46", "providers": ["twilio"]},
    "CH": {"name": "Switzerland", "flag": "🇨🇭", "code": "+41", "providers": ["twilio"]},
    "IE": {"name": "Ireland", "flag": "🇮🇪", "code": "+353", "providers": ["twilio"]},
    "NZ": {"name": "New Zealand", "flag": "🇳🇿", "code": "+64", "providers": ["twilio"]},
    # Exotel supported countries
    "IN": {"name": "India", "flag": "🇮🇳", "code": "+91", "providers": ["twilio", "exotel"]},
    "MY": {"name": "Malaysia", "flag": "🇲🇾", "code": "+60", "providers": ["exotel"]},
    "ID": {"name": "Indonesia", "flag": "🇮🇩", "code": "+62", "providers": ["exotel"]},
    "PH": {"name": "Philippines", "flag": "🇵🇭", "code": "+63", "providers": ["exotel"]},
    "AE": {"name": "UAE", "flag": "🇦🇪", "code": "+971", "providers": ["twilio", "exotel"]},
}


# ============== Helper Functions ==============

def get_twilio_number_type_endpoint(country: str, number_type: str) -> str:
    """Get the correct Twilio API endpoint based on number type"""
    base = f"https://api.twilio.com/2010-04-01/Accounts"
    
    if number_type == "toll-free":
        return f"AvailablePhoneNumbers/{country}/TollFree.json"
    elif number_type == "mobile":
        return f"AvailablePhoneNumbers/{country}/Mobile.json"
    else:  # local
        return f"AvailablePhoneNumbers/{country}/Local.json"


async def search_twilio_numbers_api(
    account_sid: str,
    auth_token: str,
    country: str,
    number_type: str = "local",
    area_code: Optional[str] = None,
    contains: Optional[str] = None,
    limit: int = 20
) -> List[AvailableNumber]:
    """Search available phone numbers from Twilio API"""
    
    endpoint_path = get_twilio_number_type_endpoint(country, number_type)
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/{endpoint_path}"
    
    params = {"PageSize": min(limit, 50)}
    
    if area_code:
        params["AreaCode"] = area_code
    if contains:
        params["Contains"] = contains
    
    # Request voice and SMS capabilities
    params["VoiceEnabled"] = "true"
    
    auth = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Twilio credentials. Please check your Account SID and Auth Token."
                )
            
            if response.status_code == 404:
                # No numbers found for this country/type combination
                return []
            
            response.raise_for_status()
            data = response.json()
            
            available_numbers = data.get("available_phone_numbers", [])
            
            # Get pricing info (approximate - actual pricing varies)
            pricing = get_twilio_pricing(country, number_type)
            
            return [
                AvailableNumber(
                    phone_number=num.get("phone_number"),
                    friendly_name=num.get("friendly_name", num.get("phone_number")),
                    country=country,
                    country_code=COUNTRIES.get(country, {}).get("code", ""),
                    region=num.get("region"),
                    locality=num.get("locality"),
                    capabilities={
                        "voice": num.get("capabilities", {}).get("voice", True),
                        "sms": num.get("capabilities", {}).get("SMS", False),
                        "mms": num.get("capabilities", {}).get("MMS", False),
                    },
                    monthly_cost=pricing["monthly"],
                    setup_cost=pricing["setup"],
                    type=number_type
                )
                for num in available_numbers
            ]
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Twilio API error: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Twilio API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            logger.error(f"Twilio request error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to connect to Twilio API"
            )


def get_twilio_pricing(country: str, number_type: str) -> dict:
    """Get approximate Twilio pricing (actual pricing may vary)"""
    # These are approximate prices - actual prices vary by country
    pricing_map = {
        "US": {"local": 1.15, "toll-free": 2.15, "mobile": 1.15},
        "GB": {"local": 1.15, "toll-free": 2.15, "mobile": 1.15},
        "CA": {"local": 1.15, "toll-free": 2.15, "mobile": 1.15},
        "AU": {"local": 2.15, "toll-free": 4.00, "mobile": 2.15},
        "DE": {"local": 1.15, "toll-free": 3.00, "mobile": 1.15},
        "IN": {"local": 3.00, "toll-free": 5.00, "mobile": 3.00},
        "default": {"local": 1.50, "toll-free": 3.00, "mobile": 1.50},
    }
    
    country_pricing = pricing_map.get(country, pricing_map["default"])
    monthly = country_pricing.get(number_type, 1.50)
    
    return {"monthly": monthly, "setup": 1.00}


async def purchase_twilio_number_api(
    account_sid: str,
    auth_token: str,
    phone_number: str,
    voice_url: Optional[str] = None,
    sms_url: Optional[str] = None
) -> dict:
    """Purchase a phone number from Twilio"""
    
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/IncomingPhoneNumbers.json"
    
    auth = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {"PhoneNumber": phone_number}
    
    if voice_url:
        data["VoiceUrl"] = voice_url
    if sms_url:
        data["SmsUrl"] = sms_url
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(url, data=data, headers=headers)
            
            if response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Twilio credentials"
                )
            
            if response.status_code == 400:
                error_data = response.json()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_data.get("message", "Failed to purchase number")
                )
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Twilio purchase error: {e.response.text}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Twilio API error: {e.response.text}"
            )


async def search_exotel_numbers_api(
    api_key: str,
    api_token: str,
    subdomain: str,
    country: str = "IN",
    number_type: str = "local",
    limit: int = 20
) -> List[AvailableNumber]:
    """Search available phone numbers from Exotel API"""
    
    # Exotel API endpoint for available numbers
    url = f"https://{subdomain}.exotel.com/v1/Accounts/{subdomain}/AvailablePhoneNumbers"
    
    auth = base64.b64encode(f"{api_key}:{api_token}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}
    
    params = {
        "Country": country,
        "Type": "landline" if number_type == "local" else number_type,
        "Limit": min(limit, 50)
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Exotel credentials. Please check your API Key, Token, and Subdomain."
                )
            
            if response.status_code == 404:
                return []
            
            response.raise_for_status()
            data = response.json()
            
            available_numbers = data.get("AvailablePhoneNumbers", [])
            
            # Exotel pricing (approximate for India)
            pricing = get_exotel_pricing(country, number_type)
            
            return [
                AvailableNumber(
                    phone_number=num.get("PhoneNumber", num.get("phone_number")),
                    friendly_name=num.get("FriendlyName", num.get("PhoneNumber")),
                    country=country,
                    country_code=COUNTRIES.get(country, {}).get("code", "+91"),
                    region=num.get("Region"),
                    locality=num.get("City"),
                    capabilities={
                        "voice": True,
                        "sms": num.get("Capabilities", {}).get("SMS", False),
                        "mms": False,
                    },
                    monthly_cost=pricing["monthly"],
                    setup_cost=pricing["setup"],
                    type=number_type
                )
                for num in available_numbers
            ]
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Exotel API error: {e.response.status_code}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Exotel API error: Unable to fetch available numbers"
            )
        except httpx.RequestError as e:
            logger.error(f"Exotel request error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to connect to Exotel API"
            )


def get_exotel_pricing(country: str, number_type: str) -> dict:
    """Get approximate Exotel pricing"""
    pricing_map = {
        "IN": {"local": 200, "toll-free": 500, "mobile": 300},  # INR per month
        "SG": {"local": 15, "toll-free": 25, "mobile": 20},  # SGD per month
        "default": {"local": 10, "toll-free": 20, "mobile": 15},  # USD per month
    }
    
    country_pricing = pricing_map.get(country, pricing_map["default"])
    monthly = country_pricing.get(number_type, 10)
    
    # Convert INR to USD for display consistency (approximate)
    if country == "IN":
        monthly = round(monthly / 83, 2)  # Approximate INR to USD
    
    return {"monthly": monthly, "setup": 0}


# ============== API Routes ==============

@router.get("/countries")
async def get_supported_countries(
    provider: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get list of supported countries with their details"""
    if provider:
        filtered = {
            code: data for code, data in COUNTRIES.items() 
            if provider in data.get("providers", [])
        }
        return {"countries": filtered}
    return {"countries": COUNTRIES}


@router.post("/twilio/search", response_model=dict)
async def search_twilio_numbers(
    request: TwilioSearchRequest,
    current_user: dict = Depends(get_current_user)
):
    """Search available phone numbers from Twilio"""
    
    # Validate Account SID format
    if not request.account_sid.startswith("AC"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Account SID format. It should start with 'AC'."
        )
    
    numbers = await search_twilio_numbers_api(
        account_sid=request.account_sid,
        auth_token=request.auth_token,
        country=request.country,
        number_type=request.type,
        area_code=request.area_code,
        contains=request.contains,
        limit=request.limit
    )
    
    return {
        "available_numbers": [num.dict() for num in numbers],
        "count": len(numbers),
        "provider": "twilio",
        "country": request.country
    }


@router.post("/exotel/search", response_model=dict)
async def search_exotel_numbers(
    request: ExotelSearchRequest,
    current_user: dict = Depends(get_current_user)
):
    """Search available phone numbers from Exotel"""
    
    numbers = await search_exotel_numbers_api(
        api_key=request.api_key,
        api_token=request.api_token,
        subdomain=request.subdomain,
        country=request.country,
        number_type=request.type,
        limit=request.limit
    )
    
    return {
        "available_numbers": [num.dict() for num in numbers],
        "count": len(numbers),
        "provider": "exotel",
        "country": request.country
    }


@router.post("/twilio/purchase")
async def purchase_twilio_number(
    request: TwilioPurchaseRequest,
    current_user: dict = Depends(get_current_user)
):
    """Purchase a Twilio phone number and connect it to an agent"""
    
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company ID not found for user"
        )
    
    # Generate webhook URL for this agent
    base_url = "https://api.callsure.ai"  # Your API base URL
    voice_webhook_url = f"{base_url}/api/voice/twilio/incoming/{request.agent_id}"
    
    # Purchase the number from Twilio
    twilio_response = await purchase_twilio_number_api(
        account_sid=request.account_sid,
        auth_token=request.auth_token,
        phone_number=request.phone_number,
        voice_url=voice_webhook_url
    )
    
    # Get pricing for the country
    # Extract country from phone number (simplified)
    country = "US" if request.phone_number.startswith("+1") else "IN"
    pricing = get_twilio_pricing(country, "local")
    
    # Store in database
    phone_number_record = await save_phone_number_to_db(
        phone_number=request.phone_number,
        provider="twilio",
        provider_sid=twilio_response.get("sid"),
        agent_id=request.agent_id,
        agent_name=request.agent_name,
        company_id=company_id,
        monthly_cost=pricing["monthly"],
        country=country,
        credentials={
            "account_sid": request.account_sid,
            "auth_token": request.auth_token,
            "messaging_service_sid": request.messaging_service_sid
        }
    )
    
    return phone_number_record


@router.post("/exotel/purchase")
async def purchase_exotel_number(
    request: ExotelPurchaseRequest,
    current_user: dict = Depends(get_current_user)
):
    """Purchase an Exotel phone number and connect it to an agent"""
    
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company ID not found for user"
        )
    
    # For Exotel, the number purchase flow is different
    # Usually numbers are pre-allocated, so we just connect it
    country = "IN"
    pricing = get_exotel_pricing(country, "local")
    
    # Store in database
    phone_number_record = await save_phone_number_to_db(
        phone_number=request.phone_number,
        provider="exotel",
        provider_sid=None,
        agent_id=request.agent_id,
        agent_name=request.agent_name,
        company_id=company_id,
        monthly_cost=pricing["monthly"],
        country=country,
        credentials={
            "api_key": request.api_key,
            "api_token": request.api_token,
            "subdomain": request.subdomain
        }
    )
    
    return phone_number_record


@router.get("/company/{company_id}")
async def get_company_phone_numbers(
    company_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all phone numbers for a company"""
    
    # Verify user has access to this company
    user_company_id = current_user.get("company_id")
    if user_company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this company's phone numbers"
        )
    
    numbers = await get_phone_numbers_from_db(company_id)
    return numbers


@router.patch("/{number_id}")
async def update_phone_number(
    number_id: str,
    agent_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Update phone number assignment (change agent)"""
    
    company_id = current_user.get("company_id")
    
    updated = await update_phone_number_in_db(
        number_id=number_id,
        company_id=company_id,
        agent_id=agent_id,
        agent_name=agent_name
    )
    
    return updated


@router.delete("/{number_id}")
async def delete_phone_number(
    number_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete/release a phone number"""
    
    company_id = current_user.get("company_id")
    
    # Get the phone number record
    phone_record = await get_phone_number_by_id(number_id, company_id)
    
    if not phone_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # If Twilio, release the number
    if phone_record.get("provider") == "twilio":
        credentials = phone_record.get("credentials", {})
        if credentials.get("account_sid") and phone_record.get("provider_sid"):
            try:
                await release_twilio_number(
                    account_sid=credentials["account_sid"],
                    auth_token=credentials["auth_token"],
                    number_sid=phone_record["provider_sid"]
                )
            except Exception as e:
                logger.warning(f"Failed to release Twilio number: {e}")
    
    # Delete from database
    await delete_phone_number_from_db(number_id, company_id)
    
    return {"success": True, "message": "Phone number deleted"}


async def release_twilio_number(account_sid: str, auth_token: str, number_sid: str):
    """Release a phone number back to Twilio"""
    
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/IncomingPhoneNumbers/{number_sid}.json"
    
    auth = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.delete(url, headers=headers)
        response.raise_for_status()


# ============== Database Functions ==============

async def save_phone_number_to_db(
    phone_number: str,
    provider: str,
    provider_sid: Optional[str],
    agent_id: str,
    agent_name: Optional[str],
    company_id: str,
    monthly_cost: float,
    country: str,
    credentials: dict
) -> dict:
    """Save phone number to database"""
    
    import uuid
    from datetime import datetime, timedelta
    
    conn = await get_db_connection()
    try:
        number_id = str(uuid.uuid4())
        now = datetime.utcnow()
        renews_at = now + timedelta(days=30)
        
        query = """
            INSERT INTO phone_numbers (
                id, phone_number, provider, provider_sid, agent_id, agent_name,
                company_id, status, monthly_cost, country, credentials,
                purchased_at, renews_at, created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
            )
            RETURNING *
        """
        
        import json
        row = await conn.fetchrow(
            query,
            number_id,
            phone_number,
            provider,
            provider_sid,
            agent_id,
            agent_name,
            company_id,
            "active",
            monthly_cost,
            country,
            json.dumps(credentials),
            now,
            renews_at,
            now,
            now
        )
        
        return dict(row) if row else None
        
    finally:
        await conn.close()


async def get_phone_numbers_from_db(company_id: str) -> list:
    """Get all phone numbers for a company"""
    
    conn = await get_db_connection()
    try:
        query = """
            SELECT id, phone_number, provider, agent_id, agent_name,
                   company_id, status, monthly_cost, country, region,
                   purchased_at, renews_at, created_at, updated_at
            FROM phone_numbers
            WHERE company_id = $1 AND status != 'deleted'
            ORDER BY created_at DESC
        """
        
        rows = await conn.fetch(query, company_id)
        return [dict(row) for row in rows]
        
    finally:
        await conn.close()


async def get_phone_number_by_id(number_id: str, company_id: str) -> dict:
    """Get a specific phone number"""
    
    conn = await get_db_connection()
    try:
        query = """
            SELECT * FROM phone_numbers
            WHERE id = $1 AND company_id = $2
        """
        
        row = await conn.fetchrow(query, number_id, company_id)
        return dict(row) if row else None
        
    finally:
        await conn.close()


async def update_phone_number_in_db(
    number_id: str,
    company_id: str,
    agent_id: Optional[str] = None,
    agent_name: Optional[str] = None
) -> dict:
    """Update phone number in database"""
    
    conn = await get_db_connection()
    try:
        query = """
            UPDATE phone_numbers
            SET agent_id = COALESCE($3, agent_id),
                agent_name = COALESCE($4, agent_name),
                updated_at = NOW()
            WHERE id = $1 AND company_id = $2
            RETURNING *
        """
        
        row = await conn.fetchrow(query, number_id, company_id, agent_id, agent_name)
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Phone number not found"
            )
        
        return dict(row)
        
    finally:
        await conn.close()


async def delete_phone_number_from_db(number_id: str, company_id: str):
    """Soft delete phone number from database"""
    
    conn = await get_db_connection()
    try:
        query = """
            UPDATE phone_numbers
            SET status = 'deleted', updated_at = NOW()
            WHERE id = $1 AND company_id = $2
        """
        
        await conn.execute(query, number_id, company_id)
        
    finally:
        await conn.close()