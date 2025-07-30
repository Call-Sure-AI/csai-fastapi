Complete WhatsApp Routes Features:
Core Messaging Endpoints:

POST /whatsapp/onboard - Onboard WhatsApp Business Account
POST /whatsapp/send-message - Send text messages
POST /whatsapp/send-template - Send template messages
POST /whatsapp/send-media - Send media (images, docs, audio, video)
POST /whatsapp/send-bulk - Send bulk messages (up to 100 recipients)

Business Management:

GET /whatsapp/status/{business_id} - Get onboarding status
GET /whatsapp/businesses - List all businesses (with pagination)
DELETE /whatsapp/business/{business_id} - Delete business config
POST /whatsapp/test-connection/{business_id} - Test connection

Webhook Handling:

GET /whatsapp/webhook - Webhook verification (for WhatsApp)
POST /whatsapp/webhook - Receive incoming messages/status updates

Utility Endpoints:

GET /whatsapp/health - Service health check
GET /whatsapp/config - Get configuration info

Key Features:
✅ Complete Error Handling - Proper HTTP status codes and error messages
✅ Authentication - All endpoints require user authentication
✅ Logging - Comprehensive logging throughout
✅ Validation - Request validation with Pydantic schemas
✅ Documentation - OpenAPI/Swagger documentation strings
✅ Pagination - For listing endpoints
✅ Webhook Support - Full webhook verification and processing
✅ Health Checks - Service monitoring endpoints
✅ Database Integration - Proper transaction handling
Usage Examples:
python# Send a message
POST /whatsapp/send-message
{
    "business_id": "business_123",
    "to": "+1234567890",
    "message": "Hello from WhatsApp!"
}

# Send bulk messages
POST /whatsapp/send-bulk
{
    "business_id": "business_123", 
    "recipients": ["+1234567890", "+0987654321"],
    "message": "Bulk notification"
}

# Get business status
GET /whatsapp/status/business_123
The routes are production-ready with comprehensive error handling, logging, authentication, and full WhatsApp Business API integration!




# WhatsApp API - Complete cURL Commands
# Replace YOUR_JWT_TOKEN with your actual JWT token
# Replace localhost:8080 with your actual server URL

# Set your base URL and token
BASE_URL="http://localhost:8080"
JWT_TOKEN="YOUR_JWT_TOKEN_HERE"

# ====================================
# 1. ONBOARD WHATSAPP BUSINESS ACCOUNT
# ====================================

# Onboard with FINISH status (successful onboarding)
curl -X POST "${BASE_URL}/whatsapp/onboard" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -d '{
    "business_id": "business_123",
    "status": "FINISH",
    "waba_id": "1234567890123456",
    "phone_number_id": "1234567890123456",
    "code": "AQBx7B2Z...",
    "current_step": "completed"
  }'

# Onboard with CANCEL status
curl -X POST "${BASE_URL}/whatsapp/onboard" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -d '{
    "business_id": "business_456",
    "status": "CANCEL",
    "current_step": "cancelled"
  }'

# ====================================
# 2. SEND TEXT MESSAGE
# ====================================

# Send a simple text message
curl -X POST "${BASE_URL}/whatsapp/send-message" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -d '{
    "business_id": "business_123",
    "to": "+1234567890",
    "message": "Hello from WhatsApp! 👋",
    "type": "text",
    "preview_url": true
  }'

# Send message with context (reply to another message)
curl -X POST "${BASE_URL}/whatsapp/send-message" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -d '{
    "business_id": "business_123",
    "to": "+1234567890",
    "message": "Thanks for your message!",
    "type": "text",
    "context": {
      "message_id": "wamid.HBgLMTIzNDU2Nzg5MBUCABIYFjNBN0Y4QjY5RTNCNzFFNThBODhEOUYA"
    }
  }'

# ====================================
# 3. SEND TEMPLATE MESSAGE
# ====================================

# Send a simple template message
curl -X POST "${BASE_URL}/whatsapp/send-template" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -d '{
    "business_id": "business_123",
    "to": "+1234567890",
    "template_name": "welcome_message",
    "language_code": "en"
  }'

# Send template with parameters
curl -X POST "${BASE_URL}/whatsapp/send-template" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -d '{
    "business_id": "business_123",
    "to": "+1234567890",
    "template_name": "order_confirmation",
    "language_code": "en",
    "components": [
      {
        "type": "body",
        "parameters": [
          {
            "type": "text",
            "text": "John Doe"
          },
          {
            "type": "text",
            "text": "ORD-12345"
          }
        ]
      }
    ]
  }'

# ====================================
# 4. SEND MEDIA MESSAGES
# ====================================

# Send image with URL
curl -X POST "${BASE_URL}/whatsapp/send-media" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -d '{
    "business_id": "business_123",
    "to": "+1234567890",
    "media_type": "image",
    "media_url": "https://example.com/image.jpg",
    "caption": "Check out this amazing image! 📸"
  }'

# Send document with media ID
curl -X POST "${BASE_URL}/whatsapp/send-media" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -d '{
    "business_id": "business_123",
    "to": "+1234567890",
    "media_type": "document",
    "media_id": "1234567890123456",
    "filename": "invoice.pdf",
    "caption": "Your invoice is attached"
  }'

# Send audio file
curl -X POST "${BASE_URL}/whatsapp/send-media" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -d '{
    "business_id": "business_123",
    "to": "+1234567890",
    "media_type": "audio",
    "media_url": "https://example.com/audio.mp3"
  }'

# Send video with caption
curl -X POST "${BASE_URL}/whatsapp/send-media" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -d '{
    "business_id": "business_123",
    "to": "+1234567890",
    "media_type": "video",
    "media_url": "https://example.com/video.mp4",
    "caption": "Product demo video 🎥"
  }'

# ====================================
# 5. SEND BULK MESSAGES
# ====================================

# Send bulk messages to multiple recipients
curl -X POST "${BASE_URL}/whatsapp/send-bulk" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -d '{
    "business_id": "business_123",
    "recipients": [
      "+1234567890",
      "+0987654321",
      "+1122334455"
    ],
    "message": "Important announcement: Our store will be closed tomorrow for maintenance. 🔧",
    "type": "text"
  }'

# ====================================
# 6. GET BUSINESS STATUS
# ====================================

# Get status for a specific business
curl -X GET "${BASE_URL}/whatsapp/status/business_123" \
  -H "Authorization: Bearer ${JWT_TOKEN}"

# ====================================
# 7. LIST ALL BUSINESSES
# ====================================

# List all businesses (default pagination)
curl -X GET "${BASE_URL}/whatsapp/businesses" \
  -H "Authorization: Bearer ${JWT_TOKEN}"

# List businesses with pagination
curl -X GET "${BASE_URL}/whatsapp/businesses?limit=10&offset=0" \
  -H "Authorization: Bearer ${JWT_TOKEN}"

# ====================================
# 8. DELETE BUSINESS
# ====================================

# Delete a business configuration
curl -X DELETE "${BASE_URL}/whatsapp/business/business_123" \
  -H "Authorization: Bearer ${JWT_TOKEN}"

# ====================================
# 9. TEST CONNECTION
# ====================================

# Test WhatsApp connection for a business
curl -X POST "${BASE_URL}/whatsapp/test-connection/business_123" \
  -H "Authorization: Bearer ${JWT_TOKEN}"

# ====================================
# 10. WEBHOOK VERIFICATION (WhatsApp calls this)
# ====================================

# This is called by WhatsApp to verify your webhook
# You don't need to call this manually, but here's the format:
curl -X GET "${BASE_URL}/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=your_webhook_verify_token&hub.challenge=random_challenge_string"

# ====================================
# 11. WEBHOOK RECEIVE (WhatsApp calls this)
# ====================================

# This is called by WhatsApp to send you messages/status updates
# You don't call this manually, but here's what WhatsApp sends:
curl -X POST "${BASE_URL}/whatsapp/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "object": "whatsapp_business_account",
    "entry": [
      {
        "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
        "changes": [
          {
            "value": {
              "messaging_product": "whatsapp",
              "metadata": {
                "display_phone_number": "15551234567",
                "phone_number_id": "PHONE_NUMBER_ID"
              },
              "messages": [
                {
                  "from": "PHONE_NUMBER",
                  "id": "wamid.ID",
                  "timestamp": "TIMESTAMP",
                  "text": {
                    "body": "MESSAGE_BODY"
                  },
                  "type": "text"
                }
              ]
            },
            "field": "messages"
          }
        ]
      }
    ]
  }'

# ====================================
# 12. HEALTH CHECK
# ====================================

# Check service health
curl -X GET "${BASE_URL}/whatsapp/health"

# ====================================
# 13. GET CONFIGURATION
# ====================================

# Get WhatsApp configuration
curl -X GET "${BASE_URL}/whatsapp/config" \
  -H "Authorization: Bearer ${JWT_TOKEN}"

# ====================================
# EXAMPLE RESPONSES
# ====================================

# Successful message send response:
# {
#   "message_id": "wamid.HBgLMTIzNDU2Nzg5MBUCABIYFjNBN0Y4QjY5RTNCNzFFNThBODhEOUYA",
#   "status": "sent",
#   "to": "+1234567890"
# }

# Bulk message response:
# {
#   "total_messages": 3,
#   "successful": 2,
#   "failed": 1,
#   "results": [
#     {
#       "message_id": "wamid.123",
#       "status": "sent",
#       "to": "+1234567890"
#     },
#     {
#       "message_id": "wamid.456",
#       "status": "sent",
#       "to": "+0987654321"
#     },
#     {
#       "message_id": "",
#       "status": "failed",
#       "to": "+1122334455",
#       "error_message": "Invalid phone number"
#     }
#   ]
# }

# Business status response:
# {
#   "business_id": "business_123",
#   "status": "FINISH",
#   "current_step": "completed",
#   "waba_id": "1234567890123456",
#   "phone_number_id": "1234567890123456",
#   "has_token": true,
#   "created_at": "2025-01-01T10:00:00Z",
#   "updated_at": "2025-01-01T10:30:00Z"
# }

# ====================================
# ERROR EXAMPLES
# ====================================

# Invalid phone number error (400):
# {
#   "detail": "Phone number must be in format +1234567890 (10-15 digits)"
# }

# Business not onboarded error (400):
# {
#   "detail": "Business not onboarded or missing access token"
# }

# Authentication error (401):
# {
#   "detail": "Could not validate credentials"
# }

# Business not found error (404):
# {
#   "detail": "Business not found"
# }

# Rate limit error (from WhatsApp):
# {
#   "message_id": "",
#   "status": "rate_limited",
#   "to": "+1234567890",
#   "error_message": "Rate limit exceeded"
# }