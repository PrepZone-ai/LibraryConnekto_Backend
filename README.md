## LibraryConnekto — FastAPI Backend

Production-ready FastAPI backend powering LibraryConnekto: authentication, student/admin management, bookings, referrals, subscriptions, notifications, and payments.

Badges
- Python 3.11+ / FastAPI / SQLAlchemy / Alembic
- PostgreSQL

### Features
- Authentication with JWT (admin and student roles)
- Student lifecycle: profiles, attendance, tasks, exams, messages
- Admin panel APIs: library stats, management endpoints
- Seat booking (anonymous and authenticated)
- Referrals and codes validation
- Subscription plans and management
- Notifications (in-app) + optional email via SMTP
- Payments integration surface (Razorpay)
- Alembic migrations and background scheduler

### Tech Stack
- FastAPI, Pydantic, SQLAlchemy (sync + async engine available)
- Alembic for migrations
- PostgreSQL
- python-jose, passlib[bcrypt] for auth
- Optional: SMTP and Razorpay via environment configuration

---

## Getting Started

1) Install dependencies
```bash
pip install -r requirements.txt
```

2) Configure environment
Create `Backend/.env` with your values. Required keys:
```env
# Database
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DB_NAME

# JWT
SECRET_KEY=change-me
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS (comma-separated list)
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# File uploads
UPLOAD_DIR=uploads
MAX_FILE_SIZE=10485760

# SMTP (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=
SMTP_PASSWORD=

# Razorpay (optional)
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=

# Scheduler / Notifications
EMAIL_SCHEDULER_ENABLED=true
SCHEDULER_INITIAL_DELAY_SECONDS=60
SCHEDULER_LOOP_INTERVAL_SECONDS=60
SUBSCRIPTION_CHECKS_DAILY_ENABLED=true
SUBSCRIPTION_EMAIL_FROM_SCHEDULER_ENABLED=false
```

3) Initialize database and run migrations
```bash
python -m alembic upgrade head
```

4) Run the server
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API docs: `http://localhost:8000/docs`  |  Health: `http://localhost:8000/health`

---

## Configuration Notes
- All sensitive values are read from environment (`app/core/config.py` loads `.env`).
- CORS is driven by `ALLOWED_ORIGINS` (comma-separated). Use `*` only for local development.
- `UPLOAD_DIR` is mounted at `/uploads` for static access.
- Background notification scheduler starts on app startup when `EMAIL_SCHEDULER_ENABLED=true`.

---

## Project Structure
```
Backend/
├── main.py                   # FastAPI app entry
├── requirements.txt          # Python dependencies
├── alembic.ini               # Alembic configuration (url set via env in env.py)
├── alembic/                  # Migration environment and versions
├── app/
│   ├── core/                 # Settings (env-driven)
│   ├── api/                  # Routers and endpoints (v1)
│   ├── models/               # SQLAlchemy models
│   ├── schemas/              # Pydantic models
│   ├── services/             # Email, notifications, payments, etc.
│   ├── auth/                 # JWT utils and dependencies
│   └── database.py           # Engine/session helpers
└── uploads/                  # User-uploaded files (ignored by git)
```

---

## Common Tasks
- Create a new migration after model changes
```bash
alembic revision --autogenerate -m "Describe your change"
python -m alembic upgrade head
```

- Run tests (if configured)
```bash
pytest -q
```

---

## Security & Secrets
- Do not commit `.env`, credentials, or API keys. `.gitignore` excludes these.
- GitHub Push Protection can block pushes if secrets are detected. If that happens, rotate secrets and remove them from history (e.g., `git filter-repo --replace-text`).

---

## Deployment Tips
- Set all env vars via your platform (Docker, Render, Fly, Railway, Heroku, etc.).
- Use a managed PostgreSQL instance. Apply migrations on deploy.
- Disable reload in production, set appropriate workers (e.g., `uvicorn --workers 2`).
- Ensure `EMAIL_SCHEDULER_ENABLED` reflects your needs in production.

---

## Troubleshooting
- Database connection errors: verify `DATABASE_URL` and network access.
- CORS issues: confirm exact origins in `ALLOWED_ORIGINS`.
- Emails not sending: check SMTP creds, port (`465` for SSL) and provider app passwords.
- Migrations not applying: confirm Alembic `env.py` reads `DATABASE_URL` from env.

---

## Branding
This backend is part of the LibraryConnekto platform.

