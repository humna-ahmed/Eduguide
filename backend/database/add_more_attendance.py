import sqlite3, os
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lms.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT student_id FROM students")
students = [s[0] for s in cur.fetchall()]

cur.execute("SELECT course_id FROM courses")
courses = [c[0] for c in cur.fetchall()]

for student_id in students:
    for course_id in courses:
        attended = random.randint(20,30)
        total = 30
        cur.execute("""
        INSERT OR REPLACE INTO attendance (student_id, course_id, classes_attended, total_classes)
        VALUES (?, ?, ?, ?)
        """, (student_id, course_id, attended, total))

conn.commit()
conn.close()
print("✅ Added attendance for all students")
