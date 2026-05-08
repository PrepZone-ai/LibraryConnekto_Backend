"""Exercise forgot-password endpoints (run from backend folder: python scripts/test_forgot_password.py).

Safe by default: only checks HTTP behavior + validation.

Destructive DB round-trip (changes passwords): set environment variable
  LIBRARY_TEST_FORGOT_E2E=1
"""
import asyncio
import os
import sys
from pathlib import Path

# Ensure backend root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import text

from app.database import engine
from main import app


async def run() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # OpenAPI
        r = await c.get("/openapi.json")
        paths = [p for p in r.json().get("paths", {}) if "forgot" in p]
        print("OpenAPI forgot routes:", paths)
        assert "/api/v1/auth/admin/forgot-password" in paths
        assert "/api/v1/auth/student/forgot-password" in paths

        # Uniform responses
        r = await c.post(
            "/api/v1/auth/admin/forgot-password",
            json={"email": "definitely_missing_xyz@example.com"},
        )
        assert r.status_code == 200 and r.json().get("success") is True
        print("OK admin forgot (unknown email):", r.json()["message"][:60], "...")

        r = await c.post(
            "/api/v1/auth/admin/reset-password",
            json={"token": "invalid", "new_password": "secret12"},
        )
        assert r.status_code == 400
        print("OK admin reset invalid token:", r.json()["detail"])

        r = await c.post(
            "/api/v1/auth/student/forgot-password",
            json={"student_id": "ZZZZ99999"},
        )
        assert r.status_code == 200 and r.json().get("success") is True
        print("OK student forgot (unknown id):", r.json()["message"][:60], "...")

        r = await c.post("/api/v1/auth/student/forgot-password", json={})
        assert r.status_code == 422
        print("OK student forgot validation (empty body): 422")

        e2e = os.environ.get("LIBRARY_TEST_FORGOT_E2E", "").lower() in ("1", "true", "yes")
        if not e2e:
            print("SKIP destructive E2E (set LIBRARY_TEST_FORGOT_E2E=1 to enable).")
            print("\nAll non-destructive forgot-password tests passed.")
            return

        # E2E when DB has rows (mutates passwords)
        with engine.connect() as conn:
            admin_row = conn.execute(
                text(
                    "SELECT email FROM admin_users WHERE status = 'active' "
                    "AND email_verified = true LIMIT 1"
                )
            ).fetchone()
            st_row = conn.execute(
                text(
                    "SELECT student_id FROM students WHERE hashed_password IS NOT NULL LIMIT 1"
                )
            ).fetchone()

        if admin_row:
            email = admin_row[0]
            await c.post("/api/v1/auth/admin/forgot-password", json={"email": email})
            with engine.connect() as conn:
                tok = conn.execute(
                    text("SELECT password_reset_token FROM admin_users WHERE email = :e"),
                    {"e": email},
                ).scalar()
            assert tok, "token should be set after forgot-password"
            r = await c.post(
                "/api/v1/auth/admin/reset-password",
                json={"token": tok, "new_password": "E2E_admin_pw_99"},
            )
            assert r.status_code == 200, r.text
            r = await c.post(
                "/api/v1/auth/admin/signin",
                json={"email": email, "password": "E2E_admin_pw_99"},
            )
            assert r.status_code == 200 and r.json().get("access_token")
            print("OK E2E admin: forgot -> reset -> signin")
        else:
            print("SKIP E2E admin: no active verified admin in DB")

        if st_row:
            sid = st_row[0]
            await c.post(
                "/api/v1/auth/student/forgot-password",
                json={"student_id": sid},
            )
            with engine.connect() as conn:
                tok = conn.execute(
                    text(
                        "SELECT password_reset_token FROM students WHERE student_id = :s"
                    ),
                    {"s": sid},
                ).scalar()
            assert tok, "student token should be set"
            r = await c.post(
                "/api/v1/student/set-password",
                json={"token": tok, "new_password": "E2E_stud_88"},
            )
            assert r.status_code == 200, r.text
            r = await c.post(
                "/api/v1/auth/student/signin",
                json={"email": sid, "password": "E2E_stud_88"},
            )
            assert r.status_code == 200 and r.json().get("access_token")
            print("OK E2E student: forgot -> set-password -> signin")
        else:
            print("SKIP E2E student: no student with password in DB")

    print("\nAll forgot-password tests passed.")


if __name__ == "__main__":
    asyncio.run(run())
