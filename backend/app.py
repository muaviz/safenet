from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS  # Allow cross-origin requests (for extension)
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Enable CORS for all routes

# Configure SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config['SECRET_KEY'] = 'your_secret_key'  # Change this!
db = SQLAlchemy(app)

# Define database model for blocked sites
class BlockedSite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(255), unique=True, nullable=False)

# Create tables
with app.app_context():
    db.create_all()

# Initialize Extensions
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "home"  # Redirect to home if not logged in

# User Model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)

# Load user for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Home Route (Handles both Login & Signup)
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'login':  # LOGIN FORM
            email = request.form.get('email')
            password = request.form.get('password')

            user = User.query.filter_by(email=email).first()
            if user and bcrypt.check_password_hash(user.password, password):
                login_user(user)
                flash("Login successful!", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Invalid email or password", "danger")

        elif form_type == 'signup':  # SIGNUP FORM
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            if password != confirm_password:
                flash("Passwords do not match!", "danger")
                return render_template("landing.html")

            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash("Email already registered!", "danger")
                return render_template("landing.html")

            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
            new_user = User(name=name, email=email, password=hashed_pw)
            db.session.add(new_user)
            db.session.commit()

            flash("Account created successfully! Please log in.", "success")
            return render_template("landing.html")

    return render_template("landing.html")

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template("homepage.html")

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for("home"))





@app.route("/block")
def block():
    return render_template("block.html")
# --------- Blocklist Management API ---------
@app.route("/blocklist", methods=["GET"])
def get_blocklist():
    """Return the list of blocked sites."""
    blocked_sites = BlockedSite.query.all()
    return jsonify({"blocked_sites": [site.url for site in blocked_sites]}), 200

@app.route("/blocklist", methods=["POST"])
def add_to_blocklist():
    """Add a site to the blocklist."""
    data = request.json
    new_url = data.get("url")

    if new_url:
        if BlockedSite.query.filter_by(url=new_url).first():
            return jsonify({"message": "Site already blocked"}), 400

        new_site = BlockedSite(url=new_url)
        db.session.add(new_site)
        db.session.commit()
        return jsonify({"message": "Site blocked successfully"}), 201
    
    return jsonify({"error": "Invalid request"}), 400

@app.route("/blocklist", methods=["DELETE"])
def remove_from_blocklist():
    """Remove a site from the blocklist."""
    data = request.json
    url_to_remove = data.get("url")

    if url_to_remove:
        site = BlockedSite.query.filter_by(url=url_to_remove).first()
        if site:
            db.session.delete(site)
            db.session.commit()
            return jsonify({"message": "Site removed from blocklist"}), 200
        return jsonify({"error": "Site not found"}), 404

    return jsonify({"error": "Invalid request"}), 400

# --------- Logging API ---------
@app.route("/log", methods=["POST"])
def log_visit():
    """Log site visits from the extension."""
    try:
        data = request.get_json()  # Ensure correct JSON format
        if not data or "site" not in data:
            return jsonify({"error": "Invalid request format"}), 400

        visited_site = data["site"]
        print(f"Visit logged: {visited_site}")  # Debugging output

        return jsonify({"message": "Visit logged"}), 200
    except Exception as e:
        print("Error logging visit:", str(e))
        return jsonify({"error": "Internal server error"}), 500


# Run Server
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables
    app.run(debug=True, use_reloader=False)
