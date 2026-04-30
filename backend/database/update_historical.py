"""
Update Historical Records (Sems 1–3) — Realistic & Varied
===========================================================

WHAT THIS FIXES:
-----------------
1. No student fails — minimum passing total is 50.0 (grade D)
2. IA floor: 25.0 (out of 50 marks = 50% minimum)
3. Final floor: 50.0 (out of 100 marks)
   → IA pct stored as plain number e.g. 63.4  (no % sign)
   → Total pct stored as plain number e.g. 71.2 (no % sign)

4. Real variance — each student has a BASE band but:
   - Each semester shifts the band up or down by ±8 points
   - Each course within a semester shifts by ±5 points
   - This means same student can go from B+ one sem to A- next sem
     or drop from Good to Average — feels human and organic

5. Student mix:
   - Excellent (6): consistently high, occasional dip
   - Good     (8): solid mid-70s to 80s, noticeable swings
   - Average  (8): 58–72 range, passes comfortably
   - Struggling(5): 50–62, scrapes through, some near-fails
   - Nil      (3): 50–55 range, barely passing each semester
     (renamed from "Very Poor" to "Nil" to reflect the real term)

6. Marks stored per-course: all 4 quizzes, 4 assignments, midterm,
   final — with ia_pct and total_pct as plain floats (no % symbol).

7. semester_summary stores sem_ia_pct and sem_total_pct as weighted
   averages (credit-hour weighted), also plain floats.
"""

import sqlite3
import os
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "lms.db")

random.seed(42)

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

# ── Historical courses (same as before) ───────────────────────────────────────
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

# ── Student performance bands ──────────────────────────────────────────────────
# Each band defines the BASE percentage range for that student type.
# Actual per-semester and per-course values shift within ±8 and ±5 points.
BANDS = {
    "Excellent":  (78, 95),   # consistently strong, peaks at A
    "Good":       (65, 82),   # solid B range, can touch A- or dip to C+
    "Average":    (55, 72),   # comfortable C to B range
    "Struggling": (50, 63),   # passes every time, but not by much
    "Nil":        (50, 57),   # barely scrapes through, D to C- territory
}

# Distribution among 30 students
BAND_DIST = (
    ["Excellent"]  * 6 +
    ["Good"]       * 8 +
    ["Average"]    * 8 +
    ["Struggling"] * 5 +
    ["Nil"]        * 3
)
random.shuffle(BAND_DIST)

STUDENT_NAMES = [
    "Muhammad Ahmed", "Ali Hassan", "Omar Farooq", "Usman Ghani", "Hamza Ali",
    "Bilal Khan", "Saad Malik", "Zain ul Abideen", "Hasan Raza", "Hussain Ali",
    "Abdullah Shah", "Abdur Rehman", "Ibrahim Khalil", "Ismail Noor", "Yusuf Siddiqui",
    "Ayesha Fatima", "Mariam Bibi", "Fatima Zahra", "Zainab Bano", "Sadia Khan",
    "Hina Tariq", "Sara Ahmed", "Nadia Ali", "Rabia Basri", "Sumaira Malik",
    "Khansa Javed", "Aleena Hassan", "Eman Sheikh", "Laiba Akhtar", "Hira Naeem",
]
STUDENT_BAND = {name: BAND_DIST[i] for i, name in enumerate(STUDENT_NAMES)}

# Floors
IA_FLOOR_PCT    = 25.0   # minimum IA percentage (stored as 25.0, not "25%")
TOTAL_FLOOR_PCT = 50.0   # minimum total percentage (passing threshold)


def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def gen_course_marks(base_pct, course_shift):
    """
    Generate individual marks for one course given a base percentage
    and a per-course random shift.
    Returns dict of all raw marks + computed percentages.
    """
    effective_pct = clamp(base_pct + course_shift, 0, 100)

    # --- IA components (total max = 50) ---
    # We target effective_pct on the total (100), so IA and final
    # naturally follow. We add slight independent noise per component.
    ia_target  = effective_pct / 100 * 50    # target IA out of 50
    fin_target = effective_pct / 100 * 50    # target Final out of 50

    # Quizzes (max 2.5 each, total 10)
    q_target = ia_target * (10 / 50)
    quizzes = []
    for _ in range(4):
        raw = q_target / 4 + random.uniform(-0.3, 0.3)
        quizzes.append(round(clamp(raw, 0, 2.5), 1))

    # Assignments (max 5 each, total 20)
    a_target = ia_target * (20 / 50)
    assigns = []
    for _ in range(4):
        raw = a_target / 4 + random.uniform(-0.5, 0.5)
        assigns.append(round(clamp(raw, 0, 5.0), 1))

    # Midterm (max 20)
    m_target = ia_target * (20 / 50)
    midterm = round(clamp(m_target + random.uniform(-1.5, 1.5), 0, 20), 1)

    # Final exam (max 50)
    final = round(clamp(fin_target + random.uniform(-3.0, 3.0), 0, 50), 1)

    ia_obtained    = round(sum(quizzes) + sum(assigns) + midterm, 1)
    total_obtained = round(ia_obtained + final, 1)

    # Enforce floors on percentages
    ia_pct    = round(max(IA_FLOOR_PCT,    (ia_obtained    / 50.0)  * 100), 2)
    total_pct = round(max(TOTAL_FLOOR_PCT, (total_obtained / 100.0) * 100), 2)

    # If floor was applied, bump the raw marks proportionally
    if ia_pct == IA_FLOOR_PCT and ia_obtained < (IA_FLOOR_PCT / 100 * 50):
        # nudge midterm up just enough
        needed = (IA_FLOOR_PCT / 100 * 50)
        deficit = needed - ia_obtained
        midterm = round(min(20.0, midterm + deficit), 1)
        ia_obtained = round(sum(quizzes) + sum(assigns) + midterm, 1)

    if total_pct == TOTAL_FLOOR_PCT and total_obtained < (TOTAL_FLOOR_PCT / 100 * 100):
        needed = TOTAL_FLOOR_PCT
        deficit = needed - total_obtained
        final = round(min(50.0, final + deficit), 1)
        total_obtained = round(ia_obtained + final, 1)
        total_pct = round((total_obtained / 100.0) * 100, 2)

    return {
        "quizzes":        quizzes,
        "assigns":        assigns,
        "midterm":        midterm,
        "final":          final,
        "ia_obtained":    ia_obtained,
        "ia_pct":         ia_pct,         # plain float, no % sign
        "total_obtained": total_obtained,
        "total_pct":      total_pct,      # plain float, no % sign
    }


def run():
    if not os.path.exists(DB_PATH):
        print(f"❌ DB not found at: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")
    cur = conn.cursor()

    # Ensure tables exist (safe no-op if already there)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS historical_courses (
        hc_id INTEGER PRIMARY KEY AUTOINCREMENT,
        semester INTEGER NOT NULL,
        course_name TEXT NOT NULL,
        credit_hours INTEGER NOT NULL
    )""")

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
    )""")

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
    )""")

    # Populate historical_courses if empty
    cur.execute("SELECT COUNT(*) FROM historical_courses")
    if cur.fetchone()[0] == 0:
        for sem, courses in HISTORICAL_COURSES.items():
            for cname, ch in courses:
                cur.execute(
                    "INSERT INTO historical_courses (semester, course_name, credit_hours) VALUES (?,?,?)",
                    (sem, cname, ch)
                )
        print("✓ historical_courses populated")

    conn.commit()

    # Load all students
    cur.execute("SELECT student_id, name FROM students WHERE semester=4 AND department='CS'")
    all_students = cur.fetchall()
    print(f"\nFound {len(all_students)} students. Rebuilding historical records...\n")

    for student_id, name in all_students:
        band = STUDENT_BAND.get(name, "Average")
        band_lo, band_hi = BANDS[band]

        # Wipe old historical data for this student
        cur.execute("DELETE FROM historical_marks   WHERE student_id=?", (student_id,))
        cur.execute("DELETE FROM semester_summary   WHERE student_id=? AND semester IN (1,2,3)",
                    (student_id,))

        for sem in [1, 2, 3]:
            courses = HISTORICAL_COURSES[sem]

            # Per-semester base: random point within band, shifts each semester
            sem_shift = random.uniform(-8, 8)
            sem_base  = clamp(random.uniform(band_lo, band_hi) + sem_shift, band_lo - 5, band_hi + 5)

            course_results = []

            for course_name, credit_hours in courses:
                # Additional per-course noise
                course_shift = random.uniform(-5, 5)
                data = gen_course_marks(sem_base, course_shift)

                cur.execute("""
                    INSERT INTO historical_marks
                    (student_id, semester, course_name, credit_hours,
                     quiz1, quiz2, quiz3, quiz4,
                     assign1, assign2, assign3, assign4,
                     midterm, final_exam,
                     ia_obtained, ia_pct, total_obtained, total_pct)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    student_id, sem, course_name, credit_hours,
                    *data["quizzes"],
                    *data["assigns"],
                    data["midterm"],
                    data["final"],
                    data["ia_obtained"],
                    data["ia_pct"],
                    data["total_obtained"],
                    data["total_pct"],
                ))

                course_results.append({
                    "ch":        credit_hours,
                    "ia_pct":    data["ia_pct"],
                    "total_pct": data["total_pct"],
                })

            # Weighted semester aggregates (credit-hour weighted)
            total_ch      = sum(c["ch"] for c in course_results)
            sem_ia_pct    = round(
                sum(c["ia_pct"]    * c["ch"] for c in course_results) / total_ch, 2
            )
            sem_total_pct = round(
                sum(c["total_pct"] * c["ch"] for c in course_results) / total_ch, 2
            )
            # Enforce floors on semester aggregates too
            sem_ia_pct    = max(IA_FLOOR_PCT,    sem_ia_pct)
            sem_total_pct = max(TOTAL_FLOOR_PCT, sem_total_pct)

            grade, gpa = get_grade(sem_total_pct)

            cur.execute("""
                INSERT OR REPLACE INTO semester_summary
                (student_id, semester, sem_ia_pct, sem_total_pct, gpa, grade)
                VALUES (?,?,?,?,?,?)
            """, (student_id, sem, sem_ia_pct, sem_total_pct, gpa, grade))

            print(f"  [{band:<10}] {name:<22} | Sem {sem} "
                  f"| IA: {sem_ia_pct:5.1f}  Total: {sem_total_pct:5.1f}  "
                  f"GPA: {gpa} ({grade})")

    conn.commit()

    # ── Summary stats ──────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("GRADE DISTRIBUTION ACROSS ALL HISTORICAL RECORDS")
    print("=" * 65)
    cur.execute("""
        SELECT grade, COUNT(*) as cnt
        FROM semester_summary
        WHERE semester IN (1,2,3)
        GROUP BY grade ORDER BY gpa DESC
    """, )
    # gpa not in scope here, re-query with join
    cur.execute("""
        SELECT grade, COUNT(*) as cnt
        FROM semester_summary
        WHERE semester IN (1,2,3)
        GROUP BY grade
        ORDER BY sem_total_pct DESC
    """)
    print(f"\n{'Grade':<8} {'Count':>6}")
    for grade, cnt in cur.fetchall():
        print(f"  {grade:<8} {cnt:>4}")

    cur.execute("SELECT COUNT(*) FROM historical_marks WHERE semester IN (1,2,3)")
    print(f"\nTotal historical_marks rows: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM semester_summary WHERE semester IN (1,2,3)")
    print(f"Total semester_summary rows: {cur.fetchone()[0]}")

    cur.execute("""
        SELECT MIN(sem_total_pct), MAX(sem_total_pct), AVG(sem_total_pct)
        FROM semester_summary WHERE semester IN (1,2,3)
    """)
    mn, mx, av = cur.fetchone()
    print(f"\nTotal pct range: {mn:.1f} – {mx:.1f}  (avg {av:.1f})")

    cur.execute("""
        SELECT MIN(sem_ia_pct), MAX(sem_ia_pct), AVG(sem_ia_pct)
        FROM semester_summary WHERE semester IN (1,2,3)
    """)
    mn, mx, av = cur.fetchone()
    print(f"IA pct range:    {mn:.1f} – {mx:.1f}  (avg {av:.1f})")

    print("\n✅ Historical records updated successfully!")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.close()


if __name__ == "__main__":
    run()