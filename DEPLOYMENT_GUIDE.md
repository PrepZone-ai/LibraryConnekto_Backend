# LibraryConnekto Backend - Google Cloud Deployment Guide

This guide walks you through deploying the LibraryConnekto Backend to Google Cloud Run using GitHub Actions CI/CD.

**Your Project Details:**
- Project ID: `kabaddiguru`
- Project Number: `324578194548`
- Region: `us-central1`
- Database Instance: `kabaddiguru:us-central1:lb4321`
- Database IP: `35.226.85.141:5432`

## Prerequisites

1. Google Cloud Project `kabaddiguru` with billing enabled ✅
2. GitHub repository with the LibraryConnekto_Backend code
3. Basic knowledge of Google Cloud Console and GitHub

## Step 1: Google Cloud Setup

### 1.1 Enable Required APIs

```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable sqladmin.googleapis.com
```

### 1.2 Create Artifact Registry Repository

```bash
# Set your project
gcloud config set project kabaddiguru

gcloud artifacts repositories create libraryconnekto-backend \
    --repository-format=docker \
    --location=us-central1 \
    --description="LibraryConnekto Backend Docker images"
```

### 1.3 Database Setup (Already Created ✅)

Your Cloud SQL instance is already set up:
- **Instance Name**: `lb4321`
- **Connection Name**: `kabaddiguru:us-central1:lb4321`
- **Public IP**: `35.226.85.141`
- **Port**: `5432`

### 1.4 Create Database and User

Connect to your existing PostgreSQL instance and create the application database:

```bash
# Connect to your existing instance
gcloud sql connect lb4321 --user=postgres --quiet

# Or connect directly via psql if you have the client installed
psql -h 35.226.85.141 -U postgres -d postgres
```

Then run these SQL commands:
```sql
-- Create database for the application
CREATE DATABASE libraryconnekto;

-- Create user for the application
CREATE USER libraryconnekto_user WITH PASSWORD 'YOUR_SECURE_PASSWORD';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE libraryconnekto TO libraryconnekto_user;
GRANT ALL ON SCHEMA public TO libraryconnekto_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO libraryconnekto_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO libraryconnekto_user;

-- Exit
\q
```

### 1.5 Create Service Accounts

#### Backend Runtime Service Account
```bash
gcloud iam service-accounts create backend-runtime \
    --display-name="Backend Runtime Service Account" \
    --project=kabaddiguru

# Grant Cloud SQL Client role
gcloud projects add-iam-policy-binding kabaddiguru \
    --member="serviceAccount:backend-runtime@kabaddiguru.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"
```

#### GitHub Actions Service Account
```bash
gcloud iam service-accounts create github-actions \
    --display-name="GitHub Actions Service Account" \
    --project=kabaddiguru

# Grant necessary roles
gcloud projects add-iam-policy-binding kabaddiguru \
    --member="serviceAccount:github-actions@kabaddiguru.iam.gserviceaccount.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding kabaddiguru \
    --member="serviceAccount:github-actions@kabaddiguru.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding kabaddiguru \
    --member="serviceAccount:github-actions@kabaddiguru.iam.gserviceaccount.com" \
    --role="roles/artifactregistry.writer"

# Create and download key
gcloud iam service-accounts keys create github-actions-key.json \
    --iam-account=github-actions@kabaddiguru.iam.gserviceaccount.com
```

## Step 2: GitHub Repository Secrets

Navigate to your GitHub repository → Settings → Secrets and variables → Actions

Add the following secrets:

### Google Cloud Configuration (Pre-configured)
- `GCP_PROJECT_ID`: `kabaddiguru` ✅ (already set in workflow)
- `GCP_REGION`: `us-central1` ✅ (already set in workflow)
- `GCP_SA_KEY`: Contents of the `github-actions-key.json` file (you need to add this)

### Database Configuration
- `DATABASE_URL`: `postgresql://libraryconnekto_user:YOUR_PASSWORD@/libraryconnekto?host=/cloudsql/kabaddiguru:us-central1:lb4321`
- `DATABASE_URL_PUBLIC` (for testing): `postgresql://libraryconnekto_user:YOUR_PASSWORD@35.226.85.141:5432/libraryconnekto`

### Application Configuration
- `SECRET_KEY`: Generate a strong secret key (use `openssl rand -hex 32`)
- `JWT_ALGORITHM`: `HS256`
- `ACCESS_TOKEN_EXPIRE_MINUTES`: `30`
- `ALLOWED_ORIGINS`: `https://your-frontend-domain.com,http://localhost:3000`
- `UPLOAD_DIR`: `uploads`
- `MAX_FILE_SIZE`: `10485760`

### Email Configuration (Optional)
- `SMTP_HOST`: `smtp.gmail.com`
- `SMTP_PORT`: `465`
- `SMTP_USERNAME`: Your Gmail address
- `SMTP_PASSWORD`: Your Gmail App Password

### Payment Configuration (Optional)
- `RAZORPAY_KEY_ID`: Your Razorpay Key ID
- `RAZORPAY_KEY_SECRET`: Your Razorpay Key Secret

### Scheduler Configuration
- `EMAIL_SCHEDULER_ENABLED`: `true`
- `SCHEDULER_INITIAL_DELAY_SECONDS`: `60`
- `SCHEDULER_LOOP_INTERVAL_SECONDS`: `60`
- `SUBSCRIPTION_CHECKS_DAILY_ENABLED`: `true`
- `SUBSCRIPTION_EMAIL_FROM_SCHEDULER_ENABLED`: `false`

## Step 3: Project Structure Verification

Ensure your repository structure looks like this:

```
your-repo/
├── LibraryConnekto_Backend/
│   ├── .github/
│   │   └── workflows/
│   │       └── deploy-backend.yml
│   ├── app/
│   ├── alembic/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── requirements.txt
│   ├── main.py
│   ├── alembic.ini
│   └── environment.template
```

## Step 4: Local Testing (Optional)

Before deploying, test locally:

```bash
cd LibraryConnekto_Backend

# Copy environment template
cp environment.template .env

# Edit .env with your local values
# Make sure to set DATABASE_URL to your local PostgreSQL

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Step 5: Deploy

### Automatic Deployment
Push your code to the main branch:

```bash
git add .
git commit -m "Deploy LibraryConnekto Backend"
git push origin main
```

The GitHub Actions workflow will automatically:
1. Build the Docker image
2. Push to Artifact Registry
3. Deploy to Cloud Run
4. Run database migrations
5. Test the deployment

### Manual Deployment (Alternative)
You can also deploy manually using the provided scripts:

```bash
cd LibraryConnekto_Backend
./deploy-cloudrun.sh YOUR_PROJECT_ID asia-south1 libraryconnekto-api
```

## Step 6: Verify Deployment

1. Check the GitHub Actions workflow logs
2. Visit the Cloud Run service URL
3. Test the health endpoint: `https://your-service-url/health`
4. Test the API docs: `https://your-service-url/docs`

## Step 7: Domain Setup (Optional)

To use a custom domain:

```bash
gcloud run domain-mappings create \
    --service=libraryconnekto-api \
    --domain=api.yourdomain.com \
    --region=asia-south1
```

## Troubleshooting

### Common Issues

1. **Migration Failures**: Check database connectivity and permissions
2. **Memory Issues**: Increase Cloud Run memory allocation
3. **Cold Starts**: Set minimum instances to 1 for production
4. **CORS Issues**: Verify `ALLOWED_ORIGINS` includes your frontend domain

### Monitoring

1. **Cloud Run Logs**: 
   ```bash
   gcloud logs read --service=libraryconnekto-api
   ```

2. **Cloud SQL Logs**:
   ```bash
   gcloud sql operations list --instance=libraryconnekto-db
   ```

### Performance Optimization

For production workloads, consider:

1. **Increase Resources**:
   ```bash
   --cpu=2 --memory=4Gi
   ```

2. **Set Minimum Instances**:
   ```bash
   --min-instances=1
   ```

3. **Configure Concurrency**:
   ```bash
   --concurrency=100
   ```

## Security Considerations

1. Use Secret Manager for sensitive values
2. Enable VPC connector for database security
3. Implement proper authentication and authorization
4. Regular security updates for dependencies
5. Monitor access logs and set up alerts

## Cost Optimization

1. Use Cloud Run's pay-per-request model
2. Set appropriate timeout values
3. Monitor resource usage and adjust accordingly
4. Use Cloud SQL's automatic backups efficiently

## Next Steps

1. Set up monitoring and alerting
2. Configure SSL certificates for custom domains
3. Implement proper backup strategies
4. Set up staging environment
5. Configure CI/CD for multiple environments

For support, check the [GitHub repository](https://github.com/your-repo) issues or documentation.
