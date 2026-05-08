# Archived: Google Cloud Run deployment files

These files (`cloudbuild.yaml`, `deploy-cloudrun.ps1`, `deploy-cloudrun.sh`) were
the previous deployment path targeting **Google Cloud Run**. They are kept here
for reference only and are not used by any active CI/CD pipeline.

The active deployment target is **AWS** (EC2 + RDS + Redis + Nginx + S3 +
CloudFront + Route 53). See:

- `../../AWS_Deploy.md` — full AWS deployment guide.
- `../aws/` — systemd unit files, Nginx config, and EC2 bootstrap script.
- `../../.github/workflows/deploy-backend.yml` — AWS EC2 SSH deploy workflow.

If you ever need to revive the Cloud Run path, move these files back to the
backend root and restore the GCP-flavored `.github/workflows/deploy-backend.yml`
from git history.
