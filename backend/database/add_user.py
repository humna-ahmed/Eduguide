# Create a temporary script add_user.py
import sqlite3
import bcrypt
import os

DB_PATH = "backend/database/lms.db"  # Adjust path
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Add a test student (adjust registration_no and password)
reg_no = "2021-CS-002"
password = "test123"  # Change this
password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

cur.execute("""
    INSERT OR REPLACE INTO students (registration_no, password_hash, name, semester)
    VALUES (?, ?, ?, ?)
""", (reg_no, password_hash, "Test Student", 5))

conn.commit()
conn.close()
print("Test user added!")