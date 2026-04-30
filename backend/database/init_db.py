import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lms.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Students table
cur.execute("""
CREATE TABLE IF NOT EXISTS students (
    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
    registration_no TEXT UNIQUE,
    name TEXT,
    password_hash BLOB,
    semester INTEGER,
    department TEXT
)
""")

# Courses table with credit_hours
cur.execute("""
CREATE TABLE IF NOT EXISTS courses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_name TEXT UNIQUE,
    credit_hours INTEGER DEFAULT 3
)
""")

# Quizzes table
cur.execute("""
CREATE TABLE IF NOT EXISTS quizzes (
    quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    course_id INTEGER,
    quiz_name TEXT,
    marks_obtained REAL,
    max_marks REAL,
    FOREIGN KEY(student_id) REFERENCES students(student_id),
    FOREIGN KEY(course_id) REFERENCES courses(course_id)
)
""")

# Assignments table
cur.execute("""
CREATE TABLE IF NOT EXISTS assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    course_id INTEGER,
    assignment_name TEXT,
    marks_obtained REAL,
    max_marks REAL,
    FOREIGN KEY(student_id) REFERENCES students(student_id),
    FOREIGN KEY(course_id) REFERENCES courses(course_id)
)
""")

# Marks table
cur.execute("""
CREATE TABLE IF NOT EXISTS marks (
    mark_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    course_id INTEGER,
    midterm REAL,
    final REAL,
    FOREIGN KEY(student_id) REFERENCES students(student_id),
    FOREIGN KEY(course_id) REFERENCES courses(course_id)
)
""")

# Attendance table
cur.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    course_id INTEGER,
    classes_attended INTEGER,
    total_classes INTEGER,
    FOREIGN KEY(student_id) REFERENCES students(student_id),
    FOREIGN KEY(course_id) REFERENCES courses(course_id)
)
""")
# Sessions table
cur.execute("""
CREATE TABLE IF NOT EXISTS sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    session_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES students(student_id)
)
""")
# Lectures table - stores lecture file metadata
cur.execute("""
CREATE TABLE IF NOT EXISTS lectures (
    lecture_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    lecture_number INTEGER NOT NULL,
    lecture_title TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_data BLOB NOT NULL,
    file_type TEXT NOT NULL,
    file_size INTEGER,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(course_id) REFERENCES courses(course_id),
    UNIQUE(course_id, lecture_number)
)
""")
conn.commit()
conn.close()
print("Database initialized with credit_hours at:", DB_PATH)