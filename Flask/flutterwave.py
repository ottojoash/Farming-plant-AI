from __future__ import annotations

import base64
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import os

import requests


API_BASE = "https://api.flutterwave.com/v3"


class FlutterwaveError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(os.getenv("FLW_PUBLIC_KEY", "").strip() and os.getenv("FLW_SECRET_KEY", "").strip())


def _headers() -> dict[str, str]:
    secret = os.getenv("FLW_SECRET_KEY", "").strip()
    if not secret:
        raise FlutterwaveError("Flutterwave is not configured.")
    return {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}


def create_checkout(*, tx_ref: str, amount: Decimal, currency: str, redirect_url: str, customer: dict) -> str:
    payload = {
        "tx_ref": tx_ref,
        "amount": f"{amount:.2f}",
        "currency": currency,
        "redirect_url": redirect_url,
        "customer": customer,
        "customizations": {
            "title": "Plant AI subscription",
            "description": "Unlimited plant scans and saved diagnosis history",
        },
    }
    try:
        response = requests.post(f"{API_BASE}/payments", headers=_headers(), json=payload, timeout=20)
        response.raise_for_status()
        body = response.json()
        link = body.get("data", {}).get("link")
        if body.get("status") != "success" or not link:
            raise FlutterwaveError("Flutterwave did not return a checkout link.")
        return link
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise FlutterwaveError("Could not start Flutterwave checkout.") from exc


def verify_transaction(transaction_id: str) -> dict:
    if not transaction_id or not str(transaction_id).replace("-", "").isalnum():
        raise FlutterwaveError("Invalid Flutterwave transaction identifier.")
    try:
        response = requests.get(
            f"{API_BASE}/transactions/{transaction_id}/verify",
            headers=_headers(),
            timeout=20,
        )
        response.raise_for_status()
        body = response.json()
        data = body.get("data")
        if body.get("status") != "success" or not isinstance(data, dict):
            raise FlutterwaveError("Flutterwave could not verify this transaction.")
        return data
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise FlutterwaveError("Could not verify the Flutterwave transaction.") from exc


def transaction_matches(data: dict, *, tx_ref: str, amount: Decimal, currency: str, email: str) -> bool:
    try:
        paid_amount = Decimal(str(data.get("amount")))
    except (InvalidOperation, TypeError):
        return False
    customer_email = str(data.get("customer", {}).get("email", "")).strip().lower()
    return (
        data.get("status") == "successful"
        and data.get("tx_ref") == tx_ref
        and str(data.get("currency", "")).upper() == currency.upper()
        and paid_amount >= amount
        and (not customer_email or customer_email == email.lower())
    )


def valid_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    secret_hash = os.getenv("FLW_SECRET_HASH", "").strip()
    if not secret_hash or not signature:
        return False
    digest = hmac.new(secret_hash.encode("utf-8"), raw_body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, signature)
