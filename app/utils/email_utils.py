import re
from typing import List, Dict, Any
from email.utils import parseaddr
import html

class EmailUtils:
    @staticmethod
    def validate_email_format(email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def sanitize_html(html_content: str) -> str:
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.IGNORECASE | re.DOTALL)
        html_content = re.sub(r'\s*on\w+\s*=\s*["\'][^"\']*["\']', '', html_content, flags=re.IGNORECASE)
        
        return html_content
    
    @staticmethod
    def extract_email_name(email: str) -> tuple:
        name, addr = parseaddr(email)
        return name, addr
    
    @staticmethod
    def format_email_address(email: str, name: str = None) -> str:
        if name:
            return f"{name} <{email}>"
        return email
    
    @staticmethod
    def validate_bulk_recipients(recipients: List[str], max_recipients: int = 100) -> Dict[str, Any]:
        valid_emails = []
        invalid_emails = []
        
        if len(recipients) > max_recipients:
            return {
                "valid": False,
                "error": f"Too many recipients (max {max_recipients})",
                "valid_emails": [],
                "invalid_emails": recipients
            }
        
        for email in recipients:
            if EmailUtils.validate_email_format(email):
                valid_emails.append(email)
            else:
                invalid_emails.append(email)
        
        return {
            "valid": len(invalid_emails) == 0,
            "valid_emails": valid_emails,
            "invalid_emails": invalid_emails,
            "error": f"Invalid emails found: {invalid_emails}" if invalid_emails else None
        }
    
    @staticmethod
    def create_unsubscribe_link(email: str, list_id: str = None) -> str:
        base_url = "https://callsure.ai/unsubscribe"
        if list_id:
            return f"{base_url}?email={email}&list={list_id}"
        return f"{base_url}?email={email}"
    
    @staticmethod
    def add_tracking_pixel(html_content: str, tracking_id: str) -> str:
        tracking_pixel = f'<img src="https://callsure.ai/track/open/{tracking_id}" width="1" height="1" style="display:none;" />'

        if '</body>' in html_content:
            html_content = html_content.replace('</body>', f'{tracking_pixel}</body>')
        else:
            html_content += tracking_pixel
        
        return html_content
