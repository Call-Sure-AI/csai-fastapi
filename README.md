# FastAPI Starter

A simple FastAPI starter project with basic routes and configuration.

## Setup

### Prerequisites
- Python 3.12.10
- pip

### Installation

1. Clone the repository
```bash
git clone [csai-fastapi](https://github.com/Call-Sure-AI/csai-fastapi)
cd csai-fastapi
```

2. Create and activate virtual environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Set up environment variables (optional)
```bash
copy .env.example .env
# Edit .env file with your configuration
```

### Running the Server

Start the development server:
```bash
uvicorn app.main:app --reload
```

The API will be available at:
- Main app: http://localhost:8000

## API Endpoints

- `GET /` - Welcome message
- `GET /api/health` - Health check

## Project Structure

```
├── app/
│   └── main.py          # FastAPI application
├── routes/
│   └── health_check.py       # Basic API routes
├── handlers/            # Request handlers
├── scripts/             # Scripts
├── config.py            # Configuration settings
├── requirements.txt     # Python dependencies
├── .env.example        # Environment variables template
└── README.md           # This file
```

Key Improvements in This Setup
1. Clean Separation of Concerns

main.py handles app configuration, middleware, and lifecycle
routes/__init__.py handles route organization
Easy to find and modify routes

2. Production-Ready Features

Request timing middleware
Global exception handling
Health checks for voice system
Prometheus metrics endpoint
Security middleware (CORS, Trusted Host)
Response compression

3. Voice System Optimizations

Database latency monitoring
Connection pool statistics
Active agent counting
Sub-100ms latency checks

4. Developer Experience

Debug routes in development
Structured logging
Clear startup/shutdown logs
API documentation at /api/docs

5. Scalability

Easy to add API versioning
Modular route structure
Environment-based configuration
Multi-worker support in production


Usage Examples
bash# Development
uvicorn app.main:app --reload --port 8000

# Production
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000


API Structure
/                       # Root - System status
/health                 # Detailed health check
/metrics               # Prometheus metrics
/api/docs              # Swagger UI
/api/redoc             # ReDoc UI
/api/auth/*            # Authentication endpoints
/api/agents/*          # Agent management
/api/companies/*       # Company management
/api/email/*           # Email services
/api/invitations/*     # Invitation system
/api/s3/*              # File storage
/api/health            # API health check

API Endpoints
With this setup, your endpoints will be:

GET /api/agents/ - Get all agents for the current user
GET /api/agents/test - Test endpoint (public)
GET /api/agents/{agent_id} - Get specific agent
GET /api/agents/user/{user_id} - Get agents by user ID
POST /api/agents/ - Create new agent
PUT /api/agents/{agent_id} - Update agent
DELETE /api/agents/{agent_id} - Delete agent
 
This structure is much better for a production voice calling system because it:

Keeps the main.py focused on app configuration
Makes routes easier to manage and test
Provides better monitoring and debugging capabilities
Scales better as your system grows