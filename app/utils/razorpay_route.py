"""Helpers for Razorpay Route: settle order payments to library linked accounts."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from app.core.config import settings
from app.models.admin import AdminDetails


def order_transfers_to_library(
    library: Optional[AdminDetails],
    *,
    amount_paise: int,
    currency: str = "INR",
    notes: Optional[Dict[str, Any]] = None,
) -> Optional[List[Dict[str, Any]]]:
    """
    Build Razorpay Order `transfers` so the full amount settles to the library linked account.

    Returns None when RAZORPAY_ROUTE_ENABLED is false (legacy: full amount stays on platform).

    Raises HTTPException when Route is enabled but the library has no linked account id.
    """
    if not settings.RAZORPAY_ROUTE_ENABLED:
        return None
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    acc = (library.razorpay_linked_account_id or "").strip()
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Online payments are not configured for this library. "
                "The library admin must add their Razorpay linked account ID in Library Settings "
                "(Razorpay Route / Linked Accounts)."
            ),
        )
    if amount_paise <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payment amount")
    return [
        {
            "account": acc,
            "amount": amount_paise,
            "currency": currency,
            "notes": dict(notes or {}),
        }
    ]
