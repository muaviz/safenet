from flask import Flask, render_template, request, jsonify
from flask_cors import CORS  # Allow cross-origin requests (for extension)
import json
import os

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Enable CORS for all routes

# Define blocklist file
BLOCKLIST_FILE = "blocklist.json"

# Ensure blocklist file exists
if not os.path.exists(BLOCKLIST_FILE):
    with open(BLOCKLIST_FILE, "w") as file:
        json.dump({"blocked_sites": []}, file)

# --------- Utility Functions ---------
def load_blocklist():
    """Load blocklist from JSON file."""
    if not os.path.exists(BLOCKLIST_FILE):  # Create file if it doesn't exist
        save_blocklist([])  # Initialize an empty blocklist
    with open(BLOCKLIST_FILE, "r") as file:
        return json.load(file).get("blocked_sites", [])

def save_blocklist(blocklist):
    """Save blocklist to JSON file."""
    try:
        with open(BLOCKLIST_FILE, "w") as file:
            json.dump({"blocked_sites": blocklist}, file, indent=4)
        print("✅ Blocklist successfully saved")  # Debugging
    except Exception as e:
        print(f"❌ Error saving blocklist: {e}")  # Debugging



# --------- Existing Routes ---------
@app.route("/")
# Hirako neeche homepage.html ko test.html kr dena - isse fir test.html run hoga then app.py wapas run kr dena
def home():
    return render_template("homepage.html")

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
    return jsonify({"blocked_sites": load_blocklist()}), 200

@app.route("/blocklist", methods=["POST"])
def add_to_blocklist():
    """Add a site to the blocklist and save to JSON."""
    data = request.json
    new_url = data.get("url")

    if not new_url:
        print("⚠️ Invalid request: No URL provided")  # Debugging
        return jsonify({"error": "Invalid request"}), 400

    blocklist = load_blocklist()
    print(f"🔍 Current Blocklist: {blocklist}")  # Debugging

    if new_url in blocklist:
        print("⚠️ Site already blocked")  # Debugging
        return jsonify({"message": "Site already blocked"}), 400

    blocklist.append(new_url)
    save_blocklist(blocklist)
    print(f"✅ Site blocked: {new_url}")  # Debugging
    return jsonify({"message": "Site blocked successfully"}), 201


@app.route("/blocklist", methods=["DELETE"])
def remove_from_blocklist():
    """Remove a site from the blocklist."""
    data = request.json
    url_to_remove = data.get("url")

    if url_to_remove:
        blocklist = load_blocklist()
        if url_to_remove in blocklist:
            blocklist.remove(url_to_remove)
            save_blocklist(blocklist)
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
