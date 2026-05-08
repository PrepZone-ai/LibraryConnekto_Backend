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
| **Deployment** | AWS EC2 + Nginx + systemd, RDS PostgreSQL, local Redis, S3 + CloudFront for the frontend |
| **CI/CD** | GitHub Actions (`.github/workflows/deploy-backend.yml`) |
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
├── Dockerfile              # Optional - container image (not used by the AWS path)
├── entrypoint.sh           # Used inside Docker / when running via container
├── test_db_connection.py   # DB-readiness probe consumed by entrypoint.sh
├── deploy/aws/             # AWS deployment kit (systemd, nginx, scripts)
│   ├── systemd/            # FastAPI / Celery worker / Celery beat unit files
│   ├── nginx/              # Reverse-proxy config for api.<domain>
│   └── scripts/            # 01-provision-aws.ps1 + ec2-bootstrap.sh
├── deploy/_archive_gcp/    # Old Cloud Run files (kept for reference only)
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

## Deploy to AWS

**Account reference:** [deploy/aws/AWS_ACCOUNT.md](deploy/aws/AWS_ACCOUNT.md) (ID `836809166355`, region `ap-south-1`).

The full step-by-step guide lives in [`../AWS_Deploy.md`](../AWS_Deploy.md).
It deploys this backend to AWS EC2 (Mumbai region `ap-south-1`) with RDS
PostgreSQL, local Redis on the instance, Celery worker + beat, Nginx + Let's
Encrypt SSL, and the React frontend on S3 + CloudFront + Route 53.

Two scripts automate the bulk of the work:

```powershell
# 1. From your Windows machine — provisions all AWS resources.
cd LibraryConnekto_Backend\deploy\aws\scripts
$pw = Read-Host "RDS password" -AsSecureString
.\01-provision-aws.ps1 -Region ap-south-1 -Domain libraryconnekto.me -DbPassword $pw -InstanceType t3.micro
```

```bash
# 2. SSH into the new EC2 instance, then bootstrap the application stack.
ssh -i libraryconnekto-key.pem ubuntu@<elastic-ip>
curl -fsSL https://raw.githubusercontent.com/PrepZone-ai/LibraryConnekto_Backend/main/deploy/aws/scripts/ec2-bootstrap.sh -o bootstrap.sh
chmod +x bootstrap.sh
./bootstrap.sh
```

CI/CD: pushes to `main` automatically deploy via
`.github/workflows/deploy-backend.yml` (SSH into EC2, pull, restart services).
Required GitHub repository secrets:

| Secret | Description |
| --- | --- |
| `EC2_HOST` | Elastic IP of the EC2 instance |
| `EC2_SSH_KEY` | Contents of `libraryconnekto-key.pem` |
