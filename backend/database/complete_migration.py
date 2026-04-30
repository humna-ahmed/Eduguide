"""
Complete LMS Migration & Seeding Script
========================================

WHAT THIS SCRIPT DOES:
-----------------------
1. SCHEMA CHANGES:
   - Replaces old semester 4 courses (Calculus, DS, etc.) with the 5 correct ones
   - Adds `sessional` column to `marks` table (quiz + assignment + midterm for sem 4)
   - Creates `course_outlines` table with 16 topics per sem-4 course
   - Creates `historical_courses`, `historical_marks`, `semester_summary` tables for sems 1–3

2. SEM 4 DATA FIX:
   - Reseeds all 30 students with correct courses (Operating Systems, DBMS, etc.)
   - Credit hours: OS=3, DBMS=3, SDA=3, DAA=2, EM=1 → total = 12
   - Computes and stores sessional marks per student per course in `marks.sessional`

3. HISTORICAL DATA (Sems 1–3):
   - Generates synthetic but realistic marks for all 30 students
   - Stores weighted semester IA%, total%, GPA, grade in `semester_summary`
   - Each student keeps a consistent performance profile across semesters

4. COURSE OUTLINES:
   - Stores all 16 topics for each of the 5 sem-4 courses in `course_outlines`

MARKS BREAKDOWN (per course):
   - 4 Quizzes × 2.5   = 10 marks
   - 4 Assignments × 5  = 20 marks
   - Midterm             = 20 marks   ← IA = 50 marks total
   - Final               = 50 marks
   - Total               = 100 marks

WEIGHTED % FORMULA (GPA-style in %):
   Weighted % = Σ(course_pct × credit_hours) / Σ(credit_hours)
"""

import sqlite3
import os
import bcrypt
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lms.db")

random.seed(99)

# ── Grading scale ──────────────────────────────────────────────────────────────
GRADE_SCALE = [
    (85, "A",  4.00), (80, "A-", 3.67), (75, "B+", 3.33),
    (71, "B",  3.00), (68, "B-", 2.67), (64, "C+", 2.33),
    (60, "C",  2.00), (57, "C-", 1.67), (53, "D+", 1.33),
    (50, "D",  1.00), (0,  "F",  0.00),
]
def get_grade(pct):
    for threshold, grade, gp in GRADE_SCALE:
        if pct >= threshold:
            return grade, gp
    return "F", 0.00

# ── Semester 4 courses (correct ones) ─────────────────────────────────────────
SEM4_COURSES = [
    ("Operating Systems",              3),
    ("Database Management Systems",    3),
    ("Software Design and Architecture", 3),
    ("Design and Analysis of Algorithms", 2),
    ("Engineering Management",         1),
]

# ── Historical semester courses ────────────────────────────────────────────────
HISTORICAL_COURSES = {
    1: [
        ("Introduction to Computing",   3),
        ("Calculus I",                   3),
        ("English Composition",          2),
        ("Islamic Studies",              2),
        ("Pakistan Studies",             2),
    ],
    2: [
        ("Object Oriented Programming",  3),
        ("Calculus II",                  3),
        ("Digital Logic Design",         2),
        ("Technical Writing",            2),
        ("Linear Algebra",               2),
    ],
    3: [
        ("Data Structures & Algorithms", 3),
        ("Discrete Mathematics",         3),
        ("Computer Organization",        2),
        ("Probability & Statistics",     2),
        ("Professional Ethics",          2),
    ],
}

# ── Course outlines (sem 4) ────────────────────────────────────────────────────
COURSE_OUTLINES = {
    "Operating Systems": [
        "An Overview of Computer System",
        "Operating System as a Resource Manager",
        "Process States, Creation and Termination",
        "Process Control Structures",
        "Types of Processor Scheduling",
        "Uni-processor Scheduling (Part I)",
        "Uni-processor Scheduling (Part II)",
        "Multi-threading, Thread Functionality",
        "Concurrency: Mutual Exclusion and Synchronization – I",
        "Concurrency: Mutual Exclusion and Synchronization – II",
        "Concurrency: Deadlock and Starvation – I",
        "Concurrency: Deadlock and Starvation – II",
        "Memory Management - I",
        "Memory Management - II",
        "Memory Management - III",
        "Course Revision",
    ],
    "Database Management Systems": [
        "Database Systems",
        "Database Systems: Design, Implementation, and Management",
        "The Relational Database Model",
        "The Relational Model",
        "Relational Operators",
        "Relational Algebra",
        "ER Diagram Examples",
        "Advanced Data Modeling",
        "ER Notation",
        "ER Exercise",
        "Normalization of Database Tables",
        "Normalization Exercise",
        "Transactions",
        "Concurrency Control",
        "Recovery System",
        "Distributed Databases and NoSQL",
    ],
    "Software Design and Architecture": [
        "What is Software Architecture & Software Design",
        "Software Design Principles with UML",
        "System Design & Software Architecture; Object Design, Mapping Design to Code",
        "Functional Design; UI Design; Web Applications Design",
        "Web Application – N-Tier MVC Load Balancing",
        "Design Pattern, Creational Pattern",
        "Structural Pattern",
        "Behavioral Pattern",
        "Interactive Systems with MVC Architecture; Software Reuse",
        "Architecture Description Languages (ADLs)",
        "Architectural Design Patterns",
        "Architectural Design Issues",
        "Quality Tactics",
        "Architectural Evaluation Technique",
        "Software Quality Attributes",
        "Case Studies and Review",
    ],
    "Design and Analysis of Algorithms": [
        "Introduction",
        "Time and Space Complexity",
        "Recursive Functions, Master Theorem and its Complexity",
        "Hashing",
        "Sorting",
        "Divide and Conquer",
        "Back Tracking",
        "Hashing Analysis",
        "Dynamic Programming, Combination Problem, Make Change Problem",
        "Dynamic Programming (Advanced)",
        "Chain Matrix Multiplication and LCS",
        "Longest Common Sequence",
        "Dijkstra Algorithm",
        "Branch and Bound Algorithm",
        "Pattern Matching",
        "Knapsack 0/1 Problem – Greedy Algorithm",
    ],
    "Engineering Management": [
        "Introduction to Engineering Management",
        "Organization Strategy and Project Selection",
        "Organization Structure and Culture",
        "Introduction to Project Management",
        "Project Management",
        "Controlling in Management",
        "Coordinating in Management",
        "Managing Research and Development",
        "Managing Engineering Design I",
        "Managing Engineering Design II",
        "Project Scheduling and Resource Allocation",
        "Project Costing",
        "Leadership",
        "Intellectual Property",
        "Quality Management System (QMS)",
        "Energy Management System (EMS)",
    ],
}

# ── 30 student names ───────────────────────────────────────────────────────────
STUDENT_NAMES = [
    "Muhammad Ahmed", "Ali Hassan", "Omar Farooq", "Usman Ghani", "Hamza Ali",
    "Bilal Khan", "Saad Malik", "Zain ul Abideen", "Hasan Raza", "Hussain Ali",
    "Abdullah Shah", "Abdur Rehman", "Ibrahim Khalil", "Ismail Noor", "Yusuf Siddiqui",
    "Ayesha Fatima", "Mariam Bibi", "Fatima Zahra", "Zainab Bano", "Sadia Khan",
    "Hina Tariq", "Sara Ahmed", "Nadia Ali", "Rabia Basri", "Sumaira Malik",
    "Khansa Javed", "Aleena Hassan", "Eman Sheikh", "Laiba Akhtar", "Hira Naeem",
]

# Performance profiles for mark generation
PROFILES = {
    "Excellent": {"lo": 0.82, "hi": 0.98},
    "Good":      {"lo": 0.68, "hi": 0.84},
    "Average":   {"lo": 0.55, "hi": 0.72},
    "Poor":      {"lo": 0.42, "hi": 0.60},
    "Very Poor": {"lo": 0.28, "hi": 0.50},
}
PROFILE_DIST = (["Excellent"] * 6 + ["Good"] * 8 + ["Average"] * 8 +
                ["Poor"] * 5 + ["Very Poor"] * 3)
random.shuffle(PROFILE_DIST)

# Assign each student a persistent profile
STUDENT_PROFILES = {name: PROFILE_DIST[i] for i, name in enumerate(STUDENT_NAMES)}


def gen_marks(profile, max_val):
    lo = PROFILES[profile]["lo"]
    hi = PROFILES[profile]["hi"]
    return round(random.uniform(lo * max_val, hi * max_val), 1)


# ══════════════════════════════════════════════════════════════════════════════
def run():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")
    cur = conn.cursor()

    # ── STEP 1: Schema additions ───────────────────────────────────────────────
    print("🔧 Step 1: Applying schema changes...")

    # Add `semester` to existing tables
    for table in ("quizzes", "assignments", "marks", "attendance"):
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN semester INTEGER DEFAULT 4")
            print(f"   + Added `semester` column to `{table}`")
        except sqlite3.OperationalError:
            print(f"   ✓ `semester` already exists in `{table}`")

    # Add `sessional` to marks (quiz+assign+midterm for sem 4)
    try:
        cur.execute("ALTER TABLE marks ADD COLUMN sessional REAL")
        print("   + Added `sessional` column to `marks`")
    except sqlite3.OperationalError:
        print("   ✓ `sessional` already exists in `marks`")

    # course_outlines table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS course_outlines (
        outline_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id    INTEGER NOT NULL,
        topic_number INTEGER NOT NULL,
        topic_name   TEXT NOT NULL,
        FOREIGN KEY(course_id) REFERENCES courses(course_id)
    )
    """)
    print("   + `course_outlines` table ready")

    # historical_courses table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS historical_courses (
        hc_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        semester     INTEGER NOT NULL,
        course_name  TEXT NOT NULL,
        credit_hours INTEGER NOT NULL
    )
    """)

    # historical_marks table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS historical_marks (
        hm_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id     INTEGER NOT NULL,
        semester       INTEGER NOT NULL,
        course_name    TEXT NOT NULL,
        credit_hours   INTEGER NOT NULL,
        quiz1 REAL, quiz2 REAL, quiz3 REAL, quiz4 REAL,
        assign1 REAL, assign2 REAL, assign3 REAL, assign4 REAL,
        midterm        REAL,
        final_exam     REAL,
        ia_obtained    REAL,
        ia_pct         REAL,
        total_obtained REAL,
        total_pct      REAL,
        FOREIGN KEY(student_id) REFERENCES students(student_id)
    )
    """)

    # semester_summary table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS semester_summary (
        summary_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id    INTEGER NOT NULL,
        semester      INTEGER NOT NULL,
        sem_ia_pct    REAL,
        sem_total_pct REAL,
        gpa           REAL,
        grade         TEXT,
        UNIQUE(student_id, semester),
        FOREIGN KEY(student_id) REFERENCES students(student_id)
    )
    """)
    print("   + Historical tables ready")
    conn.commit()

    # ── STEP 2: Load existing Sem 4 courses ───────────────────────────────────
    print("\n📚 Step 2: Loading Semester 4 courses...")

    sem4_names = [c[0] for c in SEM4_COURSES]
    cur.execute(
        "SELECT course_id, course_name, credit_hours FROM courses WHERE course_name IN ({})".format(
            ",".join("?" * len(sem4_names))), sem4_names
    )
    sem4_course_rows = cur.fetchall()
    sem4_course_map = {row[1]: (row[0], row[2]) for row in sem4_course_rows}
    print(f"   ✓ {len(sem4_course_rows)} Sem 4 courses found: {[r[1] for r in sem4_course_rows]}")

    if len(sem4_course_rows) != 5:
        print("   ⚠ Warning: Expected 5 courses. Check your courses table.")
      
    # ── STEP 3: Course outlines ────────────────────────────────────────────────
    print("\n📋 Step 3: Inserting course outlines...")
    for course_name, topics in COURSE_OUTLINES.items():
        if course_name not in sem4_course_map:
            print(f"   ⚠ Course '{course_name}' not found in DB, skipping outline.")
            continue
        course_id = sem4_course_map[course_name][0]
        cur.execute("DELETE FROM course_outlines WHERE course_id=?", (course_id,))
        for i, topic in enumerate(topics, 1):
            cur.execute(
                "INSERT INTO course_outlines (course_id, topic_number, topic_name) VALUES (?,?,?)",
                (course_id, i, topic)
            )
        print(f"   ✓ {course_name}: {len(topics)} topics inserted")
    conn.commit()

    # ── STEP 4: Ensure 30 students exist ──────────────────────────────────────
    print("\n👥 Step 4: Ensuring all 30 students exist...")
    for i, name in enumerate(STUDENT_NAMES, 1):
        reg_no = f"2024-CS-{i:03d}"
        pw_hash = bcrypt.hashpw("1234".encode(), bcrypt.gensalt())
        cur.execute("""
            INSERT OR IGNORE INTO students (registration_no, name, password_hash, semester, department)
            VALUES (?,?,?,4,'CS')
        """, (reg_no, name, pw_hash))
    conn.commit()

    cur.execute("SELECT student_id, name, registration_no FROM students WHERE semester=4 AND department='CS'")
    all_students = cur.fetchall()
    print(f"   ✓ {len(all_students)} students in DB")

    # ── STEP 5: Sem 4 marks (clear & reseed with correct courses) ─────────────
    print("\n📝 Step 5: Seeding Semester 4 marks...")

    all_student_ids = [row[0] for row in all_students]
    id_placeholders = ",".join("?" * len(all_student_ids))
    sem4_course_ids = [v[0] for v in sem4_course_map.values()]

    # Clear existing sem 4 records for these students
    for tbl in ("quizzes", "assignments", "marks", "attendance"):
        cur.execute(f"DELETE FROM {tbl} WHERE student_id IN ({id_placeholders}) AND semester=4",
                    all_student_ids)
    conn.commit()

    for student_id, name, reg_no in all_students:
        profile = STUDENT_PROFILES.get(name, "Average")

        for course_name, (course_id, credit_hours) in sem4_course_map.items():
            quizzes  = [gen_marks(profile, 2.5) for _ in range(4)]
            assigns  = [gen_marks(profile, 5.0) for _ in range(4)]
            midterm  = gen_marks(profile, 20.0)
            final    = gen_marks(profile, 50.0)

            sessional = round(sum(quizzes) + sum(assigns) + midterm, 1)

            # Insert quizzes
            for j, q in enumerate(quizzes, 1):
                cur.execute("""
                    INSERT INTO quizzes (student_id, course_id, quiz_name, marks_obtained, max_marks, semester)
                    VALUES (?,?,?,?,2.5,4)
                """, (student_id, course_id, f"Quiz {j}", q))

            # Insert assignments
            for j, a in enumerate(assigns, 1):
                cur.execute("""
                    INSERT INTO assignments (student_id, course_id, assignment_name, marks_obtained, max_marks, semester)
                    VALUES (?,?,?,?,5.0,4)
                """, (student_id, course_id, f"Assignment {j}", a))

            # Insert marks with sessional
            cur.execute("""
                INSERT INTO marks (student_id, course_id, midterm, final, sessional, semester)
                VALUES (?,?,?,?,?,4)
            """, (student_id, course_id, midterm, final, sessional))

            # Insert attendance
            lo_att = max(10, int(0.60 * 30))
            hi_att = 30
            if profile in ("Excellent", "Good"):
                attended = random.randint(25, 30)
            elif profile == "Average":
                attended = random.randint(20, 27)
            else:
                attended = random.randint(12, 22)

            cur.execute("""
                INSERT INTO attendance (student_id, course_id, classes_attended, total_classes, semester)
                VALUES (?,?,?,30,4)
            """, (student_id, course_id, attended))

        print(f"   ✓ {name} ({profile}) — Sem 4 marks inserted")

    conn.commit()

    # ── STEP 6: Historical courses table ──────────────────────────────────────
    print("\n🗂  Step 6: Populating historical_courses...")
    cur.execute("SELECT COUNT(*) FROM historical_courses")
    if cur.fetchone()[0] == 0:
        for sem, courses in HISTORICAL_COURSES.items():
            for cname, ch in courses:
                cur.execute("INSERT INTO historical_courses (semester, course_name, credit_hours) VALUES (?,?,?)",
                            (sem, cname, ch))
        print("   ✓ Historical courses inserted")
    else:
        print("   ✓ Already populated, skipping")
    conn.commit()

    # ── STEP 7: Historical marks for sems 1–3 ─────────────────────────────────
    print("\n📜 Step 7: Seeding historical marks (Sems 1–3)...")

    for student_id, name, reg_no in all_students:
        profile = STUDENT_PROFILES.get(name, "Average")

        for sem in [1, 2, 3]:
            cur.execute("SELECT COUNT(*) FROM historical_marks WHERE student_id=? AND semester=?",
                        (student_id, sem))
            if cur.fetchone()[0] > 0:
                continue  # skip if already seeded

            courses = HISTORICAL_COURSES[sem]
            course_results = []

            for course_name, credit_hours in courses:
                quizzes = [gen_marks(profile, 2.5) for _ in range(4)]
                assigns = [gen_marks(profile, 5.0)  for _ in range(4)]
                midterm = gen_marks(profile, 20.0)
                final   = gen_marks(profile, 50.0)

                ia_obtained    = round(sum(quizzes) + sum(assigns) + midterm, 1)
                total_obtained = round(ia_obtained + final, 1)
                ia_pct         = round((ia_obtained / 50.0)  * 100, 2)
                total_pct      = round((total_obtained / 100.0) * 100, 2)

                cur.execute("""
                    INSERT INTO historical_marks
                    (student_id, semester, course_name, credit_hours,
                     quiz1, quiz2, quiz3, quiz4,
                     assign1, assign2, assign3, assign4,
                     midterm, final_exam,
                     ia_obtained, ia_pct, total_obtained, total_pct)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (student_id, sem, course_name, credit_hours,
                      *quizzes, *assigns, midterm, final,
                      ia_obtained, ia_pct, total_obtained, total_pct))

                course_results.append({"ch": credit_hours, "ia_pct": ia_pct, "total_pct": total_pct})

            # Weighted semester aggregates
            total_ch     = sum(c["ch"] for c in course_results)
            sem_ia_pct   = round(sum(c["ia_pct"]    * c["ch"] for c in course_results) / total_ch, 2)
            sem_tot_pct  = round(sum(c["total_pct"] * c["ch"] for c in course_results) / total_ch, 2)
            grade, gpa   = get_grade(sem_tot_pct)

            cur.execute("""
                INSERT OR REPLACE INTO semester_summary
                (student_id, semester, sem_ia_pct, sem_total_pct, gpa, grade)
                VALUES (?,?,?,?,?,?)
            """, (student_id, sem, sem_ia_pct, sem_tot_pct, gpa, grade))

        print(f"   ✓ {name} ({profile}) — historical sems 1–3 done")

    conn.commit()

    # ── STEP 8: Verification summary ──────────────────────────────────────────
    print("\n" + "=" * 60)
    print("📊 VERIFICATION SUMMARY")
    print("=" * 60)

    cur.execute("SELECT COUNT(*) FROM students WHERE semester=4")
    print(f"\n👥 Students:          {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM courses")
    print(f"📚 Courses (Sem 4):   {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM course_outlines")
    print(f"📋 Course outline rows: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM quizzes WHERE semester=4")
    print(f"📝 Quiz records:      {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM marks WHERE semester=4")
    print(f"📝 Marks records:     {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM historical_marks")
    print(f"🗂  Historical marks:  {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM semester_summary")
    print(f"📈 Semester summaries: {cur.fetchone()[0]}")

    print("\n📖 Sem 4 Courses:")
    cur.execute("SELECT course_name, credit_hours FROM courses ORDER BY course_id")
    for row in cur.fetchall():
        print(f"   - {row[0]} ({row[1]} CH)")

    print("\n🎓 Sample Semester Summary (first 5 students, all sems):")
    cur.execute("""
        SELECT s.name, ss.semester, ss.sem_ia_pct, ss.sem_total_pct, ss.gpa, ss.grade
        FROM semester_summary ss
        JOIN students s ON s.student_id = ss.student_id
        ORDER BY s.student_id, ss.semester
        LIMIT 15
    """)
    for row in cur.fetchall():
        print(f"   {row[0]:<22} | Sem {row[1]} | IA: {row[2]:5.1f}% | Total: {row[3]:5.1f}% | GPA: {row[4]} ({row[5]})")

    print("\n✅ Migration complete!")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.close()


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"❌ DB not found at: {DB_PATH}")
        print("   Run init_db.py first, then place this script in the same folder.")
    else:
        run()