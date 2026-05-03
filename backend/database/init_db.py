import sqlite3
import os
import bcrypt
import random
from datetime import datetime, timedelta

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lms.db")
random.seed(99) # For reproducibility

# Grade Scale
GRADE_SCALE = [
    (85, "A",  4.00), (80, "A-", 3.67), (75, "B+", 3.33),
    (71, "B",  3.00), (68, "B-", 2.67), (64, "C+", 2.33),
    (60, "C",  2.00), (57, "C-", 1.67), (53, "D+", 1.33),
    (50, "D",  1.00), (0,  "F",  0.00),
]

def get_grade(pct):
    for threshold, grade, gp in GRADE_SCALE:
        if pct >= threshold: return grade, gp
    return "F", 0.00

# Course Data
SEM4_COURSES = [
    ("Operating Systems", 3),
    ("Database Management Systems", 3),
    ("Software Design and Architecture", 3),
    ("Design and Analysis of Algorithms", 2),
    ("Engineering Management", 1),
]

HISTORICAL_COURSES = {
    1: [("Introduction to Computing", 3), ("Calculus I", 3), ("English Composition", 2), ("Islamic Studies", 2), ("Pakistan Studies", 2)],
    2: [("Object Oriented Programming", 3), ("Calculus II", 3), ("Digital Logic Design", 2), ("Technical Writing", 2), ("Linear Algebra", 2)],
    3: [("Data Structures & Algorithms", 3), ("Discrete Mathematics", 3), ("Computer Organization", 2), ("Probability & Statistics", 2), ("Professional Ethics", 2)],
}

COURSE_OUTLINES = {
    "Operating Systems": ["An Overview of Computer System", "Operating System as a Resource Manager", "Process States, Creation and Termination", "Process Control Structures", "Types of Processor Scheduling", "Uni-processor Scheduling (Part I)", "Uni-processor Scheduling (Part II)", "Multi-threading, Thread Functionality", "Concurrency: Mutual Exclusion and Synchronization – I", "Concurrency: Mutual Exclusion and Synchronization – II", "Concurrency: Deadlock and Starvation – I", "Concurrency: Deadlock and Starvation – II", "Memory Management - I", "Memory Management - II", "Memory Management - III", "Course Revision"],
    "Database Management Systems": ["Database Systems", "Database Systems: Design, Implementation, and Management", "The Relational Database Model", "The Relational Model", "Relational Operators", "Relational Algebra", "ER Diagram Examples", "Advanced Data Modeling", "ER Notation", "ER Exercise", "Normalization of Database Tables", "Normalization Exercise", "Transactions", "Concurrency Control", "Recovery System", "Distributed Databases and NoSQL"],
    "Software Design and Architecture": ["What is Software Architecture & Software Design", "Software Design Principles with UML", "System Design & Software Architecture; Object Design, Mapping Design to Code", "Functional Design; UI Design; Web Applications Design", "Web Application – N-Tier MVC Load Balancing", "Design Pattern, Creational Pattern", "Structural Pattern", "Behavioral Pattern", "Interactive Systems with MVC Architecture; Software Reuse", "Architecture Description Languages (ADLs)", "Architectural Design Patterns", "Architectural Design Issues", "Quality Tactics", "Architectural Evaluation Technique", "Software Quality Attributes", "Case Studies and Review"],
    "Design and Analysis of Algorithms": ["Introduction", "Time and Space Complexity", "Recursive Functions, Master Theorem and its Complexity", "Hashing", "Sorting", "Divide and Conquer", "Back Tracking", "Hashing Analysis", "Dynamic Programming, Combination Problem, Make Change Problem", "Dynamic Programming (Advanced)", "Chain Matrix Multiplication and LCS", "Longest Common Sequence", "Dijkstra Algorithm", "Branch and Bound Algorithm", "Pattern Matching", "Knapsack 0/1 Problem – Greedy Algorithm"],
    "Engineering Management": ["Introduction to Engineering Management", "Organization Strategy and Project Selection", "Organization Structure and Culture", "Introduction to Project Management", "Project Management", "Controlling in Management", "Coordinating in Management", "Managing Research and Development", "Managing Engineering Design I", "Managing Engineering Design II", "Project Scheduling and Resource Allocation", "Project Costing", "Leadership", "Intellectual Property", "Quality Management System (QMS)", "Energy Management System (EMS)"]
}

STUDENT_NAMES = [
    "Muhammad Ahmed", "Ali Hassan", "Omar Farooq", "Usman Ghani", "Hamza Ali", "Bilal Khan", "Saad Malik", "Zain ul Abideen", "Hasan Raza", "Hussain Ali",
    "Abdullah Shah", "Abdur Rehman", "Ibrahim Khalil", "Ismail Noor", "Yusuf Siddiqui", "Ayesha Fatima", "Mariam Bibi", "Fatima Zahra", "Zainab Bano", "Sadia Khan",
    "Hina Tariq", "Sara Ahmed", "Nadia Ali", "Rabia Basri", "Sumaira Malik", "Khansa Javed", "Aleena Hassan", "Eman Sheikh", "Laiba Akhtar", "Hira Naeem"
]

PROFILES = {
    "Excellent": {"lo": 0.85, "hi": 0.98},
    "Good":      {"lo": 0.72, "hi": 0.84},
    "Average":   {"lo": 0.60, "hi": 0.71},
    "Poor":      {"lo": 0.52, "hi": 0.59}, # Adjusted to ensure > 50%
    "Very Poor": {"lo": 0.50, "hi": 0.55}, # Floor set at 50%
}

PROFILE_DIST = (["Excellent"] * 6 + ["Good"] * 8 + ["Average"] * 8 + ["Poor"] * 5 + ["Very Poor"] * 3)
random.shuffle(PROFILE_DIST)
STUDENT_PROFILES = {name: PROFILE_DIST[i] for i, name in enumerate(STUDENT_NAMES)}

def gen_marks(profile, max_val):
    lo, hi = PROFILES[profile]["lo"], PROFILES[profile]["hi"]
    return round(random.uniform(lo * max_val, hi * max_val), 1)

def setup_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 1. CORE TABLES
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS students (
        student_id INTEGER PRIMARY KEY AUTOINCREMENT,
        registration_no TEXT UNIQUE, name TEXT, password_hash BLOB, semester INTEGER, department TEXT
    );
    CREATE TABLE IF NOT EXISTS courses (
        course_id INTEGER PRIMARY KEY AUTOINCREMENT, course_name TEXT UNIQUE, credit_hours INTEGER DEFAULT 3
    );
    CREATE TABLE IF NOT EXISTS quizzes (
        quiz_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, course_id INTEGER, 
        quiz_name TEXT, marks_obtained REAL, max_marks REAL, semester INTEGER DEFAULT 4,
        FOREIGN KEY(student_id) REFERENCES students(student_id), FOREIGN KEY(course_id) REFERENCES courses(course_id)
    );
    CREATE TABLE IF NOT EXISTS assignments (
        assignment_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, course_id INTEGER, 
        assignment_name TEXT, marks_obtained REAL, max_marks REAL, semester INTEGER DEFAULT 4,
        FOREIGN KEY(student_id) REFERENCES students(student_id), FOREIGN KEY(course_id) REFERENCES courses(course_id)
    );
    CREATE TABLE IF NOT EXISTS marks (
        mark_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, course_id INTEGER, 
        midterm REAL, final REAL, sessional REAL, semester INTEGER DEFAULT 4,
        FOREIGN KEY(student_id) REFERENCES students(student_id), FOREIGN KEY(course_id) REFERENCES courses(course_id)
    );
    CREATE TABLE IF NOT EXISTS attendance (
        attendance_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, course_id INTEGER, 
        classes_attended INTEGER, total_classes INTEGER, semester INTEGER DEFAULT 4,
        FOREIGN KEY(student_id) REFERENCES students(student_id), FOREIGN KEY(course_id) REFERENCES courses(course_id)
    );
    CREATE TABLE IF NOT EXISTS sessions (
        session_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, 
        session_token TEXT NOT NULL UNIQUE, expires_at TIMESTAMP NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(student_id) REFERENCES students(student_id)
    );
    CREATE TABLE IF NOT EXISTS lectures (
        lecture_id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER NOT NULL, lecture_number INTEGER NOT NULL,
        lecture_title TEXT NOT NULL, file_name TEXT NOT NULL, file_data BLOB NOT NULL, file_type TEXT NOT NULL,
        file_size INTEGER, uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(course_id) REFERENCES courses(course_id), UNIQUE(course_id, lecture_number)
    );
    CREATE TABLE IF NOT EXISTS course_outlines (
        outline_id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER NOT NULL, 
        topic_number INTEGER NOT NULL, topic_name TEXT NOT NULL,
        FOREIGN KEY(course_id) REFERENCES courses(course_id)
    );
    CREATE TABLE IF NOT EXISTS historical_courses (
        hc_id INTEGER PRIMARY KEY AUTOINCREMENT, semester INTEGER NOT NULL, course_name TEXT NOT NULL, credit_hours INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS historical_marks (
        hm_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, semester INTEGER NOT NULL, 
        course_name TEXT NOT NULL, credit_hours INTEGER NOT NULL,
        quiz1 REAL, quiz2 REAL, quiz3 REAL, quiz4 REAL, assign1 REAL, assign2 REAL, assign3 REAL, assign4 REAL,
        midterm REAL, final_exam REAL, ia_obtained REAL, ia_pct REAL, total_obtained REAL, total_pct REAL,
        FOREIGN KEY(student_id) REFERENCES students(student_id)
    );
    CREATE TABLE IF NOT EXISTS semester_summary (
        summary_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, semester INTEGER NOT NULL, 
        sem_ia_pct REAL, sem_total_pct REAL, gpa REAL, grade TEXT,
        UNIQUE(student_id, semester), FOREIGN KEY(student_id) REFERENCES students(student_id)
    );
    """)
    conn.commit()
    return conn

def run_migration():
    conn = setup_database()
    cur = conn.cursor()
    print("🚀 Starting Unified Migration...")

    # --- STEP 2: COURSES & OUTLINES ---
    sem4_course_map = {}
    for name, ch in SEM4_COURSES:
        cur.execute("INSERT OR IGNORE INTO courses (course_name, credit_hours) VALUES (?,?)", (name, ch))
        cur.execute("SELECT course_id FROM courses WHERE course_name=?", (name,))
        cid = cur.fetchone()[0]
        sem4_course_map[name] = (cid, ch)
        
        # Insert Outlines
        cur.execute("DELETE FROM course_outlines WHERE course_id=?", (cid,))
        for i, topic in enumerate(COURSE_OUTLINES.get(name, []), 1):
            cur.execute("INSERT INTO course_outlines (course_id, topic_number, topic_name) VALUES (?,?,?)", (cid, i, topic))

    # --- STEP 3: STUDENTS ---
    password_hash = bcrypt.hashpw("1234".encode(), bcrypt.gensalt())
    for i, name in enumerate(STUDENT_NAMES, 1):
        reg = f"2024-CS-{i:03d}"
        cur.execute("INSERT OR IGNORE INTO students (registration_no, name, password_hash, semester, department) VALUES (?,?,?,4,'CS')",
                    (reg, name, password_hash))
    
    cur.execute("SELECT student_id, name FROM students WHERE semester=4")
    students = cur.fetchall()

    # --- STEP 4: SEEDING MARKS (Sems 1-4) ---
    for sid, name in students:
        profile = STUDENT_PROFILES[name]
        
        # Historical (1-3)
        for sem in [1, 2, 3]:
            course_results = []
            for cname, ch in HISTORICAL_COURSES[sem]:
                # Generate components
                qs = [gen_marks(profile, 2.5) for _ in range(4)]
                asgn = [gen_marks(profile, 5.0) for _ in range(4)]
                mid = gen_marks(profile, 20.0)
                
                ia = round(sum(qs) + sum(asgn) + mid, 1)
                
                # Rule: Total >= 50 and Final <= 50
                target_total = gen_marks(profile, 100.0)
                if target_total < 50: target_total = random.uniform(50.5, 60.0)
                
                final = round(target_total - ia, 1)
                # Cap final at 50, adjust IA if necessary
                if final > 50:
                    final = 50.0
                    ia = round(target_total - 50.0, 1)
                
                total = round(ia + final, 1)
                ia_pct = round((ia / 50.0) * 100, 2)
                total_pct = round((total / 100.0) * 100, 2)

                cur.execute("""INSERT INTO historical_marks 
                    (student_id, semester, course_name, credit_hours, quiz1, quiz2, quiz3, quiz4, assign1, assign2, assign3, assign4, midterm, final_exam, ia_obtained, ia_pct, total_obtained, total_pct)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (sid, sem, cname, ch, *qs, *asgn, mid, final, ia, ia_pct, total, total_pct))
                
                course_results.append({"ch": ch, "ia_pct": ia_pct, "total_pct": total_pct})

            # Semester Summary
            total_ch = sum(c["ch"] for c in course_results)
            avg_ia = round(sum(c["ia_pct"] * c["ch"] for c in course_results) / total_ch, 2)
            avg_tot = round(sum(c["total_pct"] * c["ch"] for c in course_results) / total_ch, 2)
            grade, gpa = get_grade(avg_tot)
            
            cur.execute("INSERT OR REPLACE INTO semester_summary (student_id, semester, sem_ia_pct, sem_total_pct, gpa, grade) VALUES (?,?,?,?,?,?)",
                        (sid, sem, avg_ia, avg_tot, gpa, grade))

        # Current (Sem 4)
        for cname, (cid, ch) in sem4_course_map.items():
            qs = [gen_marks(profile, 2.5) for _ in range(4)]
            asgn = [gen_marks(profile, 5.0) for _ in range(4)]
            mid = gen_marks(profile, 20.0)
            final = gen_marks(profile, 50.0)
            sess = round(sum(qs) + sum(asgn) + mid, 1)

            for i, val in enumerate(qs, 1):
                cur.execute("INSERT INTO quizzes (student_id, course_id, quiz_name, marks_obtained, max_marks, semester) VALUES (?,?,?,?,2.5,4)", (sid, cid, f"Quiz {i}", val))
            for i, val in enumerate(asgn, 1):
                cur.execute("INSERT INTO assignments (student_id, course_id, assignment_name, marks_obtained, max_marks, semester) VALUES (?,?,?,?,5.0,4)", (sid, cid, f"Assignment {i}", val))
            
            cur.execute("INSERT INTO marks (student_id, course_id, midterm, final, sessional, semester) VALUES (?,?,?,?,?,4)", (sid, cid, mid, final, sess))
            
            att = random.randint(22, 30) if profile in ["Excellent", "Good"] else random.randint(15, 25)
            cur.execute("INSERT INTO attendance (student_id, course_id, classes_attended, total_classes, semester) VALUES (?,?,?,30,4)", (sid, cid, att))

    conn.commit()
    print("✅ Database successfully generated with strictly consistent historical data.")
    conn.close()

if __name__ == "__main__":
    if os.path.exists(DB_PATH): os.remove(DB_PATH) # Start fresh
    run_migration()