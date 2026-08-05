from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser

from flask import session
from flask_login import current_user

from database import ScanRecord, ScanUsage, db, get_int_setting


class _PlainTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


def details_as_text(value: str | None) -> str | None:
    if not value:
        return None
    parser = _PlainTextExtractor()
    parser.feed(value)
    return "\n".join(parser.parts) or None


def current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def usage_for_user(user_id: int) -> ScanUsage | None:
    return ScanUsage.query.filter_by(user_id=user_id, year_month=current_month()).first()


def scan_allowance() -> dict:
    if current_user.is_authenticated:
        if current_user.has_premium:
            return {
                "allowed": True,
                "limit": None,
                "used": usage_for_user(current_user.id).scan_count if usage_for_user(current_user.id) else 0,
                "remaining": None,
                "audience": "premium",
            }
        limit = get_int_setting("free_monthly_scan_limit")
        usage = usage_for_user(current_user.id)
        used = usage.scan_count if usage else 0
        return {
            "allowed": used < limit,
            "limit": limit,
            "used": used,
            "remaining": max(0, limit - used),
            "audience": "free",
        }

    limit = get_int_setting("anonymous_scan_limit")
    used = int(session.get("anonymous_scan_count", 0))
    return {
        "allowed": used < limit,
        "limit": limit,
        "used": used,
        "remaining": max(0, limit - used),
        "audience": "anonymous",
    }


def record_successful_scan(result: dict, confidence: float | None) -> None:
    if not current_user.is_authenticated:
        session["anonymous_scan_count"] = int(session.get("anonymous_scan_count", 0)) + 1
        session.modified = True
        return

    usage = usage_for_user(current_user.id)
    if usage is None:
        usage = ScanUsage(user_id=current_user.id, year_month=current_month(), scan_count=0)
        db.session.add(usage)
    usage.scan_count += 1

    if current_user.has_premium:
        db.session.add(
            ScanRecord(
                user_id=current_user.id,
                crop=result["crop"],
                condition=result["disease"],
                confidence=confidence,
                source=result["source"],
                summary=result.get("summary"),
                details=details_as_text(result.get("details_html")),
                observations=result.get("observations") or [],
                causes=result.get("causes") or [],
                actions=result.get("actions") or [],
                warning=result.get("warning"),
                model_votes=result.get("model_votes") or [],
            )
        )
    db.session.commit()
