import sqlite3, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lms.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# List of new courses
new_courses = ["Data Structures", "Operating Systems", "Linear Algebra", "Economics"]

for course in new_courses:
    cur.execute("INSERT OR IGNORE INTO courses (course_name) VALUES (?)", (course,))

conn.commit()
conn.close()
print("✅ Added new courses")
