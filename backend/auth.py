from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import bcrypt
import os

app = Flask(__name__)
CORS(app)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "lms.db")
@app.route("/")
def index():
    login_ui_dir = os.path.join(BASE_DIR, "..", "ui")
    return send_from_directory(login_ui_dir, "login.html")

@app.route("/styles.css")
def styles():
    login_ui_dir = os.path.join(BASE_DIR, "..", "ui")
    return send_from_directory(login_ui_dir, "styles.css")
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    print("Login attempt received:", data)  # <-- debug
    reg = data.get("registration_no")
    password = data.get("password")
    print("Registration No:", reg, "Password entered:", password)  # <-- debug
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT student_id, password_hash, registration_no FROM students WHERE registration_no = ?", (reg,))
    row = cur.fetchone()

    print("DB row fetched:", row)  # <-- debug

    conn.close()

    if row:
        stored_hash = row[1]
        print("Stored hash type:", type(stored_hash), stored_hash)
        print("Password encoded type:", type(password.encode()), password.encode())

        if bcrypt.checkpw(password.encode(), stored_hash):
            print("Password correct!")  # <-- debug
            return jsonify({"success": True, "student_id": row[0]})
        else:
            print("Password incorrect!")  # <-- debug
            return jsonify({"success": False}), 401
    else:
        print("No student found with that registration number!")  # <-- debug
        return jsonify({"success": False}), 401

if __name__ == "__main__":
    app.run(debug=False, use_reloader=False)