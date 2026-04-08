import sqlite3
import bcrypt
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lms.db")

password = bcrypt.hashpw("1234".encode(), bcrypt.gensalt())

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
INSERT OR REPLACE INTO students
(registration_no, name, password_hash, semester, department)
VALUES (?, ?, ?, ?, ?)
""", ("2021-CS-001", "Test Student", password, 7, "CS"))

conn.commit()
conn.close()

print("✅ Test student added to:", DB_PATH)
