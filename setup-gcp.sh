#!/bin/bash

# LibraryConnekto Backend - Google Cloud Setup Script
# This script helps set up the necessary Google Cloud resources
# Project: kabaddiguru (324578194548)

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    print_error "gcloud CLI is not installed. Please install it first:"
    print_error "https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Set project details
PROJECT_ID="kabaddiguru"
REGION="us-central1"

# Allow override via command line arguments
if [ $# -gt 0 ]; then
    PROJECT_ID="$1"
fi
if [ $# -gt 1 ]; then
    REGION="$2"
fi

print_status "Setting up LibraryConnekto Backend on Google Cloud"
print_status "Project ID: $PROJECT_ID"
print_status "Region: $REGION"

# Set the project
print_status "Setting gcloud project..."
gcloud config set project "$PROJECT_ID"

# Enable required APIs
print_status "Enabling required APIs..."
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable sqladmin.googleapis.com

print_status "APIs enabled successfully!"

# Create Artifact Registry repository
print_status "Creating Artifact Registry repository..."
if gcloud artifacts repositories describe libraryconnekto-backend --location="$REGION" &> /dev/null; then
    print_warning "Artifact Registry repository already exists"
else
    gcloud artifacts repositories create libraryconnekto-backend \
        --repository-format=docker \
        --location="$REGION" \
        --description="LibraryConnekto Backend Docker images"
    print_status "Artifact Registry repository created!"
fi

# Create Cloud SQL instance
print_status "Creating Cloud SQL instance..."
if gcloud sql instances describe libraryconnekto-db &> /dev/null; then
    print_warning "Cloud SQL instance already exists"
else
    gcloud sql instances create libraryconnekto-db \
        --database-version=POSTGRES_14 \
        --tier=db-f1-micro \
        --region="$REGION" \
        --storage-size=10GB \
        --storage-type=SSD \
        --backup-start-time=02:00
    print_status "Cloud SQL instance created!"
fi

# Create database
print_status "Creating database..."
if gcloud sql databases describe libraryconnekto --instance=libraryconnekto-db &> /dev/null; then
    print_warning "Database already exists"
else
    gcloud sql databases create libraryconnekto --instance=libraryconnekto-db
    print_status "Database created!"
fi

# Create database user
print_status "Creating database user..."
echo "Please enter a secure password for the database user:"
read -s DB_PASSWORD

if gcloud sql users describe libraryconnekto-user --instance=libraryconnekto-db &> /dev/null; then
    print_warning "Database user already exists"
else
    gcloud sql users create libraryconnekto-user \
        --instance=libraryconnekto-db \
        --password="$DB_PASSWORD"
    print_status "Database user created!"
fi

# Create service accounts
print_status "Creating service accounts..."

# Backend runtime service account
if gcloud iam service-accounts describe backend-runtime@${PROJECT_ID}.iam.gserviceaccount.com &> /dev/null; then
    print_warning "Backend runtime service account already exists"
else
    gcloud iam service-accounts create backend-runtime \
        --display-name="Backend Runtime Service Account"
    
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:backend-runtime@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/cloudsql.client"
    
    print_status "Backend runtime service account created!"
fi

# GitHub Actions service account
if gcloud iam service-accounts describe github-actions@${PROJECT_ID}.iam.gserviceaccount.com &> /dev/null; then
    print_warning "GitHub Actions service account already exists"
else
    gcloud iam service-accounts create github-actions \
        --display-name="GitHub Actions Service Account"
    
    # Grant necessary roles
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/run.admin"
    
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/storage.admin"
    
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/artifactregistry.writer"
    
    print_status "GitHub Actions service account created!"
fi

# Create service account key
print_status "Creating service account key..."
KEY_FILE="github-actions-key.json"

if [ -f "$KEY_FILE" ]; then
    print_warning "Service account key file already exists: $KEY_FILE"
else
    gcloud iam service-accounts keys create "$KEY_FILE" \
        --iam-account=github-actions@${PROJECT_ID}.iam.gserviceaccount.com
    print_status "Service account key created: $KEY_FILE"
fi

# Generate DATABASE_URL
DB_URL="postgresql://libraryconnekto-user:${DB_PASSWORD}@/libraryconnekto?host=/cloudsql/${PROJECT_ID}:${REGION}:libraryconnekto-db"
INSTANCE_CONNECTION_NAME="${PROJECT_ID}:${REGION}:libraryconnekto-db"

print_status "Setup completed successfully!"
print_status ""
print_status "Next steps:"
print_status "1. Add the following secrets to your GitHub repository:"
print_status ""
print_status "   GCP_PROJECT_ID: $PROJECT_ID"
print_status "   GCP_REGION: $REGION"
print_status "   GAR_REPOSITORY_BACKEND: libraryconnekto-backend"
print_status "   CLOUD_RUN_SERVICE_BACKEND: libraryconnekto-api"
print_status "   DATABASE_URL: $DB_URL"
print_status "   INSTANCE_CONNECTION_NAME: $INSTANCE_CONNECTION_NAME"
print_status "   GCP_SA_KEY: <contents of $KEY_FILE>"
print_status ""
print_status "2. Generate a SECRET_KEY:"
print_status "   openssl rand -hex 32"
print_status ""
print_status "3. Configure other environment variables as needed"
print_status "4. Push your code to trigger deployment"
print_status ""
print_warning "Important: Keep the $KEY_FILE secure and do not commit it to version control!"

# Cleanup instructions
print_status ""
print_status "To clean up resources later, run:"
print_status "gcloud sql instances delete libraryconnekto-db"
print_status "gcloud artifacts repositories delete libraryconnekto-backend --location=$REGION"
print_status "gcloud iam service-accounts delete backend-runtime@${PROJECT_ID}.iam.gserviceaccount.com"
print_status "gcloud iam service-accounts delete github-actions@${PROJECT_ID}.iam.gserviceaccount.com"
