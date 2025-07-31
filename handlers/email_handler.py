import os
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.models.schemas import EmailRequest, EmailResponse

class EmailHandler:
    """Email handling controsller for sending emails"""
    
    @staticmethod
    async def send_email(email_request: EmailRequest) -> EmailResponse:
        """Send email using SMTP"""
        try:
            # Validate required fields (Pydantic already handles this, but explicit check)
            if not email_request.to or not email_request.subject or not email_request.html:
                raise HTTPException(
                    status_code=400, 
                    detail="Missing required fields: to, subject, html"
                )

            # Create email message
            message = MIMEMultipart('alternative')
            message['Subject'] = email_request.subject
            message['From'] = f"Callsure AI <noreply@callsure.ai>"
            message['To'] = email_request.to

            # Add HTML content
            html_part = MIMEText(email_request.html, 'html')
            message.attach(html_part)

            # Add text content if provided
            if email_request.text:
                text_part = MIMEText(email_request.text, 'plain')
                message.attach(text_part)

            # Send email using aiosmtplib
            await aiosmtplib.send(
                message,
                hostname='smtp.hostinger.com',
                port=465,
                use_tls=True,  # Use TLS/SSL
                username='noreply@callsure.ai',
                password=os.getenv('SMTP_PASSWORD'),
            )

            return EmailResponse(
                success=True,
                message="Email sent successfully"
            )

        except aiosmtplib.SMTPException as smtp_error:
            print(f'SMTP error: {smtp_error}')
            raise HTTPException(
                status_code=500, 
                detail=f"SMTP error: {str(smtp_error)}"
            )
        except Exception as error:
            print(f'Send email error: {error}')
            raise HTTPException(
                status_code=500, 
                detail="Internal server error"
            )
        
    async def send_otp_email(self, email: EmailStr, code: str) -> EmailResponse:
        """Send OTP email"""
        try:
            # Generate OTP email
            html = self._get_otp_email(code)
            
            # Send email
            await self.send_email(EmailRequest(
                to=email,
                subject="Your OTP Code",
                html=html
            ))
            
            return EmailResponse(
                success=True,
                message="Email sent successfully"
            )
        
        except Exception as error:
            print(f'Send OTP email error: {error}')
            raise HTTPException(
                status_code=500, 
                detail="Internal server error"
            )
        
    @staticmethod
    async def send_bulk_emails(recipients: list[EmailStr], subject: str, html: str) -> EmailResponse:
        """Send bulk emails to multiple recipients"""
        try:
            failed_emails = []
            successful_count = 0

            for recipient in recipients:
                try:
                    email_request = EmailRequest(
                        to=recipient,
                        subject=subject,
                        html=html
                    )
                    await EmailHandler.send_email(email_request)
                    successful_count += 1
                except Exception as e:
                    failed_emails.append({"email": recipient, "error": str(e)})

            if failed_emails:
                return EmailResponse(
                    success=False,
                    message=f"Sent {successful_count}/{len(recipients)} emails. {len(failed_emails)} failed."
                )
            else:
                return EmailResponse(
                    success=True,
                    message=f"All {successful_count} emails sent successfully"
                )

        except Exception as error:
            print(f'Bulk email error: {error}')
            raise HTTPException(
                status_code=500,
                detail="Internal server error"
            )

    @staticmethod
    async def send_template_email(
        to: EmailStr, 
        template_name: str, 
        template_data: dict,
        subject: str = None
    ) -> EmailResponse:
        """Send email using predefined templates"""
        try:
            # Load email template
            html_content = EmailHandler._get_email_template(template_name, template_data)
            
            # Use template subject if not provided
            if not subject:
                subject = EmailHandler._get_template_subject(template_name)

            email_request = EmailRequest(
                to=to,
                subject=subject,
                html=html_content
            )

            return await EmailHandler.send_email(email_request)

        except Exception as error:
            print(f'Template email error: {error}')
            raise HTTPException(
                status_code=500,
                detail="Internal server error"
            )

    @staticmethod
    def _get_email_template(template_name: str, data: dict) -> str:
        try:
            if template_name == 'otp':
                return EmailHandler._get_otp_template(data)
            elif template_name == 'welcome':
                return EmailHandler._get_welcome_template(data)
            elif template_name == 'password_reset':
                return EmailHandler._get_password_reset_template(data)
            elif template_name == 'verification':
                return EmailHandler._get_verification_template(data)
            elif template_name == 'monthly_invoice':
                return EmailHandler._get_monthly_invoice_template(data)
            else:
                raise ValueError(f"Template '{template_name}' not found")
                
        except Exception as e:
            raise ValueError(f"Failed to load template '{template_name}': {str(e)}")

    @staticmethod
    def _get_monthly_invoice_template(data: dict) -> str:
        """Generate monthly invoice email template"""
        try:
            client_name = data.get('client_name', 'Valued Client')
            invoice_number = data.get('invoice_number', 'N/A')
            billing_period = data.get('billing_period', 'N/A')
            amount_due = data.get('amount_due', '$0.00')
            due_date = data.get('due_date', 'N/A')
            services = data.get('services', [])
            
            services_html = ""
            if services:
                services_html = "<ul>"
                for service in services:
                    description = service.get('description', 'Service')
                    amount = service.get('amount', '$0.00')
                    services_html += f"<li>{description}: {amount}</li>"
                services_html += "</ul>"
            
            return f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="text-align: center; margin-bottom: 30px;">
                            <h1 style="color: #2c3e50; margin-bottom: 10px;">Monthly Invoice</h1>
                            <p style="color: #7f8c8d; font-size: 16px;">Invoice #{invoice_number}</p>
                        </div>
                        
                        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 30px;">
                            <h2 style="color: #2c3e50; margin-bottom: 15px;">Dear {client_name},</h2>
                            <p>We hope this message finds you well. Please find attached your monthly invoice for the billing period: <strong>{billing_period}</strong>.</p>
                        </div>
                        
                        <div style="border: 1px solid #e9ecef; border-radius: 8px; padding: 20px; margin-bottom: 30px;">
                            <h3 style="color: #2c3e50; margin-bottom: 15px;">Invoice Details</h3>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 10px 0; border-bottom: 1px solid #e9ecef;"><strong>Invoice Number:</strong></td>
                                    <td style="padding: 10px 0; border-bottom: 1px solid #e9ecef; text-align: right;">{invoice_number}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px 0; border-bottom: 1px solid #e9ecef;"><strong>Billing Period:</strong></td>
                                    <td style="padding: 10px 0; border-bottom: 1px solid #e9ecef; text-align: right;">{billing_period}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px 0; border-bottom: 1px solid #e9ecef;"><strong>Due Date:</strong></td>
                                    <td style="padding: 10px 0; border-bottom: 1px solid #e9ecef; text-align: right;">{due_date}</td>
                                </tr>
                                <tr style="background-color: #f8f9fa;">
                                    <td style="padding: 15px 0; font-size: 18px;"><strong>Total Amount Due:</strong></td>
                                    <td style="padding: 15px 0; font-size: 18px; font-weight: bold; color: #e74c3c; text-align: right;">{amount_due}</td>
                                </tr>
                            </table>
                        </div>
                        
                        {f'<div style="margin-bottom: 30px;"><h3 style="color: #2c3e50; margin-bottom: 15px;">Services Provided</h3>{services_html}</div>' if services else ''}
                        
                        <div style="background-color: #e8f5e8; padding: 20px; border-radius: 8px; border-left: 4px solid #28a745; margin-bottom: 30px;">
                            <h3 style="color: #155724; margin-bottom: 10px;">Payment Information</h3>
                            <p style="margin-bottom: 10px;">Please remit payment by <strong>{due_date}</strong> to avoid any late fees.</p>
                            <p style="margin-bottom: 0;">If you have any questions regarding this invoice, please don't hesitate to contact our billing department.</p>
                        </div>
                        
                        <div style="text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e9ecef;">
                            <p style="color: #7f8c8d; font-size: 14px; margin-bottom: 10px;">Thank you for your business!</p>
                            <p style="color: #7f8c8d; font-size: 12px;">This is an automated message. Please do not reply directly to this email.</p>
                        </div>
                    </div>
                </body>
            </html>
            """
            
        except Exception as e:
            raise ValueError(f"Failed to generate monthly invoice template: {str(e)}")


    @staticmethod
    def _get_template_subject(template_name: str) -> str:
        """Get default subject for template"""
        subjects = {
            'otp': 'Your OTP Code',
            'welcome': 'Welcome to Our Platform',
            'password_reset': 'Reset Your Password',
            'verification': 'Verify Your Email',
            'monthly_invoice': 'Monthly Invoice - Payment Due'
        }
        
        return subjects.get(template_name, 'Important Message')



    @staticmethod
    def _get_otp_template(data: dict) -> str:
        """OTP email template"""
        code = data.get('code', '000000')
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Your OTP Code</title>
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #162a47 0%, #3362A6 100%); padding: 30px; border-radius: 10px; text-align: center;">
                <h1 style="color: white; margin: 0;">Callsure AI</h1>
            </div>
            
            <div style="padding: 30px; background: #f9f9f9; border-radius: 0 0 10px 10px;">
                <h2 style="color: #162a47; margin-bottom: 20px;">Your Verification Code</h2>
                <p style="color: #666; font-size: 16px; line-height: 1.5;">
                    Use the following code to complete your sign-in process:
                </p>
                
                <div style="background: white; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
                    <div style="font-size: 32px; font-weight: bold; color: #3362A6; letter-spacing: 5px;">
                        {code}
                    </div>
                </div>
                
                <p style="color: #666; font-size: 14px;">
                    This code will expire in 10 minutes. If you didn't request this code, please ignore this email.
                </p>
            </div>
        </body>
        </html>
        """
    
    @staticmethod
    def _get_otp_email(code: str) -> str:
        """Generate OTP email HTML content"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Your OTP Code</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f4f4f4;">
            <div style="background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                <!-- Header -->
                <div style="background: linear-gradient(135deg, #162a47 0%, #3362A6 100%); padding: 30px; text-align: center;">
                    <h1 style="color: white; margin: 0; font-size: 28px; font-weight: bold;">Callsure AI</h1>
                    <p style="color: #e0e7ff; margin: 10px 0 0 0; font-size: 16px;">Verification Code</p>
                </div>
                
                <!-- Content -->
                <div style="padding: 40px 30px;">
                    <h2 style="color: #162a47; margin: 0 0 20px 0; font-size: 24px;">Your Verification Code</h2>
                    
                    <p style="color: #666; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                        We received a request to sign in to your Callsure AI account. Please use the verification code below to complete your sign-in:
                    </p>
                    
                    <!-- OTP Code Box -->
                    <div style="background: #f8fafc; border: 2px dashed #3362A6; padding: 25px; border-radius: 12px; text-align: center; margin: 30px 0;">
                        <div style="font-size: 36px; font-weight: bold; color: #3362A6; letter-spacing: 8px; font-family: 'Courier New', monospace;">
                            {code}
                        </div>
                    </div>
                    
                    <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 25px 0; border-radius: 4px;">
                        <p style="color: #856404; margin: 0; font-size: 14px;">
                            <strong>Important:</strong> This code will expire in 10 minutes for your security.
                        </p>
                    </div>
                    
                    <p style="color: #666; font-size: 14px; line-height: 1.5; margin-top: 30px;">
                        If you didn't request this verification code, please ignore this email. Your account remains secure.
                    </p>
                    
                    <!-- Help Section -->
                    <div style="border-top: 1px solid #e5e7eb; padding-top: 20px; margin-top: 30px;">
                        <p style="color: #9ca3af; font-size: 12px; text-align: center; margin: 0;">
                            Need help? Contact us at <a href="mailto:support@callsure.ai" style="color: #3362A6; text-decoration: none;">support@callsure.ai</a>
                        </p>
                    </div>
                </div>
            </div>
            
            <!-- Footer -->
            <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
                <p style="margin: 0;">© 2024 Callsure AI. All rights reserved.</p>
            </div>
        </body>
        </html>
        """

    @staticmethod
    def _get_welcome_template(data: dict) -> str:
        """Welcome email template"""
        name = data.get('name', 'User')
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Welcome to Callsure AI</title>
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #162a47 0%, #3362A6 100%); padding: 30px; border-radius: 10px; text-align: center;">
                <h1 style="color: white; margin: 0;">Welcome to Callsure AI</h1>
            </div>
            
            <div style="padding: 30px; background: #f9f9f9; border-radius: 0 0 10px 10px;">
                <h2 style="color: #162a47; margin-bottom: 20px;">Hello {name}!</h2>
                <p style="color: #666; font-size: 16px; line-height: 1.5;">
                    Welcome to Callsure AI! We're excited to have you on board.
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="https://callsure.ai/dashboard" style="background: #3362A6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Get Started
                    </a>
                </div>
                
                <p style="color: #666; font-size: 14px;">
                    If you have any questions, feel free to reach out to our support team.
                </p>
            </div>
        </body>
        </html>
        """

    @staticmethod
    def _get_password_reset_template(data: dict) -> str:
        """Password reset email template"""
        reset_link = data.get('reset_link', '#')
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Reset Your Password</title>
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #162a47 0%, #3362A6 100%); padding: 30px; border-radius: 10px; text-align: center;">
                <h1 style="color: white; margin: 0;">Callsure AI</h1>
            </div>
            
            <div style="padding: 30px; background: #f9f9f9; border-radius: 0 0 10px 10px;">
                <h2 style="color: #162a47; margin-bottom: 20px;">Reset Your Password</h2>
                <p style="color: #666; font-size: 16px; line-height: 1.5;">
                    Click the button below to reset your password:
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" style="background: #3362A6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Reset Password
                    </a>
                </div>
                
                <p style="color: #666; font-size: 14px;">
                    This link will expire in 1 hour. If you didn't request this reset, please ignore this email.
                </p>
            </div>
        </body>
        </html>
        """

    @staticmethod
    def _get_verification_template(data: dict) -> str:
        """Email verification template"""
        verification_link = data.get('verification_link', '#')
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Verify Your Email</title>
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #162a47 0%, #3362A6 100%); padding: 30px; border-radius: 10px; text-align: center;">
                <h1 style="color: white; margin: 0;">Callsure AI</h1>
            </div>
            
            <div style="padding: 30px; background: #f9f9f9; border-radius: 0 0 10px 10px;">
                <h2 style="color: #162a47; margin-bottom: 20px;">Verify Your Email</h2>
                <p style="color: #666; font-size: 16px; line-height: 1.5;">
                    Click the button below to verify your email address:
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_link}" style="background: #3362A6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Verify Email
                    </a>
                </div>
                
                <p style="color: #666; font-size: 14px;">
                    If you didn't create an account, please ignore this email.
                </p>
            </div>
        </body>
        </html>
        """
    
email_handler = EmailHandler()