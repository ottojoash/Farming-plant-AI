from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
import os
import secrets
from urllib.parse import urljoin, urlparse

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from database import (
    AppSetting,
    Payment,
    ScanRecord,
    ScanUsage,
    UpgradeRequest,
    User,
    db,
    get_int_setting,
    get_price_setting,
    utc_now,
)
from entitlements import current_month, scan_allowance, usage_for_user
from flutterwave import (
    FlutterwaveError,
    create_checkout,
    is_configured as flutterwave_is_configured,
    transaction_matches,
    valid_webhook_signature,
    verify_transaction,
)


accounts = Blueprint("accounts", __name__)
payment_webhooks = Blueprint("payment_webhooks", __name__)


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def premium_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.has_premium:
            flash("Scan history is available on the premium plan.", "error")
            return redirect(url_for("accounts.dashboard_plan"))
        return view(*args, **kwargs)

    return wrapped


def safe_next_url(target: str | None) -> str | None:
    if not target:
        return None
    host = urlparse(request.host_url)
    candidate = urlparse(urljoin(request.host_url, target))
    if candidate.scheme in {"http", "https"} and candidate.netloc == host.netloc:
        return candidate.path + (f"?{candidate.query}" if candidate.query else "")
    return None


def pricing() -> dict:
    return {
        "monthly": get_price_setting("premium_monthly_price"),
        "yearly": get_price_setting("premium_yearly_price"),
    }


def pending_upgrade_for_user():
    return UpgradeRequest.query.filter_by(user_id=current_user.id, status="pending").first()


def admin_metrics() -> dict:
    return {
        "users": User.query.filter_by(role="user").count(),
        "premium": User.query.filter(User.role == "user", User.plan.in_(["premium", "monthly", "yearly"])).count(),
        "month_scans": db.session.query(func.coalesce(func.sum(ScanUsage.scan_count), 0))
        .filter(ScanUsage.year_month == current_month())
        .scalar(),
        "history_records": ScanRecord.query.count(),
    }


@accounts.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("accounts.admin_dashboard" if current_user.role == "admin" else "accounts.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=request.form.get("remember") == "on")
            destination = safe_next_url(request.args.get("next"))
            if not destination:
                destination = url_for("accounts.admin_dashboard" if user.role == "admin" else "accounts.dashboard")
            return redirect(destination)
        flash("Invalid email or password.", "error")
    return render_template("auth.html", mode="login")


@accounts.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("accounts.dashboard"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if len(name) < 2:
            flash("Enter your name.", "error")
        elif "@" not in email or len(email) > 255:
            flash("Enter a valid email address.", "error")
        elif len(password) < 10:
            flash("Use a password with at least 10 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        else:
            user = User(name=name, email=email, role="user", plan="free")
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Your free account is ready.", "success")
            return redirect(url_for("accounts.dashboard"))
    return render_template("auth.html", mode="register")


@accounts.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


@accounts.post("/account/password")
@login_required
def change_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirmation = request.form.get("confirm_password", "")
    destination = "accounts.account_settings"

    if not current_user.check_password(current_password):
        flash("Your current password is incorrect.", "error")
    elif len(new_password) < 10:
        flash("Use a new password with at least 10 characters.", "error")
    elif new_password != confirmation:
        flash("The new passwords do not match.", "error")
    elif current_user.check_password(new_password):
        flash("Choose a password that is different from your current password.", "error")
    else:
        current_user.set_password(new_password)
        db.session.commit()
        flash("Password updated.", "success")
    return redirect(url_for(destination))


@accounts.get("/dashboard")
@login_required
def dashboard():
    if current_user.role == "admin":
        return redirect(url_for("accounts.admin_dashboard"))
    allowance = scan_allowance()
    history = (
        ScanRecord.query.filter_by(user_id=current_user.id).order_by(ScanRecord.created_at.desc()).limit(5).all()
        if current_user.has_premium
        else []
    )
    return render_template(
        "dashboard.html",
        allowance=allowance,
        history=history,
    )


@accounts.get("/dashboard/scan")
@login_required
def dashboard_scan():
    return render_template(
        "dashboard_scan.html",
        allowance=scan_allowance(),
        max_upload_mb=current_app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024),
    )


@accounts.get("/dashboard/history")
@premium_required
def dashboard_history():
    history = ScanRecord.query.filter_by(user_id=current_user.id).order_by(ScanRecord.created_at.desc()).limit(250).all()
    return render_template("dashboard_history.html", history=history)


@accounts.get("/scan-records/<int:record_id>")
@login_required
def scan_record_detail(record_id: int):
    scan = db.get_or_404(ScanRecord, record_id)
    if current_user.role == "admin":
        back_url = url_for("accounts.admin_records")
        back_label = "Back to all scan records"
    else:
        if scan.user_id != current_user.id:
            abort(403)
        if not current_user.has_premium:
            flash("An active Monthly or Yearly plan is required to view scan history.", "error")
            return redirect(url_for("accounts.dashboard_plan"))
        back_url = url_for("accounts.dashboard_history")
        back_label = "Back to scan history"
    return render_template(
        "scan_record_detail.html",
        scan=scan,
        back_url=back_url,
        back_label=back_label,
    )


@accounts.get("/dashboard/plan")
@login_required
def dashboard_plan():
    if current_user.role == "admin":
        return redirect(url_for("accounts.admin_plans"))
    return render_template(
        "dashboard_plan.html",
        allowance=scan_allowance(),
        pricing=pricing(),
        pending_upgrade=pending_upgrade_for_user(),
        flutterwave_ready=flutterwave_is_configured(),
        payments=Payment.query.filter_by(user_id=current_user.id).order_by(Payment.created_at.desc()).limit(10).all(),
        free_limit=get_int_setting("free_monthly_scan_limit"),
    )


@accounts.get("/account")
@login_required
def account_settings():
    return render_template("account_settings.html")


@accounts.post("/upgrade-request")
@login_required
def request_upgrade():
    if current_user.role == "admin" or current_user.has_premium:
        flash("This account already has premium access.", "success")
        return redirect(url_for("accounts.dashboard"))
    existing = UpgradeRequest.query.filter_by(user_id=current_user.id, status="pending").first()
    if existing is None:
        cycle = request.form.get("billing_cycle", "monthly")
        if cycle not in {"monthly", "yearly"}:
            abort(400)
        db.session.add(UpgradeRequest(user_id=current_user.id, billing_cycle=cycle))
        db.session.commit()
    flash("Upgrade request submitted. No payment has been collected; an administrator must approve it.", "success")
    return redirect(url_for("accounts.dashboard_plan"))


def _payment_currency() -> str:
    currency = os.getenv("FLW_CURRENCY", "USD").strip().upper()
    return currency if len(currency) == 3 and currency.isalpha() else "USD"


def _payment_amount(cycle: str) -> Decimal:
    return pricing()[cycle]


def _activate_verified_payment(payment: Payment, transaction: dict) -> bool:
    if payment.status == "successful":
        return True
    if not transaction_matches(
        transaction,
        tx_ref=payment.tx_ref,
        amount=Decimal(payment.amount),
        currency=payment.currency,
        email=payment.user.email,
    ):
        payment.status = "failed"
        db.session.commit()
        return False
    payment.status = "successful"
    payment.flutterwave_transaction_id = str(transaction.get("id"))
    payment.paid_at = utc_now()
    payment.user.plan = payment.billing_cycle
    duration = timedelta(days=30 if payment.billing_cycle == "monthly" else 365)
    coverage_start = max(utc_now(), payment.user.subscription_expires_at or utc_now())
    payment.user.subscription_expires_at = coverage_start + duration
    db.session.commit()
    return True


@accounts.post("/subscribe/<cycle>")
@login_required
def subscribe(cycle: str):
    if current_user.role == "admin":
        flash("Administrator accounts already have unlimited access.", "success")
        return redirect(url_for("accounts.admin_dashboard"))
    if cycle not in {"monthly", "yearly"}:
        abort(404)
    if not flutterwave_is_configured():
        flash("Flutterwave checkout is not configured yet. Please contact the administrator.", "error")
        return redirect(url_for("accounts.dashboard_plan"))

    payment = Payment(
        user_id=current_user.id,
        tx_ref=f"plantai-{secrets.token_urlsafe(18)}",
        billing_cycle=cycle,
        amount=_payment_amount(cycle),
        currency=_payment_currency(),
        status="pending",
    )
    db.session.add(payment)
    db.session.commit()
    base_url = os.getenv("APP_BASE_URL", "").strip().rstrip("/")
    callback_path = url_for("accounts.flutterwave_callback")
    callback_url = f"{base_url}{callback_path}" if base_url else url_for("accounts.flutterwave_callback", _external=True)
    try:
        checkout_url = create_checkout(
            tx_ref=payment.tx_ref,
            amount=Decimal(payment.amount),
            currency=payment.currency,
            redirect_url=callback_url,
            customer={"email": current_user.email, "name": current_user.name},
        )
    except FlutterwaveError:
        payment.status = "failed"
        db.session.commit()
        current_app.logger.exception("Flutterwave checkout creation failed")
        flash("Flutterwave checkout is temporarily unavailable. Please try again.", "error")
        return redirect(url_for("accounts.dashboard_plan"))
    return redirect(checkout_url)


@accounts.get("/payments/flutterwave/callback")
def flutterwave_callback():
    tx_ref = request.args.get("tx_ref", "")
    transaction_id = request.args.get("transaction_id", "")
    status = request.args.get("status", "")
    payment = Payment.query.filter_by(tx_ref=tx_ref).first()
    if payment is None:
        flash("We could not match that payment to a Plant AI subscription.", "error")
    elif status != "successful":
        payment.status = "failed"
        db.session.commit()
        flash("The Flutterwave payment was not completed.", "error")
    else:
        try:
            verified = _activate_verified_payment(payment, verify_transaction(transaction_id))
            flash(
                f"Payment verified. Your {payment.billing_cycle} plan is active." if verified else "Payment details could not be verified.",
                "success" if verified else "error",
            )
        except FlutterwaveError:
            current_app.logger.exception("Flutterwave callback verification failed")
            flash("We could not verify the payment yet. Please contact support with your transaction reference.", "error")
    return redirect(url_for("accounts.dashboard_plan"))


@payment_webhooks.post("/webhooks/flutterwave")
def flutterwave_webhook():
    raw_body = request.get_data(cache=True)
    if not valid_webhook_signature(raw_body, request.headers.get("flutterwave-signature")):
        abort(401)
    payload = request.get_json(silent=True) or {}
    data = payload.get("data", {})
    tx_ref = data.get("tx_ref") or data.get("reference")
    payment = Payment.query.filter_by(tx_ref=tx_ref).first() if tx_ref else None
    if payment and payment.status != "successful" and data.get("id"):
        try:
            _activate_verified_payment(payment, verify_transaction(str(data["id"])))
        except FlutterwaveError:
            current_app.logger.exception("Flutterwave webhook verification failed")
    return "", 200


@accounts.get("/admin")
@admin_required
def admin_dashboard():
    return render_template(
        "admin.html",
        metrics=admin_metrics(),
        pending_count=UpgradeRequest.query.filter_by(status="pending").count(),
        recent_users=User.query.order_by(User.created_at.desc()).limit(5).all(),
    )


@accounts.get("/admin/users")
@admin_required
def admin_users():
    return render_template("admin_users.html", users=User.query.order_by(User.created_at.desc()).all())


@accounts.get("/admin/upgrades")
@admin_required
def admin_upgrades():
    pending = UpgradeRequest.query.filter_by(status="pending").order_by(UpgradeRequest.created_at.asc()).all()
    resolved = UpgradeRequest.query.filter(UpgradeRequest.status != "pending").order_by(UpgradeRequest.resolved_at.desc()).limit(50).all()
    return render_template("admin_upgrades.html", upgrade_requests=pending, resolved_requests=resolved)


@accounts.get("/admin/plans")
@admin_required
def admin_plans():
    return render_template(
        "admin_plans.html",
        pricing=pricing(),
        anonymous_limit=get_int_setting("anonymous_scan_limit"),
        free_limit=get_int_setting("free_monthly_scan_limit"),
        flutterwave_ready=flutterwave_is_configured(),
        payment_counts={
            "pending": Payment.query.filter_by(status="pending").count(),
            "successful": Payment.query.filter_by(status="successful").count(),
            "failed": Payment.query.filter_by(status="failed").count(),
        },
        recent_payments=Payment.query.order_by(Payment.created_at.desc()).limit(20).all(),
    )


@accounts.get("/admin/records")
@admin_required
def admin_records():
    records = ScanRecord.query.order_by(ScanRecord.created_at.desc()).limit(250).all()
    return render_template("admin_records.html", recent_scans=records)


@accounts.get("/admin/system")
@admin_required
def admin_system():
    system = {
        "database": current_app.config["DATABASE_BACKEND"],
        "environment": "Testing" if current_app.config.get("TESTING") else "Production server",
        "csrf": current_app.config.get("WTF_CSRF_ENABLED", True),
        "users_table": User.query.count(),
        "usage_rows": ScanUsage.query.count(),
        "history_rows": ScanRecord.query.count(),
    }
    return render_template("admin_system.html", system=system)


@accounts.post("/admin/settings")
@admin_required
def update_settings():
    validators = {
        "premium_monthly_price": ("decimal", Decimal("0.01"), Decimal("10000")),
        "premium_yearly_price": ("decimal", Decimal("0.01"), Decimal("100000")),
        "anonymous_scan_limit": ("integer", 0, 100),
        "free_monthly_scan_limit": ("integer", 0, 10000),
    }
    updates = {}
    try:
        for key, (kind, minimum, maximum) in validators.items():
            raw = request.form.get(key, "").strip()
            value = Decimal(raw) if kind == "decimal" else int(raw)
            if value < minimum or value > maximum:
                raise ValueError(key)
            updates[key] = f"{value:.2f}" if kind == "decimal" else str(value)
    except (InvalidOperation, TypeError, ValueError):
        flash("Enter valid pricing and scan limits.", "error")
        return redirect(url_for("accounts.admin_plans"))

    for key, value in updates.items():
        setting = db.session.get(AppSetting, key)
        if setting is None:
            db.session.add(AppSetting(key=key, value=value))
        else:
            setting.value = value
    db.session.commit()
    flash("Plan configuration updated.", "success")
    return redirect(url_for("accounts.admin_plans"))


@accounts.post("/admin/users/<int:user_id>")
@admin_required
def update_user(user_id: int):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("Use a separate administrator to change your own role or status.", "error")
        return redirect(url_for("accounts.admin_users"))
    role = request.form.get("role", "user")
    plan = request.form.get("plan", "free")
    if role not in {"user", "admin"} or plan not in {"free", "monthly", "yearly", "premium"}:
        abort(400)
    user.role = role
    user.plan = "premium" if role == "admin" else plan
    user.subscription_expires_at = None
    user.active = request.form.get("active") == "on"
    db.session.commit()
    flash(f"Updated {user.email}.", "success")
    return redirect(url_for("accounts.admin_users"))


@accounts.post("/admin/upgrades/<int:request_id>/<decision>")
@admin_required
def resolve_upgrade(request_id: int, decision: str):
    upgrade = db.get_or_404(UpgradeRequest, request_id)
    if decision not in {"approve", "reject"} or upgrade.status != "pending":
        abort(400)
    upgrade.status = "approved" if decision == "approve" else "rejected"
    upgrade.resolved_at = utc_now()
    if decision == "approve":
        upgrade.user.plan = "premium"
    db.session.commit()
    flash(f"Upgrade request {upgrade.status}.", "success")
    return redirect(url_for("accounts.admin_upgrades"))
