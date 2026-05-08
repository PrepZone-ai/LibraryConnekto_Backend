"""Lightweight database connectivity probe used by the container entrypoint.

Exits with code 0 only when the database is reachable AND a known
application table exists. The entrypoint script uses this signal to
skip Alembic migrations on already-bootstrapped databases.
"""
from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, inspect, text


REQUIRED_TABLES = ("admin_users", "students")


def main() -> int:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[db-probe] DATABASE_URL not set", file=sys.stderr)
        return 1

    try:
        engine = create_engine(db_url, pool_pre_ping=True, future=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            inspector = inspect(conn)
            existing = set(inspector.get_table_names())
            missing = [t for t in REQUIRED_TABLES if t not in existing]
            if missing:
                print(
                    f"[db-probe] Connected, but missing tables: {missing}",
                    file=sys.stderr,
                )
                return 2
            print("[db-probe] Database reachable and schema present.")
            return 0
    except Exception as exc:  # noqa: BLE001 - we want to surface any failure
        print(f"[db-probe] Connection failed: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
