"""
WhatsApp Onboarding Helper

This utility helps manage the WhatsApp Business API onboarding flow,
including generating proper authorization URLs and handling expired codes.
"""

import os
import urllib.parse
from typing import Dict, Any, Optional
from config import Config
import logging

logger = logging.getLogger(__name__)

class WhatsAppOnboardingHelper:
    
    def __init__(self):
        self.fb_app_id = Config.FACEBOOK_APP_ID
        self.facebook_version = Config.FACEBOOK_VERSION
        self.frontend_url = Config.FRONTEND_URL
        
    def generate_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate WhatsApp Business API authorization URL
        
        Args:
            state: Optional state parameter for security/tracking
            
        Returns:
            Authorization URL that users should visit to grant permissions
        """
        redirect_uri = f"{self.frontend_url}/whatsapp/callback"
        
        # Required permissions for WhatsApp Business API
        scope = "whatsapp_business_management,whatsapp_business_messaging"
        
        params = {
            "client_id": self.fb_app_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "response_type": "code"
        }
        
        if state:
            params["state"] = state
            
        query_string = urllib.parse.urlencode(params)
        auth_url = f"https://www.facebook.com/{self.facebook_version}/dialog/oauth?{query_string}"
        
        logger.info(f"Generated authorization URL: {auth_url}")
        return auth_url
    
    def generate_onboarding_response(self, business_id: str, error_type: str = None) -> Dict[str, Any]:
        """
        Generate appropriate response for onboarding errors
        
        Args:
            business_id: Business ID attempting onboarding
            error_type: Type of error that occurred
            
        Returns:
            Response with new authorization URL and instructions
        """
        auth_url = self.generate_authorization_url(state=business_id)
        
        response = {
            "error": "Authorization code expired or invalid",
            "error_type": error_type or "expired_code",
            "business_id": business_id,
            "action_required": "Please complete the authorization process again",
            "authorization_url": auth_url,
            "instructions": {
                "step1": "Click the authorization_url link",
                "step2": "Log in to Facebook and grant permissions",
                "step3": "You will be redirected back with a new authorization code",
                "step4": "The onboarding will complete automatically"
            },
            "notes": [
                "Authorization codes expire within 10 minutes",
                "Make sure to complete the process quickly",
                "If you encounter issues, clear your browser cache and try again"
            ]
        }
        
        return response
    
    def validate_callback_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate parameters returned from Facebook OAuth callback
        
        Args:
            params: Query parameters from the callback URL
            
        Returns:
            Validation result with status and any errors
        """
        result = {"valid": False, "errors": [], "data": {}}
        
        # Check for error in callback
        if "error" in params:
            error_description = params.get("error_description", "Unknown error")
            result["errors"].append(f"OAuth error: {error_description}")
            return result
        
        # Check for required authorization code
        if "code" not in params:
            result["errors"].append("Authorization code missing from callback")
            return result
        
        code = params["code"]
        if not code or len(code.strip()) == 0:
            result["errors"].append("Authorization code is empty")
            return result
        
        # Extract other useful parameters
        state = params.get("state")  # Can be used to identify the business
        
        result.update({
            "valid": True,
            "data": {
                "code": code,
                "state": state
            }
        })
        
        return result
    
    def get_troubleshooting_guide(self) -> Dict[str, Any]:
        """
        Get troubleshooting guide for common onboarding issues
        
        Returns:
            Comprehensive troubleshooting guide
        """
        return {
            "common_issues": {
                "expired_authorization_code": {
                    "description": "The authorization code has expired (typically after 10 minutes)",
                    "solution": "Restart the onboarding process with a new authorization URL",
                    "prevention": "Complete the onboarding process immediately after clicking the authorization link"
                },
                "invalid_redirect_uri": {
                    "description": "The redirect URI doesn't match what's configured in Facebook App",
                    "solution": "Ensure the redirect URI in your Facebook App settings matches your frontend URL",
                    "check": f"Current redirect URI: {self.frontend_url}/whatsapp/callback"
                },
                "insufficient_permissions": {
                    "description": "The app doesn't have required WhatsApp Business permissions",
                    "solution": "Ensure your Facebook App has WhatsApp Business API permissions enabled",
                    "required_permissions": ["whatsapp_business_management", "whatsapp_business_messaging"]
                },
                "invalid_app_configuration": {
                    "description": "Facebook App ID or Secret is incorrect",
                    "solution": "Verify FACEBOOK_APP_ID and FACEBOOK_APP_SECRET environment variables",
                    "current_app_id": self.fb_app_id
                }
            },
            "debugging_steps": [
                "1. Check that FACEBOOK_APP_ID and FACEBOOK_APP_SECRET are correctly set",
                "2. Verify that your Facebook App has WhatsApp Business API permissions",
                "3. Ensure the redirect URI matches your Facebook App configuration",
                "4. Clear browser cache and cookies for Facebook",
                "5. Try the onboarding process in an incognito/private browser window",
                "6. Check that your business has been approved for WhatsApp Business API"
            ],
            "configuration_checklist": {
                "app_id_set": bool(self.fb_app_id),
                "app_secret_set": bool(os.getenv('FACEBOOK_APP_SECRET')),
                "frontend_url_set": bool(self.frontend_url),
                "facebook_version": self.facebook_version,
                "redirect_uri": f"{self.frontend_url}/whatsapp/callback" if self.frontend_url else "Not configured"
            },
            "next_steps": {
                "if_code_expired": [
                    "Generate new authorization URL using /whatsapp/start-onboarding endpoint",
                    "Complete the authorization process within 10 minutes",
                    "Submit the onboarding request immediately after callback"
                ],
                "if_permissions_missing": [
                    "Go to Facebook Developer Console",
                    "Navigate to your app's WhatsApp > Getting Started",
                    "Request WhatsApp Business API permissions",
                    "Wait for approval (can take several days)"
                ],
                "if_still_failing": [
                    "Check server logs for detailed error messages",
                    "Verify network connectivity to graph.facebook.com",
                    "Contact Facebook support if app-level issues persist"
                ]
            }
        }
    
    def create_onboarding_session(self, business_id: str, user_id: str) -> Dict[str, Any]:
        """
        Create a new onboarding session with tracking
        
        Args:
            business_id: Business ID for the onboarding
            user_id: User initiating the onboarding
            
        Returns:
            Session information with authorization URL
        """
        import time
        import hashlib
        
        # Create a unique state parameter for security
        timestamp = str(int(time.time()))
        state_data = f"{business_id}:{user_id}:{timestamp}"
        state = hashlib.md5(state_data.encode()).hexdigest()
        
        auth_url = self.generate_authorization_url(state=state)
        
        session_info = {
            "session_id": state,
            "business_id": business_id,
            "user_id": user_id,
            "created_at": timestamp,
            "authorization_url": auth_url,
            "expires_in": 600,  # 10 minutes
            "status": "pending",
            "instructions": {
                "step1": "Click the authorization URL to grant permissions",
                "step2": "Complete the Facebook OAuth flow",
                "step3": "You'll be redirected back automatically",
                "step4": "The onboarding will complete within seconds"
            },
            "important_notes": [
                "⏰ You have 10 minutes to complete this process",
                "🔒 Keep this session secure - don't share the URLs",
                "🔄 If expired, you'll need to restart the process",
                "📱 Make sure your WhatsApp Business Account is ready"
            ]
        }
        
        logger.info(f"Created onboarding session {state} for business {business_id}")
        return session_info
    
    def parse_state_parameter(self, state: str) -> Optional[Dict[str, str]]:
        """
        Parse state parameter to extract session information
        
        Args:
            state: State parameter from OAuth callback
            
        Returns:
            Parsed session information or None if invalid
        """
        try:
            # In a real implementation, you'd want to store and validate sessions
            # For now, we'll just return the business_id if state looks valid
            if state and len(state) == 32:  # MD5 hash length
                return {
                    "session_id": state,
                    "valid": True
                }
            return None
        except Exception as e:
            logger.error(f"Error parsing state parameter: {e}")
            return None
    
    def get_retry_strategy(self, error_type: str) -> Dict[str, Any]:
        """
        Get retry strategy based on error type
        
        Args:
            error_type: Type of error encountered
            
        Returns:
            Retry strategy with recommendations
        """
        strategies = {
            "expired_code": {
                "should_retry": True,
                "retry_immediately": True,
                "max_retries": 3,
                "strategy": "Generate new authorization URL and restart process",
                "wait_time": 0,
                "user_action": "Click the new authorization link immediately"
            },
            "invalid_app_config": {
                "should_retry": False,
                "retry_immediately": False,
                "max_retries": 0,
                "strategy": "Fix configuration before retrying",
                "wait_time": 0,
                "user_action": "Contact administrator to fix app configuration"
            },
            "rate_limit": {
                "should_retry": True,
                "retry_immediately": False,
                "max_retries": 5,
                "strategy": "Exponential backoff",
                "wait_time": 60,  # Start with 1 minute
                "user_action": "Wait before retrying"
            },
            "permissions_denied": {
                "should_retry": False,
                "retry_immediately": False,
                "max_retries": 0,
                "strategy": "User must grant permissions manually",
                "wait_time": 0,
                "user_action": "Complete the authorization flow and grant all requested permissions"
            },
            "network_error": {
                "should_retry": True,
                "retry_immediately": True,
                "max_retries": 3,
                "strategy": "Retry with same parameters",
                "wait_time": 5,
                "user_action": "Check internet connection and try again"
            }
        }
        
        return strategies.get(error_type, {
            "should_retry": True,
            "retry_immediately": False,
            "max_retries": 1,
            "strategy": "Generic retry",
            "wait_time": 30,
            "user_action": "Try again in a few moments"
        })
    
    def validate_business_account(self, waba_id: str, phone_number_id: str) -> Dict[str, Any]:
        """
        Validate WhatsApp Business Account parameters
        
        Args:
            waba_id: WhatsApp Business Account ID
            phone_number_id: Phone Number ID
            
        Returns:
            Validation result
        """
        result = {"valid": True, "errors": [], "warnings": []}
        
        # Validate WABA ID format (should be numeric)
        if not waba_id or not waba_id.isdigit():
            result["valid"] = False
            result["errors"].append("Invalid WhatsApp Business Account ID format")
        
        # Validate Phone Number ID format (should be numeric)
        if not phone_number_id or not phone_number_id.isdigit():
            result["valid"] = False
            result["errors"].append("Invalid Phone Number ID format")
        
        # Check if IDs are reasonable length
        if waba_id and len(waba_id) < 10:
            result["warnings"].append("WABA ID seems shorter than expected")
        
        if phone_number_id and len(phone_number_id) < 10:
            result["warnings"].append("Phone Number ID seems shorter than expected")
        
        return result