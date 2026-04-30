import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lms.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# --- Check all students and their semesters ---
print("=== STUDENTS ===")
cur.execute("SELECT student_id, registration_no, name, semester, department FROM students")
for row in cur.fetchall():
    print(row)

# --- Check all courses ---
print("\n=== COURSES ===")
cur.execute("SELECT * FROM courses")
for row in cur.fetchall():
    print(row)

# --- Count records per student in each table ---
for table, id_col in [
    ("quizzes", "student_id"),
    ("assignments", "student_id"),
    ("marks", "student_id"),
    ("attendance", "student_id"),
]:
    print(f"\n=== {table.upper()} (count per student) ===")
    cur.execute(f"""
        SELECT s.name, s.semester, COUNT(*) as record_count
        FROM {table} t
        JOIN students s ON s.student_id = t.{id_col}
        GROUP BY t.student_id
    """)
    rows = cur.fetchall()
    if rows:
        for row in rows:
            print(row)
    else:
        print("No data found.")

conn.close()
