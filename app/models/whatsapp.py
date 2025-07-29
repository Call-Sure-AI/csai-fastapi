from pydantic import BaseModel
from typing import Optional

class WhatsAppOnboardRequest(BaseModel):
    status: str  # "FINISH" or "CANCEL"
    business_id: Optional[str] = None
    waba_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    code: Optional[str] = None
    current_step: Optional[str] = None

class WhatsAppMessageRequest(BaseModel):
    business_id: str
    to: str
    message: str

class WhatsAppClient(BaseModel):
    business_id: str
    waba_id: str
    phone_number_id: str
    access_token: Optional[str] = None
    status: str
    current_step: Optional[str] = None
