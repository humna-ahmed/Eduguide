import sqlite3, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lms.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# student_id
cur.execute("SELECT student_id FROM students WHERE registration_no = ?", ("2021-CS-001",))
student_id = cur.fetchone()[0]

# Add attendance for 4 courses
attendances = [
    (student_id, 1, 28, 30),
    (student_id, 2, 25, 30),
    (student_id, 3, 27, 30),
    (student_id, 4, 29, 30),
]

for a in attendances:
    cur.execute("""
    INSERT OR REPLACE INTO attendance (student_id, course_id, classes_attended, total_classes)
    VALUES (?, ?, ?, ?)
    """, a)

conn.commit()
conn.close()
print("✅ Test attendance data added")
