from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import os

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, inspect, text
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user", index=True)
    plan = db.Column(db.String(20), nullable=False, default="free", index=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    subscription_expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    scans = db.relationship("ScanRecord", back_populates="user", cascade="all, delete-orphan")
    usage = db.relationship("ScanUsage", back_populates="user", cascade="all, delete-orphan")
    payments = db.relationship("Payment", back_populates="user", cascade="all, delete-orphan")

    @property
    def is_active(self) -> bool:
        return bool(self.active)

    @property
    def has_premium(self) -> bool:
        if self.role == "admin" or self.plan == "premium":
            return True
        if self.plan not in {"monthly", "yearly"}:
            return False
        return self.subscription_expires_at is None or self.subscription_expires_at > utc_now()

    @property
    def plan_label(self) -> str:
        if self.role == "admin":
            return "Administrator"
        return "Premium" if self.plan == "premium" else self.plan.title()

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class ScanUsage(db.Model):
    __tablename__ = "scan_usage"
    __table_args__ = (UniqueConstraint("user_id", "year_month", name="uq_user_usage_month"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    year_month = db.Column(db.String(7), nullable=False, index=True)
    scan_count = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    user = db.relationship("User", back_populates="usage")


class ScanRecord(db.Model):
    __tablename__ = "scan_records"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    crop = db.Column(db.String(120), nullable=False)
    condition = db.Column(db.String(180), nullable=False)
    confidence = db.Column(db.Float, nullable=True)
    source = db.Column(db.String(180), nullable=False)
    summary = db.Column(db.Text, nullable=True)
    details = db.Column(db.Text, nullable=True)
    observations = db.Column(db.JSON, nullable=True)
    causes = db.Column(db.JSON, nullable=True)
    actions = db.Column(db.JSON, nullable=True)
    warning = db.Column(db.Text, nullable=True)
    model_votes = db.Column(db.JSON, nullable=True)
    evidence = db.Column(db.JSON, nullable=True)
    evidence_corpus_version = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now, index=True)

    user = db.relationship("User", back_populates="scans")


class AppSetting(db.Model):
    __tablename__ = "app_settings"

    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.String(255), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class UpgradeRequest(db.Model):
    __tablename__ = "upgrade_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    billing_cycle = db.Column(db.String(20), nullable=False, default="monthly")
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    resolved_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User")


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tx_ref = db.Column(db.String(100), nullable=False, unique=True, index=True)
    billing_cycle = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="USD")
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    flutterwave_transaction_id = db.Column(db.String(100), nullable=True, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    paid_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", back_populates="payments")


DEFAULT_SETTINGS = {
    "premium_monthly_price": "20.00",
    "premium_yearly_price": "240.00",
    "anonymous_scan_limit": "2",
    "free_monthly_scan_limit": "5",
}


def ensure_schema_compatibility() -> None:
    """Apply the two additive scan-record columns needed by existing installs."""
    columns = {column["name"] for column in inspect(db.engine).get_columns("scan_records")}
    additions = {
        "evidence": "JSON NULL",
        "evidence_corpus_version": "VARCHAR(120) NULL",
    }
    for name, sql_type in additions.items():
        if name not in columns:
            db.session.execute(text(f"ALTER TABLE scan_records ADD COLUMN {name} {sql_type}"))
    db.session.commit()


def get_setting(key: str, default: str | None = None) -> str:
    setting = db.session.get(AppSetting, key)
    return setting.value if setting else (default if default is not None else DEFAULT_SETTINGS[key])


def get_int_setting(key: str) -> int:
    try:
        return max(0, int(get_setting(key)))
    except (TypeError, ValueError):
        return int(DEFAULT_SETTINGS[key])


def get_price_setting(key: str) -> Decimal:
    try:
        return Decimal(get_setting(key)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        return Decimal(DEFAULT_SETTINGS[key])


def seed_defaults() -> None:
    for key, value in DEFAULT_SETTINGS.items():
        if db.session.get(AppSetting, key) is None:
            db.session.add(AppSetting(key=key, value=value))
    db.session.commit()


def bootstrap_admin() -> User | None:
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email or not password:
        return None
    admin = User.query.filter_by(email=email).first()
    if admin is None:
        admin = User(
            name=os.getenv("ADMIN_NAME", "Plant AI Administrator").strip(),
            email=email,
            role="admin",
            plan="premium",
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
    return admin
