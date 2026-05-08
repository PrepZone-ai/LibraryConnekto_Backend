# LibraryConnekto Backend

**LibraryConnekto Backend** powers the Library Connekto platform with authentication, student/admin management, seat booking, payments, notifications, and automation.

## Features

*   **Authentication:** JWT for Admin + Student
*   **Student Management:** Profiles, attendance, tasks, exams
*   **Admin:** Dashboard and management APIs
*   **Booking:** Seat booking flows
*   **Payments:** Razorpay integration + webhooks
*   **Messaging:** Email notifications and delivery logs
*   **Automation:** Scheduler-driven notifications and checks
*   **Transfers:** QR transfer flows and seat reuse
*   **Tech:** PostgreSQL + SQLAlchemy + Alembic
*   **DevOps:** Docker + Cloud Run deployment

## Tech Stack

| Category | Tools |
| :--- | :--- |
| **Framework** | FastAPI |
| **Database** | PostgreSQL |
| **ORM** | SQLAlchemy |
| **Migrations** | Alembic |
| **Payments** | Razorpay |
| **Deployment** | Docker, Google Cloud Run |
| **Authentication** | Python-Jose, Passlib |

## Project Structure

```text
LibraryConnekto_Backend/
├── main.py
├── app/
│   ├── api/                # API routers
│   ├── auth/               # JWT utilities
│   ├── core/               # Config, logging, cache, sentry
│   ├── middleware/         # Security and rate limiting
│   ├── models/             # SQLAlchemy models
│   ├── schemas/            # Pydantic schemas
│   ├── services/           # Email, payments, notifications, transfers
│   ├── tasks/              # Background jobs
│   ├── utils/              # Shared utilities
│   ├── celery_app.py
│   └── database.py         # DB session & engine
├── alembic/                # Migration scripts
├── alembic.ini
├── requirements.txt
├── Dockerfile
├── entrypoint.sh
├── deploy-cloudrun.sh
├── deploy-cloudrun.ps1
├── cloudbuild.yaml
└── uploads/                # Static uploads (ignored by Git)
```

## Setup Instructions

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Configure environment

Create a `.env` file in the root directory. For the full list of settings, see [app/core/config.py](LibraryConnekto_Backend/app/core/config.py).

```ini
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME

SECRET_KEY=your-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

ALLOWED_ORIGINS=http://localhost:3000

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=
SMTP_PASSWORD=

RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
```

### 3) Run database migrations

```bash
alembic upgrade head
```

### 4) Start the server

```bash
uvicorn main:app --reload
```

API Docs: http://localhost:8000/docs

Health Check: http://localhost:8000/health

## Docker (Optional)

```bash
docker build -t libraryconnekto-backend .
docker run -p 8080:8080 --env-file .env libraryconnekto-backend
```

## Deploy to Google Cloud Run

Linux/Mac:

```bash
./deploy-cloudrun.sh
```

Windows:

```powershell
.\deploy-cloudrun.ps1 -ProjectId <ID> -Region <REGION> -Service <NAME>
```
