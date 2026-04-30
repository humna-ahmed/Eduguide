import sqlite3
import os
import bcrypt
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lms.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("📚 Starting to add 30 students with complete data...")

# =============================================
# 1. FIRST, ENSURE 5 COURSES EXIST WITH CREDIT HOURS
# =============================================
courses_data = [
    ("Operating Systems", 3),
    ("Database Management Systems", 3),
    ("Software Design and Architecture", 3),
    ("Design Analysis of Algorithms", 2),
    ("Engineering Management", 1)
]

print("\n📖 Setting up courses...")
for course_name, credit_hours in courses_data:
    cur.execute("""
        INSERT OR IGNORE INTO courses (course_name, credit_hours)
        VALUES (?, ?)
    """, (course_name, credit_hours))
    print(f"  ✅ {course_name} ({credit_hours} credit hours)")

# Get course IDs after insertion
cur.execute("SELECT course_id, course_name, credit_hours FROM courses WHERE course_name IN (?, ?, ?, ?, ?)", 
            tuple([c[0] for c in courses_data]))
courses = cur.fetchall()
course_ids = [c[0] for c in courses]
course_names = {c[0]: c[1] for c in courses}
course_credits = {c[0]: c[2] for c in courses}

print(f"\n✅ Total courses available: {len(courses)}")

# =============================================
# 2. GENERATE 30 MUSLIM STUDENTS
# =============================================
muslim_names = [
    "Muhammad Ahmed", "Ali Hassan", "Omar Farooq", "Usman Ghani", "Hamza Ali",
    "Bilal Khan", "Saad Malik", "Zain ul Abideen", "Hasan Raza", "Hussain Ali",
    "Abdullah Shah", "Abdur Rehman", "Ibrahim Khalil", "Ismail Noor", "Yusuf Siddiqui",
    "Ayesha Fatima", "Mariam Bibi", "Fatima Zahra", "Zainab Bano", "Sadia Khan",
    "Hina Tariq", "Sara Ahmed", "Nadia Ali", "Rabia Basri", "Sumaira Malik",
    "Khansa Javed", "Aleena Hassan", "Eman Sheikh", "Laiba Akhtar", "Hira Naeem"
]

# Student performance categories
performance_categories = {
    "Excellent": {"quiz_range": (2.0, 2.5), "assign_range": (4.0, 5.0), "mid_range": (16, 20), "attendance_range": (25, 30)},
    "Good": {"quiz_range": (1.8, 2.3), "assign_range": (3.5, 4.5), "mid_range": (14, 18), "attendance_range": (22, 28)},
    "Average": {"quiz_range": (1.5, 2.0), "assign_range": (3.0, 4.0), "mid_range": (12, 16), "attendance_range": (20, 25)},
    "Poor": {"quiz_range": (1.0, 1.5), "assign_range": (2.0, 3.0), "mid_range": (8, 12), "attendance_range": (15, 20)},
    "Very Poor": {"quiz_range": (0.5, 1.0), "assign_range": (1.0, 2.0), "mid_range": (5, 8), "attendance_range": (10, 15)}
}

# Distribution: 6 Excellent, 8 Good, 8 Average, 5 Poor, 3 Very Poor
performance_distribution = ["Excellent"] * 6 + ["Good"] * 8 + ["Average"] * 8 + ["Poor"] * 5 + ["Very Poor"] * 3
random.shuffle(performance_distribution)

print(f"\n👥 Generating 30 students...")

students_to_add = []
for i, name in enumerate(muslim_names[:30], start=1):
    registration_no = f"2024-CS-{i:03d}"
    semester = 4  # Same semester for all
    department = "CS"
    password_hash = bcrypt.hashpw("1234".encode(), bcrypt.gensalt())
    performance = performance_distribution[i-1]
    
    students_to_add.append({
        "reg_no": registration_no,
        "name": name,
        "password_hash": password_hash,
        "semester": semester,
        "department": department,
        "performance": performance
    })

# Insert students
for student in students_to_add:
    cur.execute("""
        INSERT OR IGNORE INTO students (registration_no, name, password_hash, semester, department)
        VALUES (?, ?, ?, ?, ?)
    """, (student["reg_no"], student["name"], student["password_hash"], 
          student["semester"], student["department"]))

print(f"✅ Added {len(students_to_add)} students")

# Get all student IDs
cur.execute("SELECT student_id, registration_no FROM students WHERE semester = 4 AND department = 'CS'")
all_students = cur.fetchall()
print(f"✅ Retrieved {len(all_students)} student records")

# =============================================
# 3. ADD MARKS FOR EACH STUDENT (VARIED PERFORMANCE)
# =============================================
print("\n📝 Adding marks for all students...")

for student_id, reg_no in all_students:
    # Find student's performance category
    student_data = next((s for s in students_to_add if s["reg_no"] == reg_no), None)
    if not student_data:
        continue
    
    performance = student_data["performance"]
    ranges = performance_categories[performance]
    
    for course_id in course_ids:
        # Add midterm marks
        midterm_score = round(random.uniform(ranges["mid_range"][0], ranges["mid_range"][1]), 1)
        cur.execute("""
            INSERT OR REPLACE INTO marks (student_id, course_id, midterm)
            VALUES (?, ?, ?)
        """, (student_id, course_id, midterm_score))
        
        # Add 4 quizzes
        quiz_names = ["Quiz 1", "Quiz 2", "Quiz 3", "Quiz 4"]
        for quiz_num, quiz_name in enumerate(quiz_names, 1):
            quiz_score = round(random.uniform(ranges["quiz_range"][0], ranges["quiz_range"][1]), 1)
            cur.execute("""
                INSERT OR REPLACE INTO quizzes (student_id, course_id, quiz_name, marks_obtained, max_marks)
                VALUES (?, ?, ?, ?, ?)
            """, (student_id, course_id, quiz_name, quiz_score, 2.5))
        
        # Add 4 assignments
        assign_names = ["Assignment 1", "Assignment 2", "Assignment 3", "Assignment 4"]
        for assign_num, assign_name in enumerate(assign_names, 1):
            assign_score = round(random.uniform(ranges["assign_range"][0], ranges["assign_range"][1]), 1)
            cur.execute("""
                INSERT OR REPLACE INTO assignments (student_id, course_id, assignment_name, marks_obtained, max_marks)
                VALUES (?, ?, ?, ?, ?)
            """, (student_id, course_id, assign_name, assign_score, 5))
        
        # Add attendance
        attended = random.randint(ranges["attendance_range"][0], ranges["attendance_range"][1])
        total = 30
        cur.execute("""
            INSERT OR REPLACE INTO attendance (student_id, course_id, classes_attended, total_classes)
            VALUES (?, ?, ?, ?)
        """, (student_id, course_id, attended, total))
    
    print(f"  ✅ {student_data['name']} ({performance} student) - Added marks for all courses")

# =============================================
# 4. VERIFICATION & SUMMARY
# =============================================
print("\n" + "="*60)
print("📊 DATA ADDITION SUMMARY")
print("="*60)

# Count students
cur.execute("SELECT COUNT(*) FROM students WHERE semester = 4 AND department = 'CS'")
student_count = cur.fetchone()[0]
print(f"\n👥 Total Students Added: {student_count}")

# Count courses
cur.execute("SELECT COUNT(*) FROM courses")
course_count = cur.fetchone()[0]
print(f"📚 Total Courses: {course_count}")

# Show courses with credit hours
print("\n📖 Course Details:")
cur.execute("SELECT course_name, credit_hours FROM courses ORDER BY course_id")
for course_name, credit_hours in cur.fetchall():
    print(f"  - {course_name}: {credit_hours} credit hour(s)")

# Show performance distribution
print("\n📈 Performance Distribution:")
performance_count = {}
for student in students_to_add:
    perf = student["performance"]
    performance_count[perf] = performance_count.get(perf, 0) + 1

for perf, count in performance_count.items():
    print(f"  - {perf}: {count} students")

# Show sample student marks
print("\n🎓 Sample Student Performance (First 5 students):")
cur.execute("""
    SELECT s.name, s.registration_no, 
           (SELECT SUM(marks_obtained) FROM quizzes WHERE student_id = s.student_id AND course_id = 1) as quiz_total,
           (SELECT SUM(marks_obtained) FROM assignments WHERE student_id = s.student_id AND course_id = 1) as assign_total,
           (SELECT midterm FROM marks WHERE student_id = s.student_id AND course_id = 1) as midterm
    FROM students s
    WHERE s.semester = 4 AND s.department = 'CS'
    LIMIT 5
""")

for name, reg_no, quiz_total, assign_total, midterm in cur.fetchall():
    quiz_total = quiz_total if quiz_total else 0
    assign_total = assign_total if assign_total else 0
    midterm = midterm if midterm else 0
    total = quiz_total + assign_total + midterm
    percentage = (total / 50) * 100
    print(f"  - {name} ({reg_no}): {total}/50 ({percentage:.1f}%)")

print("\n" + "="*60)
print("✅ ALL 30 STUDENTS ADDED SUCCESSFULLY!")
print("="*60)

conn.commit()
conn.close()