#!/usr/bin/env bash
# =====================================================================
# EC2 first-boot bootstrap for LibraryConnekto backend.
# Run as the `ubuntu` user on a fresh Ubuntu 22.04 instance.
# Reference: AWS_Deploy.md, Sections 6-9
#
# Usage (after SSH into the box):
#   curl -fsSL https://raw.githubusercontent.com/PrepZone-ai/LibraryConnekto_Backend/main/deploy/aws/scripts/ec2-bootstrap.sh -o bootstrap.sh
#   chmod +x bootstrap.sh
#   ./bootstrap.sh
# =====================================================================
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/PrepZone-ai/LibraryConnekto_Backend.git}"
APP_DIR="/home/ubuntu/backend"
LOG_DIR="/home/ubuntu/logs"

echo "==> [1/7] Updating system packages"
sudo apt-get update -y
sudo apt-get upgrade -y

echo "==> [2/7] Installing system dependencies"
sudo apt-get install -y \
  python3.11 python3.11-venv python3.11-dev python3-pip \
  nginx git redis-server certbot python3-certbot-nginx \
  build-essential libpq-dev unzip curl htop

echo "==> [3/7] Ensuring Redis is running"
sudo systemctl enable --now redis-server
redis-cli ping

echo "==> [4/7] Cloning / updating backend repo"
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch --all
  git -C "$APP_DIR" reset --hard origin/main
else
  git clone "$REPO_URL" "$APP_DIR"
fi

mkdir -p "$LOG_DIR"
mkdir -p "$APP_DIR/uploads/profile_images"

echo "==> [5/7] Creating Python venv and installing requirements"
cd "$APP_DIR"
if [[ ! -d venv ]]; then
  python3.11 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt
pip install gunicorn

echo "==> [6/7] Verifying .env exists"
if [[ ! -f "$APP_DIR/.env" ]]; then
  echo
  echo "WARNING: $APP_DIR/.env does not exist."
  echo "  -> Copy .env.aws.example to .env, fill values, then run:"
  echo "     scp -i libraryconnekto-key.pem .env ubuntu@<EIP>:/home/ubuntu/backend/.env"
  echo "     ssh -i libraryconnekto-key.pem ubuntu@<EIP> 'chmod 600 /home/ubuntu/backend/.env'"
  echo "  Re-run this bootstrap after the .env is in place to apply migrations."
  exit 0
fi
chmod 600 "$APP_DIR/.env"

echo "==> [6b/7] Running Alembic migrations"
alembic upgrade head

echo "==> [7/7] Installing systemd unit files & Nginx config"
sudo install -m 0644 "$APP_DIR/deploy/aws/systemd/libraryconnekto-api.service"    /etc/systemd/system/libraryconnekto-api.service
sudo install -m 0644 "$APP_DIR/deploy/aws/systemd/libraryconnekto-celery.service" /etc/systemd/system/libraryconnekto-celery.service
sudo install -m 0644 "$APP_DIR/deploy/aws/systemd/libraryconnekto-beat.service"   /etc/systemd/system/libraryconnekto-beat.service

sudo install -m 0644 "$APP_DIR/deploy/aws/nginx/libraryconnekto.conf" /etc/nginx/sites-available/libraryconnekto
sudo ln -sf /etc/nginx/sites-available/libraryconnekto /etc/nginx/sites-enabled/libraryconnekto
sudo rm -f /etc/nginx/sites-enabled/default

sudo systemctl daemon-reload
sudo systemctl enable libraryconnekto-api libraryconnekto-celery libraryconnekto-beat
sudo systemctl restart libraryconnekto-api libraryconnekto-celery libraryconnekto-beat

sudo nginx -t
sudo systemctl reload nginx
sudo systemctl enable nginx

echo
echo "==> Bootstrap complete."
echo "    - API:    sudo systemctl status libraryconnekto-api"
echo "    - Worker: sudo systemctl status libraryconnekto-celery"
echo "    - Beat:   sudo systemctl status libraryconnekto-beat"
echo "    - Health: curl http://127.0.0.1:8000/health"
echo
echo "Once DNS is pointing api.<domain> -> this EC2's Elastic IP, run:"
echo "    sudo certbot --nginx -d api.libraryconnekto.me \\"
echo "        --non-interactive --agree-tos --email you@example.com --redirect"
