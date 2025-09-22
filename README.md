# FastAPI Backend for Library Management System

This directory contains the FastAPI backend that replaces Supabase functionality.

## Setup Instructions

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy environment file and configure values:
```bash
cp .env.example .env
# then edit .env and set DATABASE_URL, SECRET_KEY, ALLOWED_ORIGINS, etc.
```

3. Setup PostgreSQL database (if not already created):
```bash
# Create database
createdb library_management
```

4. Run migrations:
```bash
python -m alembic upgrade head
```

5. Start the server:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation

Once running, visit http://localhost:8000/docs for interactive API documentation.

## Project Structure

```
Backend/
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── alembic.ini            # Database migration configuration
├── alembic/               # Database migrations
├── app/
│   ├── __init__.py
│   ├── core/              # Core configuration
│   ├── models/            # Database models
│   ├── schemas/           # Pydantic schemas
│   ├── api/               # API routes
│   ├── services/          # Business logic
│   ├── auth/              # Authentication
│   └── database.py        # Database connection
└── tests/                 # Test files
```
