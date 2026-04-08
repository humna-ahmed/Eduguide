import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lms.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Add courses
courses = ["Calculus", "Functional English", "Physics", "Programming"]
for c in courses:
    cur.execute("INSERT OR IGNORE INTO courses (course_name) VALUES (?)", (c,))

# Get student_id
cur.execute("SELECT student_id FROM students WHERE registration_no = ?", ("2021-CS-001",))
student_id = cur.fetchone()[0]

# Add ONLY midterm marks for this student (final is NULL/not yet)
for course_id in range(1, 5):
    cur.execute("""
    INSERT OR REPLACE INTO marks (student_id, course_id, midterm)
    VALUES (?, ?, ?)
    """, (student_id, course_id, 15))  # Only midterm, final is NULL

# Add quiz marks for this student (4 quizzes per course, each out of 2.5)
quiz_data = []
quiz_scores = [2.0, 2.3, 1.8, 2.2]  # Example scores out of 2.5 each
for course_id in range(1, 5):  # 4 courses
    for quiz_num in range(1, 5):  # 4 quizzes
        quiz_data.append((
            student_id, course_id, f"Quiz {quiz_num}", 
            quiz_scores[quiz_num-1],  # marks_obtained (out of 2.5)
            2.5  # max_marks
        ))

for data in quiz_data:
    cur.execute("""
    INSERT OR REPLACE INTO quizzes (student_id, course_id, quiz_name, marks_obtained, max_marks)
    VALUES (?, ?, ?, ?, ?)
    """, data)

# Add assignment marks for this student (4 assignments per course, each out of 5)
assignment_data = []
assign_scores = [4.0, 4.5, 3.8, 4.2]  # Example scores out of 5 each
for course_id in range(1, 5):  # 4 courses
    for assign_num in range(1, 5):  # 4 assignments
        assignment_data.append((
            student_id, course_id, f"Assignment {assign_num}",
            assign_scores[assign_num-1],  # marks_obtained (out of 5)
            5  # max_marks
        ))

for data in assignment_data:
    cur.execute("""
    INSERT OR REPLACE INTO assignments (student_id, course_id, assignment_name, marks_obtained, max_marks)
    VALUES (?, ?, ?, ?, ?)
    """, data)

conn.commit()
conn.close()
print("✅ Test courses and marks added with separate quiz/assignment tables")