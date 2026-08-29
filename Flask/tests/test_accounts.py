from __future__ import annotations

import io

from database import AppSetting, Payment, ScanRecord, ScanUsage, UpgradeRequest, User, db
from model import Prediction


def register(client, email: str = "grower@example.com", password: str = "strong-pass-123"):
    return client.post(
        "/register",
        data={"name": "Test Grower", "email": email, "password": password},
        follow_redirects=False,
    )


def login(client, email: str, password: str):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def scan(client, jpeg_bytes: bytes):
    return client.post(
        "/predict",
        data={"file": (io.BytesIO(jpeg_bytes), "leaf.jpg")},
        content_type="multipart/form-data",
    )


def mock_fast_prediction(monkeypatch):
    monkeypatch.setattr("app.predict_image", lambda _: Prediction("Tomato___healthy", 0.97))


def create_user(app, email: str, password: str, *, role: str = "user", plan: str = "free") -> int:
    with app.app_context():
        user = User(name="Account User", email=email, role=role, plan=plan)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


def test_registration_creates_free_user_and_opens_user_dashboard(client, app):
    response = register(client)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    with app.app_context():
        user = User.query.filter_by(email="grower@example.com").one()
        assert user.role == "user"
        assert user.plan == "free"
        assert user.password_hash != "strong-pass-123"


def test_shared_login_redirects_admin_to_admin_dashboard(client, app):
    create_user(app, "admin@example.com", "admin-pass-123", role="admin", plan="premium")

    response = login(client, "admin@example.com", "admin-pass-123")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin")


def test_anonymous_user_is_prompted_to_register_after_two_scans(client, jpeg_bytes, monkeypatch):
    mock_fast_prediction(monkeypatch)

    assert scan(client, jpeg_bytes).status_code == 200
    assert scan(client, jpeg_bytes).status_code == 200
    blocked = scan(client, jpeg_bytes)

    assert blocked.status_code == 403
    assert b"two free trial scans are complete" in blocked.data
    assert b"Create free account" in blocked.data


def test_free_user_gets_five_monthly_scans_without_history(client, app, jpeg_bytes, monkeypatch):
    mock_fast_prediction(monkeypatch)
    register(client)

    for _ in range(5):
        assert scan(client, jpeg_bytes).status_code == 200
    blocked = scan(client, jpeg_bytes)

    assert blocked.status_code == 403
    assert b"used all 5 free scans" in blocked.data
    with app.app_context():
        user = User.query.filter_by(email="grower@example.com").one()
        assert ScanUsage.query.filter_by(user_id=user.id).one().scan_count == 5
        assert ScanRecord.query.filter_by(user_id=user.id).count() == 0


def test_premium_user_has_unlimited_scans_and_history(client, app, jpeg_bytes, monkeypatch):
    mock_fast_prediction(monkeypatch)
    user_id = create_user(app, "premium@example.com", "premium-pass-123", plan="premium")
    login(client, "premium@example.com", "premium-pass-123")

    for _ in range(7):
        assert scan(client, jpeg_bytes).status_code == 200

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert b"Unlimited" in dashboard.data
    assert b"Tomato" in dashboard.data
    with app.app_context():
        assert ScanUsage.query.filter_by(user_id=user_id).one().scan_count == 7
        assert ScanRecord.query.filter_by(user_id=user_id).count() == 7


def test_premium_user_can_open_detailed_scan_record(client, app, jpeg_bytes, monkeypatch):
    mock_fast_prediction(monkeypatch)
    user_id = create_user(app, "premium@example.com", "premium-pass-123", plan="premium")
    login(client, "premium@example.com", "premium-pass-123")
    scan(client, jpeg_bytes)
    with app.app_context():
        record = ScanRecord.query.filter_by(user_id=user_id).one()
        record_id = record.id
        assert record.details
        assert record.model_votes

    page = client.get(f"/scan-records/{record_id}")

    assert page.status_code == 200
    assert b"Saved diagnosis" in page.data
    assert b"Models checked" in page.data
    assert b"Original ResNet34 model" in page.data
    assert b"Privacy note" in page.data


def test_user_cannot_open_another_users_scan_record(client, app):
    owner_id = create_user(app, "owner@example.com", "owner-pass-123", plan="premium")
    create_user(app, "viewer@example.com", "viewer-pass-123", plan="premium")
    with app.app_context():
        record = ScanRecord(
            user_id=owner_id,
            crop="Tomato",
            condition="Healthy",
            confidence=0.98,
            source="Test model",
            summary="Healthy leaf snapshot",
        )
        db.session.add(record)
        db.session.commit()
        record_id = record.id
    login(client, "viewer@example.com", "viewer-pass-123")

    assert client.get(f"/scan-records/{record_id}").status_code == 403


def test_admin_can_open_any_scan_record(client, app):
    owner_id = create_user(app, "owner@example.com", "owner-pass-123", plan="premium")
    create_user(app, "admin@example.com", "admin-pass-123", role="admin", plan="premium")
    with app.app_context():
        record = ScanRecord(
            user_id=owner_id,
            crop="Bean",
            condition="Rust",
            confidence=0.88,
            source="Field model",
        )
        db.session.add(record)
        db.session.commit()
        record_id = record.id
    login(client, "admin@example.com", "admin-pass-123")

    page = client.get(f"/scan-records/{record_id}")

    assert page.status_code == 200
    assert b"owner@example.com" in page.data
    assert b"Detailed snapshot unavailable" in page.data


def test_regular_user_cannot_open_admin_dashboard(client, app):
    create_user(app, "user@example.com", "regular-pass-123")
    login(client, "user@example.com", "regular-pass-123")

    assert client.get("/admin").status_code == 403


def test_free_sidebar_has_plan_pages_without_premium_history(client):
    register(client)

    dashboard = client.get("/dashboard")

    assert dashboard.status_code == 200
    assert b"Scan plant" in dashboard.data
    assert b"Plan &amp; usage" in dashboard.data
    assert b"Account settings" in dashboard.data
    assert b"Scan history" not in dashboard.data
    assert client.get("/dashboard/scan").status_code == 200
    assert client.get("/dashboard/plan").status_code == 200
    history_redirect = client.get("/dashboard/history")
    assert history_redirect.status_code == 302
    assert history_redirect.headers["Location"].endswith("/dashboard/plan")


def test_premium_sidebar_includes_history(client, app):
    create_user(app, "premium@example.com", "premium-pass-123", plan="premium")
    login(client, "premium@example.com", "premium-pass-123")

    dashboard = client.get("/dashboard")

    assert b"Scan history" in dashboard.data
    history = client.get("/dashboard/history")
    assert history.status_code == 200
    assert b'aria-current="page"' in history.data


def test_signed_in_scan_result_keeps_sidebar(client, jpeg_bytes, monkeypatch):
    mock_fast_prediction(monkeypatch)
    register(client)

    result = scan(client, jpeg_bytes)

    assert result.status_code == 200
    assert b"Scan result" in result.data
    assert b"Plan &amp; usage" in result.data
    assert b'aria-current="page"' in result.data


def test_dashboard_scanner_has_preview_and_upload_controls(client):
    register(client)

    page = client.get("/dashboard/scan")

    assert page.status_code == 200
    assert b"dashboard-image-preview" in page.data
    assert b"dashboard-file-input" in page.data
    assert b"Scanning every plant model" in page.data
    assert b'name="reported_crop"' in page.data
    assert b'name="symptoms"' in page.data


def test_premium_memory_uses_only_owned_records_for_the_named_crop(client, app, jpeg_bytes, monkeypatch):
    owner_id = create_user(app, "premium@example.com", "premium-pass-123", plan="monthly")
    other_id = create_user(app, "other@example.com", "other-pass-123", plan="monthly")
    with app.app_context():
        db.session.add_all(
            [
                ScanRecord(
                    user_id=owner_id,
                    crop="Tomato",
                    condition="Healthy",
                    confidence=0.91,
                    source="Previous owner model",
                ),
                ScanRecord(
                    user_id=owner_id,
                    crop="Apple",
                    condition="Healthy",
                    confidence=0.88,
                    source="Different crop model",
                ),
                ScanRecord(
                    user_id=other_id,
                    crop="Tomato",
                    condition="Late blight",
                    confidence=0.84,
                    source="Other user's model",
                ),
            ]
        )
        db.session.commit()
    login(client, "premium@example.com", "premium-pass-123")
    mock_fast_prediction(monkeypatch)

    response = client.post(
        "/predict",
        data={
            "file": (io.BytesIO(jpeg_bytes), "tomato.jpg"),
            "reported_crop": "Tomato",
            "symptoms": "No visible damage",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"Compared this assessment with 1 previous Tomato record" in response.data
    assert b"similar condition appears in your previous records" in response.data
    assert b"Other user" not in response.data


def test_free_account_does_not_receive_scan_history_as_agent_memory(client, app, jpeg_bytes, monkeypatch):
    user_id = create_user(app, "free-memory@example.com", "free-pass-123", plan="free")
    with app.app_context():
        db.session.add(
            ScanRecord(
                user_id=user_id,
                crop="Tomato",
                condition="Healthy",
                confidence=0.91,
                source="Legacy record",
            )
        )
        db.session.commit()
    login(client, "free-memory@example.com", "free-pass-123")
    mock_fast_prediction(monkeypatch)

    response = client.post(
        "/predict",
        data={
            "file": (io.BytesIO(jpeg_bytes), "tomato.jpg"),
            "reported_crop": "Tomato",
            "symptoms": "No visible damage",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"previous Tomato record" not in response.data


def test_flutterwave_checkout_creates_pending_payment(client, app, monkeypatch):
    register(client)
    monkeypatch.setenv("FLW_PUBLIC_KEY", "FLWPUBK_TEST-example")
    monkeypatch.setenv("FLW_SECRET_KEY", "FLWSECK_TEST-example")
    monkeypatch.setattr("accounts.create_checkout", lambda **_: "https://checkout.flutterwave.com/test")

    response = client.post("/subscribe/monthly")

    assert response.status_code == 302
    assert response.headers["Location"] == "https://checkout.flutterwave.com/test"
    with app.app_context():
        payment = Payment.query.one()
        assert payment.billing_cycle == "monthly"
        assert payment.status == "pending"
        assert float(payment.amount) == 20.0


def test_only_verified_flutterwave_payment_activates_monthly_plan(client, app, monkeypatch):
    user_id = create_user(app, "payer@example.com", "payer-pass-123")
    login(client, "payer@example.com", "payer-pass-123")
    with app.app_context():
        payment = Payment(
            user_id=user_id,
            tx_ref="plantai-test-reference",
            billing_cycle="monthly",
            amount="20.00",
            currency="USD",
            status="pending",
        )
        db.session.add(payment)
        db.session.commit()
    monkeypatch.setattr(
        "accounts.verify_transaction",
        lambda _: {
            "id": 441122,
            "tx_ref": "plantai-test-reference",
            "status": "successful",
            "amount": 20,
            "currency": "USD",
            "customer": {"email": "payer@example.com"},
        },
    )

    response = client.get(
        "/payments/flutterwave/callback?status=successful&tx_ref=plantai-test-reference&transaction_id=441122"
    )

    assert response.status_code == 302
    with app.app_context():
        paid_user = db.session.get(User, user_id)
        assert paid_user.plan == "monthly"
        assert paid_user.subscription_expires_at is not None
        assert paid_user.has_premium
        assert Payment.query.one().status == "successful"


def test_mismatched_flutterwave_amount_does_not_activate_plan(client, app, monkeypatch):
    user_id = create_user(app, "payer@example.com", "payer-pass-123")
    with app.app_context():
        db.session.add(
            Payment(
                user_id=user_id,
                tx_ref="plantai-low-payment",
                billing_cycle="yearly",
                amount="240.00",
                currency="USD",
                status="pending",
            )
        )
        db.session.commit()
    monkeypatch.setattr(
        "accounts.verify_transaction",
        lambda _: {
            "id": 778899,
            "tx_ref": "plantai-low-payment",
            "status": "successful",
            "amount": 2,
            "currency": "USD",
            "customer": {"email": "payer@example.com"},
        },
    )

    client.get("/payments/flutterwave/callback?status=successful&tx_ref=plantai-low-payment&transaction_id=778899")

    with app.app_context():
        assert db.session.get(User, user_id).plan == "free"
        assert Payment.query.one().status == "failed"


def test_admin_sidebar_pages_are_role_protected(client, app):
    create_user(app, "admin@example.com", "admin-pass-123", role="admin", plan="premium")
    login(client, "admin@example.com", "admin-pass-123")

    for path in ("/admin", "/admin/users", "/admin/upgrades", "/admin/plans", "/admin/records", "/admin/system"):
        assert client.get(path).status_code == 200
    admin = client.get("/admin")
    assert b"Users" in admin.data
    assert b"Upgrade requests" in admin.data
    assert b"Plans &amp; limits" in admin.data
    assert b"System status" in admin.data


def test_user_can_change_password(client, app):
    create_user(app, "user@example.com", "regular-pass-123")
    login(client, "user@example.com", "regular-pass-123")

    response = client.post(
        "/account/password",
        data={
            "current_password": "regular-pass-123",
            "new_password": "safer-new-pass-456",
            "confirm_password": "safer-new-pass-456",
        },
    )

    assert response.status_code == 302
    client.post("/logout")
    assert login(client, "user@example.com", "regular-pass-123").status_code == 200
    assert login(client, "user@example.com", "safer-new-pass-456").headers["Location"].endswith("/dashboard")


def test_admin_can_configure_prices_and_scan_limits(client, app):
    create_user(app, "admin@example.com", "admin-pass-123", role="admin", plan="premium")
    login(client, "admin@example.com", "admin-pass-123")

    response = client.post(
        "/admin/settings",
        data={
            "premium_monthly_price": "25.50",
            "premium_yearly_price": "250.00",
            "anonymous_scan_limit": "3",
            "free_monthly_scan_limit": "8",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(AppSetting, "premium_monthly_price").value == "25.50"
        assert db.session.get(AppSetting, "free_monthly_scan_limit").value == "8"


def test_admin_can_approve_upgrade_request(client, app):
    user_id = create_user(app, "user@example.com", "regular-pass-123")
    admin_id = create_user(app, "admin@example.com", "admin-pass-123", role="admin", plan="premium")
    login(client, "user@example.com", "regular-pass-123")
    client.post("/upgrade-request", data={"billing_cycle": "monthly"})
    client.post("/logout")
    login(client, "admin@example.com", "admin-pass-123")
    with app.app_context():
        request_id = UpgradeRequest.query.filter_by(user_id=user_id).one().id

    response = client.post(f"/admin/upgrades/{request_id}/approve")

    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(User, user_id).plan == "premium"
        assert db.session.get(User, admin_id).role == "admin"
