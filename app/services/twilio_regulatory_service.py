# app/services/twilio_regulatory_service.py
"""
Twilio Regulatory Compliance Service
Handles address verification and regulatory bundles for phone number purchases
in regulated countries (UK, EU, Australia, etc.)

Twilio Regulatory Flow:
1. Create End-User (business entity)
2. Create Address (business address)
3. Create Supporting Document (if required)
4. Create Regulatory Bundle
5. Assign End-User and Address to Bundle
6. Submit Bundle for Review
7. Wait for Twilio approval (webhook callback)
8. Once approved, use Bundle SID when purchasing phone numbers
"""

import os
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

# Twilio credentials from environment
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WEBHOOK_BASE_URL = os.getenv("TWILIO_WEBHOOK_BASE_URL", "https://beta.callsure.ai")


class TwilioRegulatoryService:
    """Service for managing Twilio regulatory compliance"""
    
    def __init__(self):
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            raise ValueError("Twilio credentials not configured")
        self.client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    
    # ============== End-User Management ==============
    
    def create_end_user(
        self,
        friendly_name: str,
        business_name: str,
        business_type: str = "Business"
    ) -> Dict[str, Any]:
        """
        Create an End-User entity in Twilio.
        This represents the business that will use the phone numbers.
        
        Args:
            friendly_name: Display name for the end user
            business_name: Legal business name
            business_type: Type of business (Business, Individual, etc.)
            
        Returns:
            Dict with end_user_sid and details
        """
        try:
            end_user = self.client.numbers.v2.regulatory_compliance \
                .end_users \
                .create(
                    friendly_name=friendly_name,
                    type="business",
                    attributes={
                        "business_name": business_name,
                        "business_type": business_type
                    }
                )
            
            logger.info(f"Created Twilio End-User: {end_user.sid}")
            
            return {
                "success": True,
                "end_user_sid": end_user.sid,
                "friendly_name": end_user.friendly_name,
                "type": end_user.type
            }
            
        except TwilioRestException as e:
            logger.error(f"Failed to create End-User: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": e.code
            }
    
    # ============== Address Management ==============
    
    def create_address(
        self,
        customer_name: str,
        street: str,
        city: str,
        region: str,
        postal_code: str,
        country_code: str,
        street_secondary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an Address in Twilio for regulatory compliance.
        
        Args:
            customer_name: Business name
            street: Street address
            city: City name
            region: State/Province/Region
            postal_code: Postal/ZIP code
            country_code: ISO 2-letter country code
            street_secondary: Building/Suite name (optional)
            
        Returns:
            Dict with address_sid and details
        """
        try:
            address = self.client.addresses.create(
                customer_name=customer_name,
                street=street,
                street_secondary=street_secondary,
                city=city,
                region=region,
                postal_code=postal_code,
                iso_country=country_code,
                friendly_name=f"{customer_name} - {city}, {country_code}"
            )
            
            logger.info(f"Created Twilio Address: {address.sid}")
            
            return {
                "success": True,
                "address_sid": address.sid,
                "validated": address.validated,
                "verified": address.verified
            }
            
        except TwilioRestException as e:
            logger.error(f"Failed to create Address: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": e.code
            }
    
    # ============== Supporting Documents ==============
    
    def create_supporting_document(
        self,
        friendly_name: str,
        document_type: str,
        attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a Supporting Document in Twilio.
        Required for some countries (proof of address, business registration, etc.)
        
        Args:
            friendly_name: Display name for the document
            document_type: Type of document (e.g., "business_registration")
            attributes: Document-specific attributes
            
        Returns:
            Dict with document_sid and details
        """
        try:
            document = self.client.numbers.v2.regulatory_compliance \
                .supporting_documents \
                .create(
                    friendly_name=friendly_name,
                    type=document_type,
                    attributes=attributes
                )
            
            logger.info(f"Created Supporting Document: {document.sid}")
            
            return {
                "success": True,
                "document_sid": document.sid,
                "status": document.status
            }
            
        except TwilioRestException as e:
            logger.error(f"Failed to create Supporting Document: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": e.code
            }
    
    # ============== Regulatory Bundle Management ==============
    
    def get_regulation_requirements(self, country_code: str, number_type: str = "local") -> Dict[str, Any]:
        """
        Get regulatory requirements for a specific country and number type.
        
        Args:
            country_code: ISO 2-letter country code
            number_type: Type of number (local, mobile, toll-free)
            
        Returns:
            Dict with regulation SID and requirements
        """
        try:
            # List regulations for the country
            regulations = self.client.numbers.v2.regulatory_compliance \
                .regulations \
                .list(
                    iso_country=country_code,
                    number_type=number_type
                )
            
            if not regulations:
                return {
                    "success": False,
                    "error": f"No regulations found for {country_code} {number_type} numbers"
                }
            
            regulation = regulations[0]
            
            return {
                "success": True,
                "regulation_sid": regulation.sid,
                "friendly_name": regulation.friendly_name,
                "number_type": regulation.number_type,
                "country_code": regulation.iso_country,
                "requirements": regulation.requirements
            }
            
        except TwilioRestException as e:
            logger.error(f"Failed to get regulations: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": e.code
            }
    
    def create_bundle(
        self,
        friendly_name: str,
        email: str,
        regulation_sid: str,
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Regulatory Bundle in Twilio.
        
        Args:
            friendly_name: Display name for the bundle
            email: Contact email for status updates
            regulation_sid: The regulation this bundle is for
            callback_url: Webhook URL for status updates
            
        Returns:
            Dict with bundle_sid and details
        """
        try:
            status_callback = callback_url or f"{TWILIO_WEBHOOK_BASE_URL}/api/regulatory/webhooks/twilio-bundle-status"
            
            bundle = self.client.numbers.v2.regulatory_compliance \
                .bundles \
                .create(
                    friendly_name=friendly_name,
                    email=email,
                    regulation_sid=regulation_sid,
                    status_callback=status_callback
                )
            
            logger.info(f"Created Regulatory Bundle: {bundle.sid}")
            
            return {
                "success": True,
                "bundle_sid": bundle.sid,
                "status": bundle.status,
                "regulation_sid": bundle.regulation_sid
            }
            
        except TwilioRestException as e:
            logger.error(f"Failed to create Bundle: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": e.code
            }
    
    def assign_item_to_bundle(
        self,
        bundle_sid: str,
        object_sid: str
    ) -> Dict[str, Any]:
        """
        Assign an item (End-User, Address, or Document) to a Bundle.
        
        Args:
            bundle_sid: The bundle to assign to
            object_sid: The SID of the item to assign
            
        Returns:
            Dict with assignment details
        """
        try:
            assignment = self.client.numbers.v2.regulatory_compliance \
                .bundles(bundle_sid) \
                .item_assignments \
                .create(object_sid=object_sid)
            
            logger.info(f"Assigned {object_sid} to bundle {bundle_sid}")
            
            return {
                "success": True,
                "assignment_sid": assignment.sid,
                "bundle_sid": assignment.bundle_sid,
                "object_sid": assignment.object_sid
            }
            
        except TwilioRestException as e:
            logger.error(f"Failed to assign item to bundle: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": e.code
            }
    
    def submit_bundle_for_review(self, bundle_sid: str) -> Dict[str, Any]:
        """
        Submit a bundle for Twilio review.
        The bundle must have all required items assigned.
        
        Args:
            bundle_sid: The bundle to submit
            
        Returns:
            Dict with submission status
        """
        try:
            bundle = self.client.numbers.v2.regulatory_compliance \
                .bundles(bundle_sid) \
                .update(status="pending-review")
            
            logger.info(f"Submitted bundle {bundle_sid} for review")
            
            return {
                "success": True,
                "bundle_sid": bundle.sid,
                "status": bundle.status
            }
            
        except TwilioRestException as e:
            logger.error(f"Failed to submit bundle for review: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": e.code
            }
    
    def get_bundle_status(self, bundle_sid: str) -> Dict[str, Any]:
        """
        Get the current status of a bundle.
        
        Args:
            bundle_sid: The bundle to check
            
        Returns:
            Dict with bundle status and details
        """
        try:
            bundle = self.client.numbers.v2.regulatory_compliance \
                .bundles(bundle_sid) \
                .fetch()
            
            return {
                "success": True,
                "bundle_sid": bundle.sid,
                "status": bundle.status,
                "valid_until": bundle.valid_until,
                "failure_reason": bundle.failure_reason
            }
            
        except TwilioRestException as e:
            logger.error(f"Failed to get bundle status: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": e.code
            }
    
    # ============== Complete Registration Flow ==============
    
    def register_address_for_country(
        self,
        country_code: str,
        business_name: str,
        street_address: str,
        street_secondary: Optional[str],
        city: str,
        region: str,
        postal_code: str,
        contact_name: str,
        contact_email: str,
        contact_phone: str,
        number_type: str = "local"
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Complete flow to register a business address for phone numbers in a country.
        
        This method:
        1. Gets regulatory requirements for the country
        2. Creates an End-User
        3. Creates an Address
        4. Creates a Regulatory Bundle
        5. Assigns End-User and Address to Bundle
        6. Submits Bundle for review
        
        Args:
            country_code: ISO 2-letter country code
            business_name: Legal business name
            street_address: Street address
            street_secondary: Building/Suite (optional)
            city: City
            region: State/Province/Region
            postal_code: Postal code
            contact_name: Contact person name
            contact_email: Contact email
            contact_phone: Contact phone
            number_type: Type of number (local, mobile, toll-free)
            
        Returns:
            Tuple of (success, result_dict)
        """
        result = {
            "end_user_sid": None,
            "address_sid": None,
            "bundle_sid": None,
            "regulation_sid": None,
            "status": None,
            "error": None
        }
        
        try:
            # Step 1: Get regulatory requirements
            logger.info(f"Step 1: Getting regulatory requirements for {country_code}")
            reg_result = self.get_regulation_requirements(country_code, number_type)
            if not reg_result.get("success"):
                result["error"] = f"Failed to get regulations: {reg_result.get('error')}"
                return False, result
            
            result["regulation_sid"] = reg_result["regulation_sid"]
            
            # Step 2: Create End-User
            logger.info(f"Step 2: Creating End-User for {business_name}")
            end_user_result = self.create_end_user(
                friendly_name=f"{business_name} - {contact_name}",
                business_name=business_name
            )
            if not end_user_result.get("success"):
                result["error"] = f"Failed to create End-User: {end_user_result.get('error')}"
                return False, result
            
            result["end_user_sid"] = end_user_result["end_user_sid"]
            
            # Step 3: Create Address
            logger.info(f"Step 3: Creating Address in {city}, {country_code}")
            address_result = self.create_address(
                customer_name=business_name,
                street=street_address,
                street_secondary=street_secondary,
                city=city,
                region=region,
                postal_code=postal_code,
                country_code=country_code
            )
            if not address_result.get("success"):
                result["error"] = f"Failed to create Address: {address_result.get('error')}"
                return False, result
            
            result["address_sid"] = address_result["address_sid"]
            
            # Step 4: Create Regulatory Bundle
            logger.info(f"Step 4: Creating Regulatory Bundle")
            bundle_result = self.create_bundle(
                friendly_name=f"{business_name} - {country_code} {number_type.capitalize()}",
                email=contact_email,
                regulation_sid=result["regulation_sid"]
            )
            if not bundle_result.get("success"):
                result["error"] = f"Failed to create Bundle: {bundle_result.get('error')}"
                return False, result
            
            result["bundle_sid"] = bundle_result["bundle_sid"]
            
            # Step 5: Assign End-User to Bundle
            logger.info(f"Step 5: Assigning End-User to Bundle")
            assign_result = self.assign_item_to_bundle(
                bundle_sid=result["bundle_sid"],
                object_sid=result["end_user_sid"]
            )
            if not assign_result.get("success"):
                result["error"] = f"Failed to assign End-User: {assign_result.get('error')}"
                return False, result
            
            # Step 6: Assign Address to Bundle
            logger.info(f"Step 6: Assigning Address to Bundle")
            assign_result = self.assign_item_to_bundle(
                bundle_sid=result["bundle_sid"],
                object_sid=result["address_sid"]
            )
            if not assign_result.get("success"):
                result["error"] = f"Failed to assign Address: {assign_result.get('error')}"
                return False, result
            
            # Step 7: Submit Bundle for Review
            logger.info(f"Step 7: Submitting Bundle for review")
            submit_result = self.submit_bundle_for_review(result["bundle_sid"])
            if not submit_result.get("success"):
                result["error"] = f"Failed to submit Bundle: {submit_result.get('error')}"
                return False, result
            
            result["status"] = submit_result["status"]
            
            logger.info(f"✅ Successfully registered address for {country_code}. Bundle: {result['bundle_sid']}")
            return True, result
            
        except Exception as e:
            logger.exception(f"Unexpected error in registration flow: {e}")
            result["error"] = str(e)
            return False, result
    
    # ============== Phone Number Purchase with Bundle ==============
    
    def purchase_phone_number(
        self,
        phone_number: str,
        bundle_sid: Optional[str] = None,
        friendly_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Purchase a phone number, optionally with a regulatory bundle.
        
        Args:
            phone_number: The phone number to purchase (E.164 format)
            bundle_sid: Regulatory bundle SID (required for regulated countries)
            friendly_name: Display name for the number
            
        Returns:
            Dict with purchase details
        """
        try:
            params = {
                "phone_number": phone_number,
            }
            
            if bundle_sid:
                params["bundle_sid"] = bundle_sid
            
            if friendly_name:
                params["friendly_name"] = friendly_name
            
            incoming_number = self.client.incoming_phone_numbers.create(**params)
            
            logger.info(f"Purchased phone number: {incoming_number.phone_number}")
            
            return {
                "success": True,
                "phone_number_sid": incoming_number.sid,
                "phone_number": incoming_number.phone_number,
                "friendly_name": incoming_number.friendly_name,
                "capabilities": {
                    "voice": incoming_number.capabilities.get("voice", False),
                    "sms": incoming_number.capabilities.get("sms", False),
                    "mms": incoming_number.capabilities.get("mms", False)
                }
            }
            
        except TwilioRestException as e:
            logger.error(f"Failed to purchase phone number: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": e.code
            }


# Singleton instance
_twilio_service: Optional[TwilioRegulatoryService] = None

def get_twilio_regulatory_service() -> TwilioRegulatoryService:
    """Get or create the Twilio Regulatory Service instance"""
    global _twilio_service
    if _twilio_service is None:
        _twilio_service = TwilioRegulatoryService()
    return _twilio_service