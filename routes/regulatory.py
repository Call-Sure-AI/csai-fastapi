# routes/regulatory.py
"""
Regulatory Compliance Routes
Handles address verification for phone number purchases in regulated countries
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
import uuid
import logging
import asyncio

from middleware.auth_middleware import get_current_user
from app.db.postgres_client import postgres_client
from app.models.schemas import UserResponse
from handlers.company_handler import CompanyHandler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/regulatory", tags=["Regulatory"])


# ============== Schemas ==============

class AddressCreate(BaseModel):
    """Schema for creating a new regulatory address"""
    company_id: Optional[str] = None
    country_code: str = Field(..., min_length=2, max_length=2, description="ISO 2-letter country code")
    business_name: str = Field(..., min_length=1, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255, description="Building/Office name")
    street_address: str = Field(..., min_length=1, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    region: str = Field(..., min_length=1, max_length=100, description="State/Province/Region")
    postal_code: str = Field(..., min_length=1, max_length=20)
    contact_name: str = Field(..., min_length=1, max_length=100)
    contact_email: EmailStr
    contact_phone: str = Field(..., min_length=1, max_length=20)


class AddressResponse(BaseModel):
    """Schema for address response"""
    id: str
    company_id: str
    country_code: str
    business_name: str
    address_line2: Optional[str]
    street_address: str
    city: str
    region: str
    postal_code: str
    contact_name: str
    contact_email: str
    contact_phone: str
    status: str  # pending, in_review, verified, rejected
    twilio_address_sid: Optional[str] = None
    twilio_bundle_sid: Optional[str] = None
    twilio_end_user_sid: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AddressListResponse(BaseModel):
    """Schema for listing addresses"""
    id: str
    country_code: str
    status: str
    business_name: str
    city: str
    created_at: datetime


# ============== Helper Functions ==============

async def _ensure_user_access(
    current_user: UserResponse,
    company_handler: CompanyHandler
) -> str:
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(status_code=400, detail="User has no company")
    return company["id"]


# ============== Background Task for Twilio ==============

async def submit_to_twilio_background(
    address_id: str,
    country_code: str,
    business_name: str,
    street_address: str,
    address_line2: Optional[str],
    city: str,
    region: str,
    postal_code: str,
    contact_name: str,
    contact_email: str,
    contact_phone: str
):
    """
    Background task to submit address to Twilio Regulatory Compliance API.
    """
    try:
        logger.info(f"Starting Twilio registration for address {address_id}")
        
        # Import here to avoid circular imports
        from app.services.twilio_regulatory_service import get_twilio_regulatory_service
        
        # Get Twilio service
        twilio_service = get_twilio_regulatory_service()
        
        # Submit to Twilio (this is sync, run in thread pool)
        loop = asyncio.get_event_loop()
        success, result = await loop.run_in_executor(
            None,
            twilio_service.register_address_for_country,
            country_code,
            business_name,
            street_address,
            address_line2,
            city,
            region,
            postal_code,
            contact_name,
            contact_email,
            contact_phone
        )
        
        # Update database with Twilio results
        if success:
            await postgres_client.client.execute_query(
                """
                UPDATE regulatory_addresses
                SET 
                    status = 'in_review',
                    twilio_address_sid = $1,
                    twilio_bundle_sid = $2,
                    twilio_end_user_sid = $3,
                    twilio_regulation_sid = $4,
                    updated_at = $5
                WHERE id = $6
                """,
                result.get("address_sid"),
                result.get("bundle_sid"),
                result.get("end_user_sid"),
                result.get("regulation_sid"),
                datetime.utcnow(),
                address_id
            )
            logger.info(f"✅ Successfully submitted address {address_id} to Twilio. Bundle: {result.get('bundle_sid')}")
        else:
            await postgres_client.client.execute_query(
                """
                UPDATE regulatory_addresses
                SET 
                    status = 'failed',
                    rejection_reason = $1,
                    updated_at = $2
                WHERE id = $3
                """,
                result.get("error", "Unknown error"),
                datetime.utcnow(),
                address_id
            )
            logger.error(f"❌ Failed to submit address {address_id} to Twilio: {result.get('error')}")
        
    except Exception as e:
        logger.exception(f"Error in Twilio background task for address {address_id}: {e}")
        try:
            await postgres_client.client.execute_query(
                """
                UPDATE regulatory_addresses
                SET status = 'failed', rejection_reason = $1, updated_at = $2
                WHERE id = $3
                """,
                str(e),
                datetime.utcnow(),
                address_id
            )
        except Exception as db_err:
            logger.error(f"Failed to update address status: {db_err}")


# ============== Routes ==============

@router.post("/addresses", response_model=AddressResponse)
async def create_address(
    address: AddressCreate,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Submit a new address for regulatory verification.
    """
    try:
        # Get company_id
        company_id = address.company_id
        if not company_id:
            company_id = await _ensure_user_access(current_user, company_handler)
        
        # Check if address already exists for this company and country
        existing = await postgres_client.client.execute_query_one(
            """
            SELECT id, status FROM regulatory_addresses 
            WHERE company_id = $1 AND country_code = $2 AND status NOT IN ('rejected', 'failed')
            """,
            company_id, address.country_code
        )
        
        if existing:
            raise HTTPException(
                status_code=400, 
                detail=f"An address for {address.country_code} already exists with status: {existing['status']}"
            )
        
        # Generate new ID
        address_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Insert new address with 'pending' status
        result = await postgres_client.client.execute_query_one(
            """
            INSERT INTO regulatory_addresses (
                id, company_id, country_code, business_name, address_line2,
                street_address, city, region, postal_code,
                contact_name, contact_email, contact_phone,
                status, created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
            )
            RETURNING *
            """,
            address_id, company_id, address.country_code, address.business_name,
            address.address_line2, address.street_address, address.city,
            address.region, address.postal_code, address.contact_name,
            address.contact_email, address.contact_phone,
            'pending', now, now
        )
        
        # Add background task to submit to Twilio
        background_tasks.add_task(
            submit_to_twilio_background,
            address_id=address_id,
            country_code=address.country_code,
            business_name=address.business_name,
            street_address=address.street_address,
            address_line2=address.address_line2,
            city=address.city,
            region=address.region,
            postal_code=address.postal_code,
            contact_name=address.contact_name,
            contact_email=address.contact_email,
            contact_phone=address.contact_phone
        )
        
        logger.info(f"Created regulatory address {address_id}, Twilio submission queued")
        
        return AddressResponse(
            id=str(result['id']),
            company_id=str(result['company_id']),
            country_code=result['country_code'],
            business_name=result['business_name'],
            address_line2=result.get('address_line2'),
            street_address=result['street_address'],
            city=result['city'],
            region=result['region'],
            postal_code=result['postal_code'],
            contact_name=result['contact_name'],
            contact_email=result['contact_email'],
            contact_phone=result['contact_phone'],
            status=result['status'],
            twilio_address_sid=result.get('twilio_address_sid'),
            twilio_bundle_sid=result.get('twilio_bundle_sid'),
            twilio_end_user_sid=result.get('twilio_end_user_sid'),
            rejection_reason=result.get('rejection_reason'),
            created_at=result['created_at'],
            updated_at=result['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create address: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create address: {str(e)}")


@router.get("/addresses", response_model=List[AddressListResponse])
async def get_addresses(
    company_id: Optional[str] = Query(None),
    country_code: Optional[str] = Query(None),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Get all regulatory addresses for a company.
    """
    try:
        # Get company_id from user if not provided
        if not company_id:
            company_id = await _ensure_user_access(current_user, company_handler)
        
        # Build query
        if country_code:
            results = await postgres_client.client.execute_query(
                """
                SELECT id, country_code, status, business_name, city, created_at
                FROM regulatory_addresses
                WHERE company_id = $1 AND country_code = $2
                ORDER BY created_at DESC
                """,
                company_id, country_code
            )
        else:
            results = await postgres_client.client.execute_query(
                """
                SELECT id, country_code, status, business_name, city, created_at
                FROM regulatory_addresses
                WHERE company_id = $1
                ORDER BY created_at DESC
                """,
                company_id
            )
        
        return [
            AddressListResponse(
                id=str(row['id']),
                country_code=row['country_code'],
                status=row['status'],
                business_name=row['business_name'],
                city=row['city'],
                created_at=row['created_at']
            )
            for row in (results or [])
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get addresses: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get addresses: {str(e)}")


@router.get("/addresses/{address_id}", response_model=AddressResponse)
async def get_address(
    address_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get a specific regulatory address by ID.
    """
    try:
        result = await postgres_client.client.execute_query_one(
            """
            SELECT * FROM regulatory_addresses WHERE id = $1
            """,
            address_id
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Address not found")
        
        return AddressResponse(
            id=str(result['id']),
            company_id=str(result['company_id']),
            country_code=result['country_code'],
            business_name=result['business_name'],
            address_line2=result.get('address_line2'),
            street_address=result['street_address'],
            city=result['city'],
            region=result['region'],
            postal_code=result['postal_code'],
            contact_name=result['contact_name'],
            contact_email=result['contact_email'],
            contact_phone=result['contact_phone'],
            status=result['status'],
            twilio_address_sid=result.get('twilio_address_sid'),
            twilio_bundle_sid=result.get('twilio_bundle_sid'),
            twilio_end_user_sid=result.get('twilio_end_user_sid'),
            rejection_reason=result.get('rejection_reason'),
            created_at=result['created_at'],
            updated_at=result['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get address: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get address: {str(e)}")


@router.delete("/addresses/{address_id}")
async def delete_address(
    address_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Delete a regulatory address (only if pending/failed/rejected).
    """
    try:
        # Check address exists and status
        result = await postgres_client.client.execute_query_one(
            "SELECT status FROM regulatory_addresses WHERE id = $1",
            address_id
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Address not found")
        
        if result['status'] in ('verified', 'in_review'):
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete address with status '{result['status']}'. Contact support."
            )
        
        await postgres_client.client.execute_query(
            "DELETE FROM regulatory_addresses WHERE id = $1",
            address_id
        )
        
        return {"message": "Address deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to delete address: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete address: {str(e)}")


@router.post("/addresses/{address_id}/retry")
async def retry_address_submission(
    address_id: str,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Retry Twilio submission for a failed address.
    """
    try:
        result = await postgres_client.client.execute_query_one(
            """
            SELECT * FROM regulatory_addresses WHERE id = $1
            """,
            address_id
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Address not found")
        
        if result['status'] not in ('failed', 'rejected'):
            raise HTTPException(
                status_code=400, 
                detail=f"Can only retry failed or rejected addresses. Current status: {result['status']}"
            )
        
        # Reset status to pending
        await postgres_client.client.execute_query(
            """
            UPDATE regulatory_addresses
            SET status = 'pending', rejection_reason = NULL, 
                twilio_address_sid = NULL, twilio_bundle_sid = NULL, 
                twilio_end_user_sid = NULL, updated_at = $1
            WHERE id = $2
            """,
            datetime.utcnow(), address_id
        )
        
        # Queue background task
        background_tasks.add_task(
            submit_to_twilio_background,
            address_id=address_id,
            country_code=result['country_code'],
            business_name=result['business_name'],
            street_address=result['street_address'],
            address_line2=result.get('address_line2'),
            city=result['city'],
            region=result['region'],
            postal_code=result['postal_code'],
            contact_name=result['contact_name'],
            contact_email=result['contact_email'],
            contact_phone=result['contact_phone']
        )
        
        return {"message": "Address resubmission queued", "status": "pending"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to retry: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retry: {str(e)}")


# ============== Webhook for Twilio Status Updates ==============

class TwilioWebhookPayload(BaseModel):
    """Schema for Twilio regulatory bundle webhook"""
    BundleSid: str
    Status: str
    FailureReason: Optional[str] = None


@router.post("/webhooks/twilio-bundle-status")
async def twilio_bundle_status_webhook(payload: TwilioWebhookPayload):
    """
    Webhook endpoint for Twilio to notify us of bundle status changes.
    """
    try:
        logger.info(f"Received Twilio webhook: Bundle={payload.BundleSid}, Status={payload.Status}")
        
        # Map Twilio status to our status
        status_map = {
            'twilio-approved': 'verified',
            'twilio-rejected': 'rejected',
            'pending-review': 'in_review',
            'in-review': 'in_review',
            'draft': 'pending',
        }
        
        new_status = status_map.get(payload.Status, 'pending')
        
        # Update address status
        result = await postgres_client.client.execute_query_one(
            """
            UPDATE regulatory_addresses
            SET status = $1, rejection_reason = $2, updated_at = $3
            WHERE twilio_bundle_sid = $4
            RETURNING id, company_id, country_code, contact_email
            """,
            new_status, payload.FailureReason, datetime.utcnow(), payload.BundleSid
        )
        
        if result:
            logger.info(f"Updated address {result['id']} to status '{new_status}'")
        else:
            logger.warning(f"No address found for bundle {payload.BundleSid}")
        
        return {"status": "received"}
        
    except Exception as e:
        logger.exception(f"Webhook processing failed: {e}")
        return {"status": "error", "message": str(e)}


# ============== Get Verified Bundle for Purchase ==============

@router.get("/bundles/{country_code}/verified")
async def get_verified_bundle(
    country_code: str,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    """
    Get the verified bundle SID for a country.
    """
    try:
        company_id = await _ensure_user_access(current_user, company_handler)
        
        result = await postgres_client.client.execute_query_one(
            """
            SELECT twilio_bundle_sid
            FROM regulatory_addresses
            WHERE company_id = $1 AND country_code = $2 AND status = 'verified'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            company_id, country_code.upper()
        )
        
        if not result or not result.get('twilio_bundle_sid'):
            raise HTTPException(
                status_code=404, 
                detail=f"No verified address found for {country_code}. Please submit an address for verification first."
            )
        
        return {
            "country_code": country_code.upper(),
            "bundle_sid": result['twilio_bundle_sid'],
            "status": "verified"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get bundle: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get bundle: {str(e)}")