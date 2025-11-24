📚 LibraryConnekto Backend

LibraryConnekto Backend is a production-ready backend system designed to power a smart library and student-workspace management platform.
It provides robust APIs for authentication, student management, admin operations, attendance tracking, seat booking, referrals, payments, notifications, and more.

Built with FastAPI, PostgreSQL, SQLAlchemy, Alembic, and fully deployable on Google Cloud Run.

🚀 Features
🔐 Authentication

JWT-based secure authentication

Role-based access: Admin and Student

Password hashing (bcrypt)

👨‍🎓 Student & Admin Operations

Student profile CRUD

Admin dashboard endpoints

Attendance management

Task & exam record management

Messaging system

🪑 Seat Booking System

Anonymous + authenticated seat booking

Session-based seat tracking

🎁 Referral & Offers

Referral-code generation

Referral validation

Bonus & discount logic

💳 Payments

Razorpay integration

Subscription tracking

Automated payment validation

📨 Notifications

Email notifications (SMTP)

Scheduled background jobs

Daily subscription checks

Automated reminders

🗄️ Database & Deployment

SQLAlchemy ORM (sync)

Alembic migrations

Docker + Cloud Run deployment scripts

Environment-based configuration

🛠️ Tech Stack
Category	Tools / Libraries
Framework	FastAPI
ORM / DB	SQLAlchemy, PostgreSQL
Migrations	Alembic
Auth	Python-Jose, Passlib
Payments	Razorpay
Email	SMTP
Deployment	Docker, Google Cloud Run
Background Jobs	In-app scheduler
📁 Project Structure
Backend/
├── main.py                  # FastAPI entrypoint
├── app/
│   ├── api/                 # API routes
│   ├── auth/                # JWT utilities
│   ├── core/                # Configuration & settings
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── services/            # Mail, payments, notifications
│   └── database.py          # DB session & engine
├── alembic/                 # Migration repository
├── alembic.ini
├── requirements.txt
├── Dockerfile
├── entrypoint.sh
├── deploy-cloudrun.sh
├── deploy-cloudrun.ps1
├── cloudbuild.yaml
├── environment.template
└── uploads/                 # File uploads (ignored)

⚙️ Local Setup
1️⃣ Clone the repository
git clone https://github.com/PrepZone-ai/LibraryConnekto_Backend
cd LibraryConnekto_Backend

2️⃣ Create virtual environment
python -m venv venv
source venv/bin/activate     # Linux/Mac
venv\Scripts\activate        # Windows

3️⃣ Install dependencies
pip install -r requirements.txt

4️⃣ Setup environment variables

Create .env file:

DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME

SECRET_KEY=your-secret-key
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

5️⃣ Run database migrations
alembic upgrade head

6️⃣ Start the server
uvicorn main:app --reload


API will run at:
👉 http://localhost:8000

👉 Swagger docs: http://localhost:8000/docs

🐳 Docker Setup
Build the image
docker build -t libraryconnekto-backend .

Run container
docker run -p 8080:8080 --env-file .env libraryconnekto-backend


Then open:

API: http://localhost:8080

Docs: http://localhost:8080/docs

☁️ Deploy to Google Cloud Run
Requirements

✔ Google Cloud CLI
✔ Billing Enabled
✔ Cloud Build enabled
✔ Artifact Registry enabled

Deploy using script
./deploy-cloudrun.sh

Deploy using PowerShell (Windows)
.\deploy-cloudrun.ps1 -ProjectId <PROJECT_ID> -Region <REGION> -Service <SERVICE_NAME>

Deploy manually
gcloud builds submit --tag gcr.io/PROJECT_ID/libraryconnekto
gcloud run deploy libraryconnekto \
  --image gcr.io/PROJECT_ID/libraryconnekto \
  --region REGION \
  --platform managed \
  --allow-unauthenticated

🔧 Common Developer Commands
Create migration
alembic revision --autogenerate -m "message"

Apply migrations
alembic upgrade head

Run tests (if added)
pytest

🔐 Security Notes

Never commit .env files

Use Google Secret Manager for production keys

Always rotate API keys periodically

Use HTTPS in all deployments


❤️ Acknowledgments

Thanks to all the contributors who helped build LibraryConnekto Backend.
This system is designed to make libraries smarter, faster, and automated for students.
