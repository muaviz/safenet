import os
import sys
import pytest

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app import app, db, User, ChildProfile, Device, BlockedSite, ActivityLog, AccessRequest
from classifier import normalize_domain, classify_domain_quick, classify_page_content


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_domain_normalization():
    assert normalize_domain("https://WWW.YouTube.com/watch?v=123") == "youtube.com"
    assert normalize_domain("http://example.com/some/path") == "example.com"
    assert normalize_domain("reddit.com/") == "reddit.com"
    assert normalize_domain("Sub.Domain.com") == "sub.domain.com"
    assert normalize_domain("localhost:5000") == "localhost"


def test_ai_classifier():
    # Educational
    res = classify_page_content("https://wikipedia.org", title="Science Article")
    assert res["blocked"] is False
    assert res["category"] == "educational"

    # Known adult
    res = classify_page_content("https://pornhub.com", safety_tier="moderate")
    assert res["blocked"] is True

    # Inappropriate text keywords
    res = classify_page_content("https://random-site.com", title="Free NSFW content", snippet="explicit adult photos")
    assert res["blocked"] is True

    # Phishing threat detection
    res = classify_page_content("https://secure-bank-login.xyz", title="Login", snippet="Urgent account suspended. Confirm your password and verify your bank account.")
    assert res["blocked"] is True
    assert res["category"] == "scam_phishing"

    # Strict mode restrictions (e.g. social media blocked on strict)
    res = classify_page_content("https://tiktok.com", safety_tier="strict")
    assert res["blocked"] is True


def test_user_signup_and_child_creation(client):
    # Signup
    response = client.post("/", data={
        "form_type": "signup",
        "name": "Jane Doe",
        "email": "jane@example.com",
        "password": "securepassword123",
        "confirm_password": "securepassword123"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Family Safety Center" in response.data

    with app.app_context():
        user = User.query.filter_by(email="jane@example.com").first()
        assert user is not None
        assert len(user.children) >= 1
        assert user.children[0].name == "Child 1"


def test_device_pairing_and_policy(client):
    # Create user & child
    with app.app_context():
        user = User(name="John Parent", email="john@test.com", password="hash")
        db.session.add(user)
        db.session.commit()

        child = ChildProfile(parent_id=user.id, name="Alice", age=8, safety_tier="strict")
        db.session.add(child)
        db.session.commit()
        child_id = child.id

    # Log in as parent and generate pairing code
    with client.session_transaction() as sess:
        sess["_user_id"] = "1"

    pair_resp = client.post(f"/children/{child_id}/pair-code", follow_redirects=True)
    assert pair_resp.status_code == 200

    # Read generated pairing code
    with app.app_context():
        device = Device.query.filter_by(child_id=child_id).first()
        assert device is not None
        code = device.pairing_code
        assert len(code) == 6

    # Extension pairs with code
    pair_api_resp = client.post("/api/v1/devices/pair", json={"code": code})
    assert pair_api_resp.status_code == 200
    data = pair_api_resp.get_json()
    assert "device_token" in data
    assert data["child"]["name"] == "Alice"

    device_token = data["device_token"]

    # Fetch policy with device token
    policy_resp = client.get("/api/v1/policy", headers={"Authorization": f"Bearer {device_token}"})
    assert policy_resp.status_code == 200
    policy_data = policy_resp.get_json()
    assert "blocked_sites" in policy_data
    # In strict mode, adult & gambling should be in blocked sites
    assert "pornhub.com" in policy_data["blocked_sites"]


def test_telemetry_and_access_request(client):
    with app.app_context():
        user = User(name="Parent", email="p@test.com", password="hash")
        db.session.add(user)
        db.session.commit()

        child = ChildProfile(parent_id=user.id, name="Bob", age=12)
        db.session.add(child)
        db.session.commit()

        device = Device(child_id=child.id, device_token="test-token-123")
        db.session.add(device)
        db.session.commit()

    # Telemetry
    telem_resp = client.post("/api/v1/device/telemetry", headers={
        "Authorization": "Bearer test-token-123"
    }, json={
        "visits": [
            {"domain": "https://www.khanacademy.org", "duration_seconds": 300},
            {"domain": "youtube.com", "duration_seconds": 600}
        ]
    })
    assert telem_resp.status_code == 200

    with app.app_context():
        logs = ActivityLog.query.filter_by(child_id=1).all()
        assert len(logs) == 2
        domains = [l.domain for l in logs]
        assert "khanacademy.org" in domains
        assert "youtube.com" in domains

    # Access request
    req_resp = client.post("/api/v1/device/request-access", headers={
        "Authorization": "Bearer test-token-123"
    }, json={
        "url": "https://discord.com",
        "reason": "Studying with friends"
    })
    assert req_resp.status_code == 201

    with app.app_context():
        access_req = AccessRequest.query.filter_by(child_id=1).first()
        assert access_req is not None
        assert access_req.url == "discord.com"
        assert access_req.status == "pending"


def test_legacy_blocklist_endpoints(client):
    # Add
    post_res = client.post("/blocklist", json={"url": "https://WWW.TikTok.com/@user"})
    assert post_res.status_code == 201
    assert "tiktok.com" in post_res.get_json()["message"]

    # Get
    get_res = client.get("/blocklist")
    assert get_res.status_code == 200
    assert "tiktok.com" in get_res.get_json()["blocked_sites"]

    # Delete
    del_res = client.delete("/blocklist", json={"url": "tiktok.com"})
    assert del_res.status_code == 200

    get_res2 = client.get("/blocklist")
    assert "tiktok.com" not in get_res2.get_json()["blocked_sites"]
