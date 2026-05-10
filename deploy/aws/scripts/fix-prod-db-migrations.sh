#!/usr/bin/env bash
# =============================================================================
# Production DB Migration Repair Script
# Run this ONCE on the EC2 server via SSH to fix the alembic stamp mismatch.
#
# Problem: alembic_version table shows the latest revision (p8q9r0s1t2u3)
# but the actual DB schema is missing tables/columns from migrations that
# were never applied (they were bypassed by an incorrect `alembic stamp head`).
#
# Usage (from your local machine):
#   ssh -i deploy/aws/scripts/libraryconnekto-key.pem ubuntu@<EC2_IP> 'bash -s' < deploy/aws/scripts/fix-prod-db-migrations.sh
#
# Or copy to EC2 and run directly:
#   chmod +x fix-prod-db-migrations.sh && ./fix-prod-db-migrations.sh
# =============================================================================
set -euo pipefail

BACKEND_DIR="/home/ubuntu/backend"
VENV="$BACKEND_DIR/venv/bin/activate"

echo "=== LibraryConnekto Production DB Repair ==="
echo "Time: $(date)"

cd "$BACKEND_DIR"
source "$VENV"

# ── Step 1: Show current alembic state ───────────────────────────────────────
echo ""
echo "--- Current alembic revision in DB ---"
alembic current --verbose || true

# ── Step 2: Probe which schema changes are actually in the DB ────────────────
echo ""
echo "--- Checking for missing schema (student_removal_requests table) ---"
python - <<'PYEOF'
import os, sys
from sqlalchemy import create_engine, inspect, text

url = os.environ["DATABASE_URL"]
engine = create_engine(url, pool_pre_ping=True)

with engine.connect() as conn:
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())

    missing_tables = []
    for t in ["student_removal_requests", "library_freed_seats",
              "student_qr_tokens", "student_transfer_requests"]:
        if t not in tables:
            missing_tables.append(t)

    missing_cols = {}
    if "students" in tables:
        student_cols = {c["name"] for c in inspector.get_columns("students")}
        for col in ["first_name", "last_name", "is_active", "removed_at"]:
            if col not in student_cols:
                missing_cols.setdefault("students", []).append(col)

    if "admin_users" in tables:
        admin_cols = {c["name"] for c in inspector.get_columns("admin_users")}
        for col in ["name", "bank_name", "bank_account_number", "bank_ifsc_code",
                    "bank_branch_name", "razorpay_linked_account_id",
                    "email_verification_token", "email_verified",
                    "password_reset_token", "password_reset_token_expires_at"]:
            if col not in admin_cols:
                missing_cols.setdefault("admin_users", []).append(col)

    if missing_tables or missing_cols:
        print("\n⚠️  SCHEMA IS OUT OF SYNC WITH MIGRATIONS!")
        if missing_tables:
            print(f"   Missing tables: {missing_tables}")
        for tbl, cols in missing_cols.items():
            print(f"   Missing columns on '{tbl}': {cols}")
        sys.exit(2)
    else:
        print("\n✅ All expected tables and columns are present.")
        sys.exit(0)
PYEOF

PROBE_EXIT=$?

# ── Step 3: Fix the schema mismatch ─────────────────────────────────────────
if [ "$PROBE_EXIT" -eq 2 ]; then
    echo ""
    echo "--- Fixing schema: stamping back to the pre-removal-system revision ---"
    echo "    This tells Alembic where the DB schema actually is."
    echo "    (f4118aa7b83e = last migration BEFORE student_removal_system was added)"

    # Stamp to the revision just before the first migration that the DB is missing.
    # Migration 1ee31fc54504 adds: student_removal_requests table, plus
    # first_name/last_name/is_active/removed_at on students, name on admin_users.
    # Its down_revision is f4118aa7b83e.
    alembic stamp f4118aa7b83e

    echo ""
    echo "--- Running all pending migrations ---"
    alembic upgrade head

    echo ""
    echo "--- Verifying final state ---"
    alembic current --verbose

    echo ""
    echo "✅ Migration repair complete!"

elif [ "$PROBE_EXIT" -eq 0 ]; then
    echo ""
    echo "✅ Schema is already correct. No repair needed."
    echo "   If you are still seeing 503 errors, check gunicorn logs:"
    echo "   sudo journalctl -u libraryconnekto-api -n 100 --no-pager"
fi

# ── Step 4: Restart the API so fresh connections pick up the new schema ──────
echo ""
echo "--- Restarting API service ---"
sudo systemctl restart libraryconnekto-api

echo ""
echo "--- Waiting 10s for workers to start ---"
sleep 10

echo "--- Health check ---"
curl --fail --silent --show-error http://127.0.0.1:8000/health | python3 -m json.tool || true

echo ""
echo "=== Done. Check output above for any remaining errors. ==="
echo "    Full logs: sudo journalctl -u libraryconnekto-api -n 200 --no-pager"
