# 📚 LibraryConnekto Backend

LibraryConnekto Backend is a production-ready server built using **FastAPI**, **PostgreSQL**, **SQLAlchemy**, and **Alembic**, designed to support a smart library management and student workspace system.  
It provides secure authentication, student/admin workflows, notifications, seat booking, subscriptions, and more.

---

## 🚀 Features

- 🔐 **JWT Authentication** (Admin & Student)  
- 🪑 **Seat Booking System**  
- 👨‍🎓 **Student Management APIs**  
- 🧑‍💼 **Admin Management APIs**  
- 📨 **Notification & Messaging System**  
- 💳 **Payment Integration (Razorpay)**  
- 📂 **File Upload Support**  
- 🕒 **Background Scheduler for Subscription Checks**  
- 🐳 **Docker & Cloud Run Deployment Ready**

---

## 🧱 Project Structure

Backend/
├── main.py
├── requirements.txt
├── alembic.ini
├── alembic/
├── app/
│ ├── api/
│ ├── auth/
│ ├── core/
│ ├── database.py
│ ├── models/
│ ├── schemas/
│ └── services/
├── uploads/
├── Dockerfile
├── entrypoint.sh
├── deploy-cloudrun.sh
├── deploy-cloudrun.ps1
├── cloudbuild.yaml
├── environment.template
└── local.env.template

yaml
Copy code

---

## ⚙️ Setup (Local Development)

### 1️⃣ Clone Repository
```bash
git clone https://github.com/PrepZone-ai/LibraryConnekto_Backend.git
cd LibraryConnekto_Backend
2️⃣ Install Dependencies
bash
Copy code
pip install -r requirements.txt
3️⃣ Create Environment File
Rename environment.template → .env and fill in:

env
Copy code
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/DB_NAME

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
4️⃣ Run Database Migrations
bash
Copy code
alembic upgrade head
5️⃣ Start Server
bash
Copy code
uvicorn main:app --reload
📌 Docs: http://localhost:8000/docs
📌 Health Check: http://localhost:8000/health

🐳 Run with Docker
Build Image
bash
Copy code
docker build -t libraryconnekto-backend .
Run Container
bash
Copy code
docker run -p 8080:8080 \
  -e DATABASE_URL="postgresql://USER:PASSWORD@HOST:5432/DB" \
  -e SECRET_KEY="your-secret" \
  libraryconnekto-backend
API Docs → http://localhost:8080/docs
Health → http://localhost:8080/health

☁️ Deploy to Google Cloud Run
Option A: Linux/macOS
bash
Copy code
./deploy-cloudrun.sh
Option B: Windows PowerShell
powershell
Copy code
.\deploy-cloudrun.ps1 -ProjectId <PROJECT_ID> -Region <REGION> -Service <SERVICE_NAME>
Option C: Cloud Build
bash
Copy code
gcloud builds submit --config cloudbuild.yaml
🔧 Common Developer Commands
Create Migration
bash
Copy code
alembic revision --autogenerate -m "message"
Apply Migration
bash
Copy code
alembic upgrade head
Run Tests
bash
Copy code
pytest
🔐 Security Notes
Never commit .env files or secrets

Use Google Secret Manager or environment variables for production

Rotate JWT keys regularly

🧩 Contribution Guidelines
Fork the repo

Create a new branch:

bash
Copy code
git checkout -b feature/my-feature
Commit changes

Push the branch and open a Pull Request

📄 License
Add your license file (MIT recommended) or update this section.

✨ About
LibraryConnekto Backend powers the entire ecosystem of student management, seat booking, notifications, and admin workflows.
Clean architecture, fully modular, and optimized for scale.
