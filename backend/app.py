import os
import random
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from dotenv import load_dotenv

from classifier import normalize_domain, classify_domain_quick, classify_page_content

load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configuration
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///safenet.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "safenet-production-fallback-key-9283748234")

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "home"

# ==========================================
# Database Models
# ==========================================

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    children = db.relationship("ChildProfile", backref="parent", cascade="all, delete-orphan", lazy=True)


class ChildProfile(db.Model):
    __tablename__ = "child_profiles"
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, default=10)
    safety_tier = db.Column(db.String(20), default="moderate")  # strict, moderate, teen
    daily_limit_minutes = db.Column(db.Integer, default=120)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    devices = db.relationship("Device", backref="child", cascade="all, delete-orphan", lazy=True)
    rules = db.relationship("BlockedSite", backref="child", cascade="all, delete-orphan", lazy=True)
    activity_logs = db.relationship("ActivityLog", backref="child", cascade="all, delete-orphan", lazy=True)
    access_requests = db.relationship("AccessRequest", backref="child", cascade="all, delete-orphan", lazy=True)


class Device(db.Model):
    __tablename__ = "devices"
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("child_profiles.id"), nullable=False)
    device_name = db.Column(db.String(100), default="Chrome Browser")
    device_token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    pairing_code = db.Column(db.String(6), nullable=True)
    code_expires_at = db.Column(db.DateTime, nullable=True)
    last_heartbeat = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)


class BlockedSite(db.Model):
    __tablename__ = "blocked_sites"
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("child_profiles.id"), nullable=True)
    url = db.Column(db.String(255), nullable=False, index=True)
    rule_type = db.Column(db.String(10), default="block")  # block or allow
    category = db.Column(db.String(50), default="custom")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("child_profiles.id"), nullable=True)
    domain = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50), default="general")
    duration_seconds = db.Column(db.Integer, default=0)
    was_blocked = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class AccessRequest(db.Model):
    __tablename__ = "access_requests"
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("child_profiles.id"), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="pending")  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = db.Column(db.DateTime, nullable=True)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Initialize Tables & Default Data
with app.app_context():
    db.create_all()

# ==========================================
# Web Routes (Dashboard & Auth)
# ==========================================

@app.route('/', methods=['GET', 'POST'])
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'login':
            email = (request.form.get('email') or '').strip().lower()
            password = request.form.get('password') or ''
            user = User.query.filter_by(email=email).first()

            if user and bcrypt.check_password_hash(user.password, password):
                login_user(user)
                flash("Welcome back!", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Invalid email or password", "error")
                return redirect(url_for("home"))

        elif form_type == 'signup':
            name = (request.form.get('name') or '').strip()
            email = (request.form.get('email') or '').strip().lower()
            password = request.form.get('password') or ''
            confirm_password = request.form.get('confirm_password') or ''

            if not name or not email or not password:
                flash("Please fill in all required fields.", "error")
                return redirect(url_for("home"))

            if password != confirm_password:
                flash("Passwords do not match!", "error")
                return redirect(url_for("home"))

            if len(password) < 6:
                flash("Password must be at least 6 characters long.", "error")
                return redirect(url_for("home"))

            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash("Email is already registered! Please log in.", "error")
                return redirect(url_for("home"))

            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
            new_user = User(name=name, email=email, password=hashed_pw)
            db.session.add(new_user)
            db.session.commit()

            # Create default Child Profile for convenience
            default_child = ChildProfile(
                parent_id=new_user.id,
                name="Child 1",
                age=10,
                safety_tier="moderate",
                daily_limit_minutes=120
            )
            db.session.add(default_child)
            db.session.commit()

            login_user(new_user)
            flash("Account successfully created!", "success")
            return redirect(url_for("dashboard"))

    return render_template("landing.html")


@app.route('/dashboard')
@login_required
def dashboard():
    # Retrieve user's children
    children = ChildProfile.query.filter_by(parent_id=current_user.id).all()

    # If new user has no children, create initial profile
    if not children:
        c1 = ChildProfile(parent_id=current_user.id, name="Child 1", age=10, safety_tier="moderate")
        db.session.add(c1)
        db.session.commit()
        children = [c1]

    # Calculate screen time per child for today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    child_stats = []
    for child in children:
        logs = ActivityLog.query.filter(
            ActivityLog.child_id == child.id,
            ActivityLog.timestamp >= today_start
        ).all()

        total_seconds = sum(log.duration_seconds for log in logs)
        total_minutes = round(total_seconds / 60)
        daily_limit = child.daily_limit_minutes or 120
        percent = min(round((total_minutes / daily_limit) * 100), 100)

        # Activity summary
        activity_summary = {}
        for log in logs:
            cat = log.category or "General"
            activity_summary[cat] = activity_summary.get(cat, 0) + log.duration_seconds

        top_activities = sorted(
            [{"category": k.replace('_', ' ').title(), "minutes": round(v / 60)} for k, v in activity_summary.items()],
            key=lambda x: x["minutes"],
            reverse=True
        )[:3]

        # Active pairing code / status
        active_device = Device.query.filter_by(child_id=child.id, is_active=True).first()
        active_code = None
        is_paired = False
        if active_device:
            now = datetime.now(timezone.utc)
            exp = active_device.code_expires_at
            if exp and exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if active_device.pairing_code and exp and exp > now:
                active_code = active_device.pairing_code
            if active_device.last_heartbeat and not active_device.pairing_code:
                is_paired = True

        child_stats.append({
            "id": child.id,
            "name": child.name,
            "age": child.age,
            "safety_tier": child.safety_tier,
            "total_minutes": total_minutes,
            "daily_limit": daily_limit,
            "percentage": percent,
            "top_activities": top_activities,
            "device": active_device,
            "active_code": active_code,
            "is_paired": is_paired
        })

    # Fetch blocked sites
    child_ids = [c.id for c in children]
    blocked_sites = BlockedSite.query.filter(
        (BlockedSite.child_id.in_(child_ids)) | (BlockedSite.child_id.is_(None))
    ).all()

    # Pending access requests
    pending_requests = AccessRequest.query.filter(
        AccessRequest.child_id.in_(child_ids),
        AccessRequest.status == "pending"
    ).order_by(AccessRequest.created_at.desc()).all()

    return render_template(
        "homepage.html",
        children=child_stats,
        blocked_sites=blocked_sites,
        pending_requests=pending_requests,
        current_child=child_stats[0] if child_stats else None
    )


@app.route('/add-child', methods=['POST'])
@login_required
def add_child():
    name = (request.form.get("name") or "").strip()
    age = int(request.form.get("age") or 10)
    safety_tier = request.form.get("safety_tier") or "moderate"
    daily_limit = int(request.form.get("daily_limit") or 120)

    if name:
        child = ChildProfile(
            parent_id=current_user.id,
            name=name,
            age=age,
            safety_tier=safety_tier,
            daily_limit_minutes=daily_limit
        )
        db.session.add(child)
        db.session.commit()
        flash(f"Profile for {name} added!", "success")
    return redirect(url_for("dashboard"))


@app.route('/children/<int:child_id>/pair-code', methods=['POST'])
@login_required
def generate_pair_code(child_id):
    child = db.session.get(ChildProfile, child_id)
    if not child or child.parent_id != current_user.id:
        flash("Child profile not found.", "error")
        return redirect(url_for("dashboard"))

    code = f"{random.randint(100000, 999999)}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    device = Device.query.filter_by(child_id=child.id).first()
    if not device:
        device = Device(
            child_id=child.id,
            device_token=secrets.token_hex(32),
            pairing_code=code,
            code_expires_at=expires_at
        )
        db.session.add(device)
    else:
        device.pairing_code = code
        device.code_expires_at = expires_at

    db.session.commit()
    flash(f"Pairing code for {child.name}: {code} (Valid for 15 minutes)", "info")
    return redirect(url_for("dashboard"))


@app.route('/children/<int:child_id>/rules', methods=['POST'])
@login_required
def add_child_rule(child_id):
    child = db.session.get(ChildProfile, child_id)
    if not child or child.parent_id != current_user.id:
        flash("Unauthorized", "error")
        return redirect(url_for("dashboard"))

    raw_url = request.form.get("url")
    domain = normalize_domain(raw_url)
    if domain:
        existing = BlockedSite.query.filter_by(child_id=child.id, url=domain).first()
        if not existing:
            rule = BlockedSite(
                child_id=child.id,
                url=domain,
                rule_type="block",
                category=classify_domain_quick(domain)
            )
            db.session.add(rule)
            db.session.commit()
            flash(f"Blocked {domain} for {child.name}", "success")
    return redirect(url_for("dashboard"))


@app.route('/children/<int:child_id>/delete-rule', methods=['POST'])
@login_required
def delete_child_rule(child_id):
    child = db.session.get(ChildProfile, child_id)
    if not child or child.parent_id != current_user.id:
        flash("Unauthorized", "error")
        return redirect(url_for("dashboard"))

    domain = normalize_domain(request.form.get("url"))
    rule = BlockedSite.query.filter_by(child_id=child.id, url=domain).first()
    if rule:
        db.session.delete(rule)
        db.session.commit()
        flash(f"Removed {domain} from blocklist", "info")
    return redirect(url_for("dashboard"))


@app.route('/requests/<int:request_id>/resolve', methods=['POST'])
@login_required
def resolve_request(request_id):
    action = request.form.get("action")  # approve or reject
    req_obj = db.session.get(AccessRequest, request_id)
    if req_obj and req_obj.child.parent_id == current_user.id:
        req_obj.status = "approved" if action == "approve" else "rejected"
        req_obj.resolved_at = datetime.now(timezone.utc)

        # If approved, remove from blocked list or add allow rule
        if action == "approve":
            rule = BlockedSite.query.filter_by(child_id=req_obj.child_id, url=req_obj.url).first()
            if rule:
                db.session.delete(rule)

        db.session.commit()
        flash(f"Request for {req_obj.url} {req_obj.status}.", "success")
    return redirect(url_for("dashboard"))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for("home"))


# ==========================================
# REST API (v1) for Browser Extension
# ==========================================

def get_authenticated_device():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        device = Device.query.filter_by(device_token=token, is_active=True).first()
        return device
    return None


@app.route("/api/v1/devices/pair", methods=["POST"])
def api_pair_device():
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()

    if not code:
        return jsonify({"error": "Pairing code required"}), 400

    now = datetime.now(timezone.utc)
    device = Device.query.filter_by(pairing_code=code).first()

    if not device or not device.code_expires_at:
        return jsonify({"error": "Invalid or expired pairing code"}), 400

    # Ensure code_expires_at is timezone-aware for comparison
    expires_at = device.code_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < now:
        return jsonify({"error": "Pairing code expired"}), 400

    # Pairing successful
    device.pairing_code = None  # consume code
    device.is_active = True
    device.last_heartbeat = now
    db.session.commit()

    return jsonify({
        "device_token": device.device_token,
        "child": {
            "id": device.child.id,
            "name": device.child.name,
            "safety_tier": device.child.safety_tier,
            "daily_limit_minutes": device.child.daily_limit_minutes
        }
    }), 200


@app.route("/api/v1/policy", methods=["GET"])
def api_get_policy():
    device = get_authenticated_device()
    if not device:
        return jsonify({"error": "Unauthorized device"}), 401

    child = device.child

    # Aggregate global + child-specific rules
    child_rules = BlockedSite.query.filter(
        (BlockedSite.child_id == child.id) | (BlockedSite.child_id.is_(None))
    ).all()

    blocked = [r.url for r in child_rules if r.rule_type == "block"]

    # If strict tier, automatically include preset categories
    if child.safety_tier == "strict":
        from classifier import CATEGORY_PRESETS
        for cat in ["adult", "gambling", "social"]:
            blocked.extend(CATEGORY_PRESETS.get(cat, []))

    return jsonify({
        "blocked_sites": sorted(list(set(blocked))),
        "child": {
            "id": child.id,
            "name": child.name,
            "safety_tier": child.safety_tier,
            "daily_limit_minutes": child.daily_limit_minutes
        }
    }), 200


@app.route("/api/v1/device/telemetry", methods=["POST"])
def api_receive_telemetry():
    device = get_authenticated_device()
    if not device:
        return jsonify({"error": "Unauthorized device"}), 401

    data = request.get_json(silent=True) or {}
    visits = data.get("visits", [])

    for item in visits:
        domain = normalize_domain(item.get("domain"))
        duration = int(item.get("duration_seconds") or 1)
        if domain:
            log = ActivityLog(
                child_id=device.child_id,
                domain=domain,
                category=classify_domain_quick(domain),
                duration_seconds=duration,
                was_blocked=item.get("was_blocked", False)
            )
            db.session.add(log)

    device.last_heartbeat = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"message": f"Processed {len(visits)} telemetry logs"}), 200


@app.route("/api/v1/device/heartbeat", methods=["POST"])
def api_heartbeat():
    device = get_authenticated_device()
    if device:
        device.last_heartbeat = datetime.now(timezone.utc)
        db.session.commit()
    return jsonify({"status": "ok"}), 200


@app.route("/api/v1/device/request-access", methods=["POST"])
def api_request_access():
    device = get_authenticated_device()
    child_id = device.child_id if device else None

    # Fallback to first child if unpaired
    if not child_id:
        first_child = ChildProfile.query.first()
        if first_child:
            child_id = first_child.id

    if not child_id:
        return jsonify({"error": "No child profile linked"}), 400

    data = request.get_json(silent=True) or {}
    url = normalize_domain(data.get("url"))
    reason = (data.get("reason") or "Child requested access").strip()

    if not url:
        return jsonify({"error": "URL is required"}), 400

    req = AccessRequest(
        child_id=child_id,
        url=url,
        reason=reason
    )
    db.session.add(req)
    db.session.commit()
    return jsonify({"message": "Access request submitted to parent!"}), 201


@app.route("/api/v1/device/classify", methods=["POST"])
def api_classify_content():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "")
    title = data.get("title", "")
    snippet = data.get("snippet", "")

    device = get_authenticated_device()
    tier = device.child.safety_tier if device else "moderate"

    result = classify_page_content(url=url, title=title, snippet=snippet, safety_tier=tier)
    return jsonify(result), 200


# ==========================================
# Legacy & Simple Blocklist APIs (Backward Compatibility)
# ==========================================

@app.route("/blocklist", methods=["GET"])
def get_blocklist():
    blocked_sites = BlockedSite.query.filter_by(rule_type="block").all()
    unique_sites = sorted(list(set(site.url for site in blocked_sites)))
    return jsonify({"blocked_sites": unique_sites}), 200


@app.route("/blocklist", methods=["POST"])
def add_to_blocklist():
    data = request.get_json(silent=True) or {}
    new_url = data.get("url")
    domain = normalize_domain(new_url)

    if domain:
        existing = BlockedSite.query.filter_by(url=domain).first()
        if not existing:
            new_site = BlockedSite(url=domain, rule_type="block", category=classify_domain_quick(domain))
            db.session.add(new_site)
            db.session.commit()
            return jsonify({"message": f"'{domain}' blocked successfully"}), 201
        return jsonify({"message": "Site already blocked"}), 200

    return jsonify({"error": "Invalid URL provided"}), 400


@app.route("/blocklist", methods=["DELETE"])
def remove_from_blocklist():
    data = request.get_json(silent=True) or {}
    url_to_remove = data.get("url")
    domain = normalize_domain(url_to_remove)

    if domain:
        site = BlockedSite.query.filter_by(url=domain).first()
        if site:
            db.session.delete(site)
            db.session.commit()
            return jsonify({"message": f"'{domain}' removed from blocklist"}), 200
        return jsonify({"error": "Site not found"}), 404

    return jsonify({"error": "Invalid request"}), 400


@app.route("/log", methods=["POST"])
def log_visit():
    try:
        data = request.get_json(silent=True) or {}
        visited_site = normalize_domain(data.get("site"))
        duration = int(data.get("duration") or 1)

        if not visited_site:
            return jsonify({"error": "Invalid request format"}), 400

        # Save to database
        first_child = ChildProfile.query.first()
        log = ActivityLog(
            child_id=first_child.id if first_child else None,
            domain=visited_site,
            category=classify_domain_quick(visited_site),
            duration_seconds=duration
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({"message": "Visit logged"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, use_reloader=False)
