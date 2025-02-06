from flask import Flask, render_template

# Initialize Flask app
app = Flask(__name__)

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/block")
def block():
    return render_template("block.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/signup")
def signup():
    return render_template("signup.html")
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)