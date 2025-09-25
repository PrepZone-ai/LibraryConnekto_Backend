#!/bin/bash

# LibraryConnekto Backend - Local Development Setup Script
# This script helps set up the local development environment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_status "🚀 Setting up LibraryConnekto Backend for Local Development"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.11 or later."
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
print_status "Python version: $PYTHON_VERSION"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 is not installed. Please install pip3."
    exit 1
fi

# Step 1: Create virtual environment
print_step "1. Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_status "Virtual environment created!"
else
    print_warning "Virtual environment already exists"
fi

# Step 2: Activate virtual environment and install dependencies
print_step "2. Installing Python dependencies..."
source venv/bin/activate || source venv/Scripts/activate 2>/dev/null || {
    print_error "Failed to activate virtual environment"
    exit 1
}

pip install --upgrade pip
pip install -r requirements.txt
print_status "Dependencies installed!"

# Step 3: Setup environment file
print_step "3. Setting up environment configuration..."
if [ ! -f ".env" ]; then
    cp local.env.template .env
    print_status "Environment file created from template!"
    print_warning "Please edit .env file with your local database credentials"
else
    print_warning ".env file already exists"
fi

# Step 4: Check PostgreSQL
print_step "4. Checking PostgreSQL availability..."
if command -v psql &> /dev/null; then
    print_status "PostgreSQL client found!"
else
    print_warning "PostgreSQL client not found. Please install PostgreSQL:"
    print_warning "  - Windows: Download from https://www.postgresql.org/download/windows/"
    print_warning "  - macOS: brew install postgresql"
    print_warning "  - Ubuntu: sudo apt-get install postgresql postgresql-contrib"
fi

# Step 5: Database setup instructions
print_step "5. Database setup instructions..."
print_status "To set up your local database:"
echo "1. Start PostgreSQL service"
echo "2. Create database and user:"
echo "   psql -U postgres"
echo "   CREATE DATABASE libraryconnekto_local;"
echo "   CREATE USER libraryconnekto_user WITH PASSWORD 'your_password';"
echo "   GRANT ALL PRIVILEGES ON DATABASE libraryconnekto_local TO libraryconnekto_user;"
echo "   \\q"
echo ""
echo "3. Update DATABASE_URL in .env file:"
echo "   DATABASE_URL=postgresql://libraryconnekto_user:your_password@localhost:5432/libraryconnekto_local"

# Step 6: Run migrations
print_step "6. Database migrations..."
if [ -f ".env" ]; then
    print_status "Running database migrations..."
    python -m alembic upgrade head || {
        print_warning "Migration failed. Please check your database connection in .env file"
    }
else
    print_warning "Please create .env file first, then run: python -m alembic upgrade head"
fi

# Step 7: Create uploads directory
print_step "7. Creating uploads directory..."
mkdir -p uploads/profile_images
print_status "Upload directories created!"

print_status ""
print_status "🎉 Local development setup completed!"
print_status ""
print_status "Next steps:"
print_status "1. Edit .env file with your database credentials"
print_status "2. Set up PostgreSQL database (see instructions above)"
print_status "3. Run migrations: python -m alembic upgrade head"
print_status "4. Start the development server:"
print_status "   source venv/bin/activate  # or venv\\Scripts\\activate on Windows"
print_status "   uvicorn main:app --reload --host 0.0.0.0 --port 8000"
print_status ""
print_status "The API will be available at:"
print_status "  - Health Check: http://localhost:8000/health"
print_status "  - API Docs: http://localhost:8000/docs"
print_status "  - Alternative Docs: http://localhost:8000/redoc"
print_status ""
print_status "For production deployment, see DEPLOYMENT_GUIDE.md"
