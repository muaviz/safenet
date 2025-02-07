from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS  # Allow cross-origin requests (for extension)

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Enable CORS for all routes

# Configure SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Define database model for blocked sites
class BlockedSite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(255), unique=True, nullable=False)

# Create tables
with app.app_context():
    db.create_all()

# --------- Existing Routes ---------
@app.route("/")
# Hirako neeche homepage.html ko test.html kr dena - isse fir test.html run hoga then app.py wapas run kr dena
def home():
    return render_template("test.html")

@app.route("/block")
def block():
    return render_template("block.html")

@app.route("/login")
def login():
    return render_template("sign-in.html")

@app.route("/signup")
def signup():
    return render_template("sign-up.html")

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


# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
