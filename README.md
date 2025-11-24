📚 LibraryConnekto Backend

LibraryConnekto Backend is a production-ready backend system designed to power a smart library and student workspace platform. It includes authentication, student management, admin features, seat booking, payments, notifications, and more.

🚀 Features

JWT Authentication (Admin + Student)

Student profiles, attendance, tasks, exams

Admin dashboard APIs

Seat booking system

Referral system

Razorpay payments

Email notifications

Scheduler-based automated jobs

PostgreSQL + SQLAlchemy + Alembic

Docker + Cloud Run deployment

🛠️ Tech Stack
Category	Tools
Framework	FastAPI
Database	PostgreSQL
ORM	SQLAlchemy
Migrations	Alembic
Payments	Razorpay
Deployment	Docker, Google Cloud Run
Authentication	Python-Jose, Passlib
📁 Project Structure (GitHub-Optimized)

✅ This block will display perfectly formatted when pasted into GitHub.

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
🔧 Install dependencies
pip install -r requirements.txt

🔧 Setup environment

Create .env file:

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

🔧 Run database migrations
alembic upgrade head

🚀 Start the server
uvicorn main:app --reload


Open:

API Docs → http://localhost:8000/docs

Health Check → http://localhost:8000/health

🐳 Docker (Optional)
docker build -t libraryconnekto-backend .
docker run -p 8080:8080 --env-file .env libraryconnekto-backend

☁️ Deploy to Google Cloud Run
./deploy-cloudrun.sh


Windows:

.\deploy-cloudrun.ps1 -ProjectId <ID> -Region <REGION> -Service <NAME>

