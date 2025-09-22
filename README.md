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
├── uploads/                  # User-uploaded files (ignored by git)
├── Dockerfile                # Container image (Cloud Run ready)
├── .dockerignore             # Build context excludes
├── entrypoint.sh             # Runs Alembic migrations, starts Uvicorn
├── deploy-cloudrun.sh        # Bash helper to build & deploy to Cloud Run
├── deploy-cloudrun.ps1       # PowerShell helper to build & deploy to Cloud Run
└── cloudbuild.yaml           # Optional Cloud Build CI to Cloud Run
```

---

## Docker (local)

Build and run locally:
```bash
# from Backend/
docker build -t libraryconnekto-backend:dev .
docker run --rm -p 8080:8080 \
  -e DATABASE_URL="postgresql://USER:PASSWORD@HOST:5432/DB" \
  -e SECRET_KEY=change-me -e JWT_ALGORITHM=HS256 -e ACCESS_TOKEN_EXPIRE_MINUTES=30 \
  -e ALLOWED_ORIGINS=http://localhost:3000 \
  libraryconnekto-backend:dev
```
Health: `http://localhost:8080/health`  |  Docs: `http://localhost:8080/docs`

---

## Deploy to Google Cloud Run

Prereqs:
- `gcloud` CLI installed and authenticated (`gcloud auth login`)
- Enable required APIs: `gcloud services enable run.googleapis.com cloudbuild.googleapis.com`
- A reachable PostgreSQL and its `DATABASE_URL`

Option A — One command (bash):
```bash
# from Backend/
./deploy-cloudrun.sh <PROJECT_ID> <REGION> <SERVICE_NAME>
# then set required env vars (examples are commented in the script)
```

Option B — PowerShell (Windows):
```powershell
# from Backend\
./deploy-cloudrun.ps1 -ProjectId <PROJECT_ID> -Region <REGION> -Service <SERVICE_NAME>
```

Option C — Cloud Build CI:
```bash
# from Backend/
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_SERVICE=<SERVICE>,_REGION=<REGION>,_IMAGE=gcr.io/$PROJECT_ID/<SERVICE>
```

Notes:
- Cloud Run passes `$PORT` to the container; `entrypoint.sh` runs Alembic then Uvicorn.
- Provide env vars with `--set-env-vars` or Secret Manager (`--set-secrets`).
- For database connectivity from Cloud Run to Cloud SQL, add Cloud SQL connector flags as needed.

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
- Do not commit `.env`, credentials, or API keys. `.dockerignore` excludes them.
- Prefer Secret Manager for production secrets. Use `--set-secrets` with Cloud Run.

---

## Troubleshooting
- Database connection errors: verify `DATABASE_URL` and network/connector configuration.
- 403 on Cloud Run: disable `--allow-unauthenticated` or configure IAM as needed.
- Cold starts: consider minimum instances if needed.

---

## Branding
This backend is part of the LibraryConnekto platform.

