#!/usr/bin/env python3
"""
Setup script for FastAPI Library Management System Backend
"""

import os
import sys
import subprocess
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def run_command(command, description):
    """Run a shell command and handle errors"""
    print(f"\n{description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def check_postgresql():
    """Check if PostgreSQL is installed and running"""
    print("\nChecking PostgreSQL...")
    try:
        result = subprocess.run("psql --version", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ PostgreSQL found: {result.stdout.strip()}")
            return True
        else:
            print("❌ PostgreSQL not found")
            return False
    except Exception as e:
        print(f"❌ Error checking PostgreSQL: {e}")
        return False

def create_database():
    """Check database connection using env DATABASE_URL (no hardcoded secrets)."""
    print("\nChecking database connection...")
    try:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            print("❌ DATABASE_URL not set. Skipping DB connection test.")
            return False
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Connected to PostgreSQL: {version[0]}")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        print("Please check your DATABASE_URL in the environment")
        return False

def install_dependencies():
    """Install Python dependencies"""
    return run_command("pip install -r requirements.txt", "Installing Python dependencies")

def setup_alembic():
    """Initialize Alembic if not already done"""
    if not os.path.exists("alembic/versions"):
        return run_command("alembic init alembic", "Initializing Alembic")
    else:
        print("✅ Alembic already initialized")
        return True

def create_migration():
    """Create initial migration"""
    return run_command("alembic revision --autogenerate -m 'Initial migration'", "Creating initial migration")

def run_migrations():
    """Run database migrations"""
    return run_command("alembic upgrade head", "Running database migrations")

def test_server():
    """Test if the server can start"""
    print("\nTesting server startup...")
    try:
        # Import the app to check for any import errors
        from main import app
        print("✅ Server imports successfully")
        return True
    except Exception as e:
        print(f"❌ Server import failed: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 Setting up FastAPI Library Management System Backend")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not os.path.exists("main.py"):
        print("❌ Please run this script from the Backend directory")
        sys.exit(1)
    
    success = True
    
    # Step 1: Check PostgreSQL (generic)
    check_postgresql()
    
    # Step 2: Install dependencies
    if not install_dependencies():
        success = False
    
    # Step 3: Test database connection
    if success and not create_database():
        success = False
    
    # Step 4: Setup Alembic
    if success and not setup_alembic():
        success = False
    
    # Step 5: Create migration
    if success and not create_migration():
        success = False
    
    # Step 6: Run migrations
    if success and not run_migrations():
        success = False
    
    # Step 7: Test server
    if success and not test_server():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 Setup completed successfully!")
        print("\nTo start the server, run:")
        print("   uvicorn main:app --reload --host 0.0.0.0 --port 8000")
        print("\nAPI documentation will be available at:")
        print("   http://localhost:8000/docs")
    else:
        print("❌ Setup failed. Please check the errors above and try again.")
        sys.exit(1)

if __name__ == "__main__":
    main()
