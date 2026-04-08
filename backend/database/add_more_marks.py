import sqlite3
import os
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lms.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Fetch all students
cur.execute("SELECT student_id, registration_no FROM students")
students = cur.fetchall()

# Fetch all courses
cur.execute("SELECT course_id FROM courses")
courses = [c[0] for c in cur.fetchall()]

# Assign marks for each student in each course
for student_id, reg_no in students:
    for course_id in courses:
        # Add ONLY midterm marks (final is NULL/not yet)
        cur.execute("""
        INSERT OR REPLACE INTO marks (student_id, course_id, midterm)
        VALUES (?, ?, ?)
        """, (
            student_id, course_id, 
            random.uniform(12, 20)  # midterm out of 20
            # final is NULL - will be predicted by chatbot
        ))
        
        # Add 4 quizzes (each out of 2.5)
        for quiz_num in range(1, 5):
            cur.execute("""
            INSERT OR REPLACE INTO quizzes (student_id, course_id, quiz_name, marks_obtained, max_marks)
            VALUES (?, ?, ?, ?, ?)
            """, (
                student_id, course_id, f"Quiz {quiz_num}",
                random.uniform(1.5, 2.5),  # quiz marks out of 2.5
                2.5
            ))
        
        # Add 4 assignments (each out of 5)
        for assign_num in range(1, 5):
            cur.execute("""
            INSERT OR REPLACE INTO assignments (student_id, course_id, assignment_name, marks_obtained, max_marks)
            VALUES (?, ?, ?, ?, ?)
            """, (
                student_id, course_id, f"Assignment {assign_num}",
                random.uniform(3, 5),  # assignment marks out of 5
                5
            ))

conn.commit()
conn.close()
print("✅ Added marks for all students with separate quiz/assignment tables")