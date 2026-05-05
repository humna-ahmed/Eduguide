from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import bcrypt
import os
import secrets
import json

app = Flask(__name__)
CORS(app)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "lms.db")
SESSIONS_FILE = os.path.join(BASE_DIR, "sessions.json")

def load_sessions():
    if os.path.exists(SESSIONS_FILE):
        with open(SESSIONS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_sessions(s):
    with open(SESSIONS_FILE, "w") as f:
        json.dump(s, f)
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
            token = secrets.token_hex(32)
            sessions = load_sessions()
            sessions[token] = str(row[0])
            save_sessions(sessions)
            return jsonify({"success": True, "student_id": row[0], "session_token": token})
        else:
            print("Password incorrect!")  # <-- debug
            return jsonify({"success": False}), 401
    else:
        print("No student found with that registration number!")  # <-- debug
        return jsonify({"success": False}), 401
@app.route("/validate_session", methods=["POST"])
def validate_session():
    data = request.json
    token = data.get("session_token")
    student_id = data.get("student_id")
    sessions = load_sessions()
    if token and sessions.get(token) == str(student_id):
        return jsonify({"valid": True})
    return jsonify({"valid": False}), 401

@app.route("/logout", methods=["POST"])
def logout():
    data = request.json
    token = data.get("session_token")
    sessions = load_sessions()
    if token and token in sessions:
        del sessions[token]
    save_sessions(sessions)
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=False, use_reloader=False)