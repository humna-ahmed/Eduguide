import sqlite3, os, bcrypt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lms.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# List of students (registration_no, name, password, semester, department)
students = [
    ("2021-CS-002", "Alice Khan", "1234", 7, "CS"),
    ("2021-CS-003", "Bob Ahmed", "1234", 7, "CS"),
    ("2021-EC-001", "Charlie Lee", "1234", 7, "EC"),
]

for reg_no, name, password, sem, dept in students:
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    cur.execute("""
    INSERT OR IGNORE INTO students (registration_no, name, password_hash, semester, department)
    VALUES (?, ?, ?, ?, ?)
    """, (reg_no, name, password_hash, sem, dept))

conn.commit()
conn.close()
print("✅ Added new students")
