@echo off
REM LibraryConnekto Backend - Local Development Setup Script for Windows
REM This script helps set up the local development environment on Windows

echo 🚀 Setting up LibraryConnekto Backend for Local Development (Windows)

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed. Please install Python 3.11 or later.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [INFO] Python version:
python --version

REM Check if pip is installed
pip --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] pip is not installed. Please install pip.
    pause
    exit /b 1
)

REM Step 1: Create virtual environment
echo [STEP] 1. Creating Python virtual environment...
if not exist "venv" (
    python -m venv venv
    echo [INFO] Virtual environment created!
) else (
    echo [WARNING] Virtual environment already exists
)

REM Step 2: Activate virtual environment and install dependencies
echo [STEP] 2. Installing Python dependencies...
call venv\Scripts\activate.bat
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)

python -m pip install --upgrade pip
pip install -r requirements.txt
echo [INFO] Dependencies installed!

REM Step 3: Setup environment file
echo [STEP] 3. Setting up environment configuration...
if not exist ".env" (
    copy local.env.template .env
    echo [INFO] Environment file created from template!
    echo [WARNING] Please edit .env file with your local database credentials
) else (
    echo [WARNING] .env file already exists
)

REM Step 4: Create uploads directory
echo [STEP] 4. Creating uploads directory...
if not exist "uploads" mkdir uploads
if not exist "uploads\profile_images" mkdir uploads\profile_images
echo [INFO] Upload directories created!

REM Step 5: Database setup instructions
echo [STEP] 5. Database setup instructions...
echo [INFO] To set up your local database:
echo 1. Install PostgreSQL from: https://www.postgresql.org/download/windows/
echo 2. Start PostgreSQL service
echo 3. Open Command Prompt as Administrator and run:
echo    psql -U postgres
echo    CREATE DATABASE libraryconnekto_local;
echo    CREATE USER libraryconnekto_user WITH PASSWORD 'your_password';
echo    GRANT ALL PRIVILEGES ON DATABASE libraryconnekto_local TO libraryconnekto_user;
echo    \q
echo.
echo 4. Update DATABASE_URL in .env file:
echo    DATABASE_URL=postgresql://libraryconnekto_user:your_password@localhost:5432/libraryconnekto_local

REM Step 6: Run migrations
echo [STEP] 6. Database migrations...
if exist ".env" (
    echo [INFO] Running database migrations...
    python -m alembic upgrade head
    if %ERRORLEVEL% neq 0 (
        echo [WARNING] Migration failed. Please check your database connection in .env file
    )
) else (
    echo [WARNING] Please create .env file first, then run: python -m alembic upgrade head
)

echo.
echo 🎉 Local development setup completed!
echo.
echo Next steps:
echo 1. Edit .env file with your database credentials
echo 2. Set up PostgreSQL database (see instructions above)
echo 3. Run migrations: python -m alembic upgrade head
echo 4. Start the development server:
echo    venv\Scripts\activate.bat
echo    uvicorn main:app --reload --host 0.0.0.0 --port 8000
echo.
echo The API will be available at:
echo   - Health Check: http://localhost:8000/health
echo   - API Docs: http://localhost:8000/docs
echo   - Alternative Docs: http://localhost:8000/redoc
echo.
echo For production deployment, see DEPLOYMENT_GUIDE.md

pause
