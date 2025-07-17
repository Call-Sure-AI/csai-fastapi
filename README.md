# FastAPI Starter

A simple FastAPI starter project with basic routes and configuration.

## Setup

### Prerequisites
- Python 3.12.10
- pip

### Installation

1. Clone the repository
```bash
git clone <your-repo-url>
cd <your-repo-name>
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