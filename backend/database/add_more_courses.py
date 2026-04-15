import sqlite3, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lms.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# List of new courses with credit hours
new_courses = [
    ("Data Structures", 3),
    ("Operating Systems", 3),
    ("Linear Algebra", 3),
    ("Economics", 2)
]

for course_name, credit_hours in new_courses:
    cur.execute("INSERT OR IGNORE INTO courses (course_name, credit_hours) VALUES (?, ?)", 
                (course_name, credit_hours))

conn.commit()
conn.close()
print("✅ Added new courses with credit hours")