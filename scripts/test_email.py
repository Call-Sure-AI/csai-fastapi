#!/usr/bin/env python3
"""
Script to test email functionality
Usage: python scripts/test_email.py
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.email_handler import EmailHandler, EmailRequest

async def test_basic_email():
    print("Testing basic email sending...")
    
    email_handler = EmailHandler()
    request = EmailRequest(
        to="test@example.com",
        subject="Test Email",
        html="<h1>Test Email</h1><p>This is a test email from Callsure AI.</p>"
    )
    
    try:
        result = await email_handler.send_email(request)
        print(f"✅ Basic email test: {result.message}")
        return True
    except Exception as e:
        print(f"❌ Basic email test failed: {e}")
        return False

async def test_otp_email():
    print("Testing OTP email template...")
    
    email_handler = EmailHandler()
    
    try:
        result = await email_handler.send_otp_email("test@example.com", "123456")
        print(f"✅ OTP email test: {result.message}")
        return True
    except Exception as e:
        print(f"❌ OTP email test failed: {e}")
        return False

async def test_template_email():
    print("Testing template email...")
    
    email_handler = EmailHandler()
    
    try:
        result = await email_handler.send_template_email(
            to="test@example.com",
            template_name="welcome",
            template_data={"name": "John Doe"}
        )
        print(f"✅ Template email test: {result.message}")
        return True
    except Exception as e:
        print(f"❌ Template email test failed: {e}")
        return False

async def main():
    print("🚀 Starting email tests...\n")
    
    tests = [
        test_basic_email,
        test_otp_email,
        test_template_email
    ]
    
    results = []
    for test in tests:
        result = await test()
        results.append(result)
        print()
    
    passed = sum(results)
    total = len(results)
    
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed. Check your email configuration.")

if __name__ == "__main__":
    asyncio.run(main())
