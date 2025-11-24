# 📚 LibraryConnekto Backend

**LibraryConnekto Backend** is a production-ready backend system designed to power a smart library and student workspace platform. It includes authentication, student management, admin features, seat booking, payments, notifications, and more.

## 🚀 Features

*   **Authentication:** JWT Authentication (Admin + Student)
*   **Student Management:** Student profiles, attendance, tasks, exams
*   **Admin:** Admin dashboard APIs
*   **Booking:** Seat booking system
*   **Growth:** Referral system
*   **Payments:** Razorpay payments integration
*   **Notifications:** Email notifications
*   **Automation:** Scheduler-based automated jobs
*   **Tech:** PostgreSQL + SQLAlchemy + Alembic
*   **DevOps:** Docker + Cloud Run deployment

## 🛠️ Tech Stack

| Category | Tools |
| :--- | :--- |
| **Framework** | FastAPI |
| **Database** | PostgreSQL |
| **ORM** | SQLAlchemy |
| **Migrations** | Alembic |
| **Payments** | Razorpay |
| **Deployment** | Docker, Google Cloud Run |
| **Authentication** | Python-Jose, Passlib |

## 📁 Project Structure

```text
Backend/
├── main.py
├── app/
│   ├── api/                # API routers
│   ├── auth/               # JWT utilities
│   ├── core/               # Config & environment settings
│   ├── models/             # SQLAlchemy models
│   ├── schemas/            # Pydantic schemas
│   ├── services/           # Email, payments, notifications
│   └── database.py         # DB session & engine
├── alembic/                # Migration scripts
├── alembic.ini
├── requirements.txt
├── Dockerfile
├── entrypoint.sh
├── deploy-cloudrun.sh
├── deploy-cloudrun.ps1
├── cloudbuild.yaml
├── environment.template
└── uploads/                # Static uploads (ignored by Git)
⚙️ Setup Instructions
1. Install dependencies
code
Bash
download
content_copy
expand_less
pip install -r requirements.txt
2. Setup environment

Create a .env file in the root directory:

code
Ini
download
content_copy
expand_less
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME

SECRET_KEY=your-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

ALLOWED_ORIGINS=http://localhost:3000

UPLOAD_DIR=uploads
MAX_FILE_SIZE=10485760

SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=
SMTP_PASSWORD=

RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=

EMAIL_SCHEDULER_ENABLED=true
SCHEDULER_INITIAL_DELAY_SECONDS=60
SCHEDULER_LOOP_INTERVAL_SECONDS=60
SUBSCRIPTION_CHECKS_DAILY_ENABLED=true
SUBSCRIPTION_EMAIL_FROM_SCHEDULER_ENABLED=false
3. Run database migrations

download
content_copy
expand_less
alembic upgrade head
4. Start the server

download
content_copy
expand_less
uvicorn main:app --reload

Access the application:

API Docs: http://localhost:8000/docs

Health Check: http://localhost:8000/health

🐳 Docker (Optional)

Build the image:
download
content_copy
expand_less
docker build -t libraryconnekto-backend .

Run the container:

download
content_copy
expand_less
docker run -p 8080:8080 --env-file .env libraryconnekto-backend
☁️ Deploy to Google Cloud Run

Linux/Mac:

download
content_copy
expand_less
./deploy-cloudrun.sh

Windows:

download
content_copy
expand_less
.\deploy-cloudrun.ps1 -ProjectId <ID> -Region <REGION> -Service <NAME>

download
content_copy
expand_less
