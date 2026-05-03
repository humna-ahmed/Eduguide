# fix_ia_marks.py
"""
Adds sem_ia_raw column to semester_summary table.
Converts existing sem_ia_pct (percentage) → raw marks out of 50.
sem_ia_raw = round(sem_ia_pct / 100 * 50, 2)

Run this ONCE after update_historical.py
"""

import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "lms.db")

def run():
    if not os.path.exists(DB_PATH):
        print(f"❌ DB not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    # ── STEP 1: Add sem_ia_raw column if not exists ────────────────────────
    try:
        cur.execute("ALTER TABLE semester_summary ADD COLUMN sem_ia_raw REAL")
        print("✅ Added sem_ia_raw column to semester_summary")
    except sqlite3.OperationalError:
        print("✓  sem_ia_raw column already exists")

    # ── STEP 2: Populate sem_ia_raw from sem_ia_pct ────────────────────────
    # sem_ia_pct is stored as percentage (0-100)
    # sem_ia_raw = sem_ia_pct / 100 * 50  → gives marks out of 50
    cur.execute("""
        UPDATE semester_summary
        SET sem_ia_raw = ROUND(sem_ia_pct / 100.0 * 50, 2)
        WHERE sem_ia_raw IS NULL
    """)

    updated = cur.rowcount
    print(f"✅ Updated {updated} rows with sem_ia_raw values")

    conn.commit()

    # ── STEP 3: Verify ─────────────────────────────────────────────────────
    print("\n📊 Verification — sample rows:")
    print(f"{'Student ID':<12} {'Sem':<5} {'sem_ia_pct':>12} {'sem_ia_raw':>12} {'sem_total_pct':>15}")
    print("-" * 60)

    cur.execute("""
        SELECT ss.student_id, ss.semester, ss.sem_ia_pct, ss.sem_ia_raw, ss.sem_total_pct
        FROM semester_summary ss
        ORDER BY ss.student_id, ss.semester
        LIMIT 15
    """)
    for row in cur.fetchall():
        print(f"{row[0]:<12} {row[1]:<5} {row[2]:>12.2f} {row[3]:>12.2f} {row[4]:>15.2f}")

    # ── STEP 4: Check all 3 columns the model needs are present ───────────
    print("\n✅ Checking all model feature columns are computable from DB:")
    cur.execute("""
        SELECT 
            ss.student_id,
            MAX(CASE WHEN ss.semester=1 THEN ss.sem_total_pct END) as Sem1_Marks,
            MAX(CASE WHEN ss.semester=2 THEN ss.sem_total_pct END) as Sem2_Marks,
            MAX(CASE WHEN ss.semester=3 THEN ss.sem_total_pct END) as Sem3_Marks,
            MAX(CASE WHEN ss.semester=1 THEN ss.sem_ia_raw END)    as Sem1_IA,
            MAX(CASE WHEN ss.semester=2 THEN ss.sem_ia_raw END)    as Sem2_IA,
            MAX(CASE WHEN ss.semester=3 THEN ss.sem_ia_raw END)    as Sem3_IA,
            ROUND(
                (MAX(CASE WHEN ss.semester=1 THEN ss.sem_total_pct END) +
                 MAX(CASE WHEN ss.semester=2 THEN ss.sem_total_pct END) +
                 MAX(CASE WHEN ss.semester=3 THEN ss.sem_total_pct END)) / 3.0, 2
            ) as Pct_Upto_3Sem
        FROM semester_summary ss
        GROUP BY ss.student_id
        LIMIT 5
    """)

    rows = cur.fetchall()
    print(f"\n{'SID':<5} {'Sem1_Marks':>11} {'Sem2_Marks':>11} {'Sem3_Marks':>11} "
          f"{'Sem1_IA':>8} {'Sem2_IA':>8} {'Sem3_IA':>8} {'Pct_Upto3':>10}")
    print("-" * 80)
    for row in rows:
        print(f"{row[0]:<5} {row[1]:>11.2f} {row[2]:>11.2f} {row[3]:>11.2f} "
              f"{row[4]:>8.2f} {row[5]:>8.2f} {row[6]:>8.2f} {row[7]:>10.2f}")

    print("\n✅ All model features are now available in the database!")
    print("   Sem4_IA will be computed at runtime from quizzes + assignments + midterm")
    conn.close()

if __name__ == "__main__":
    run()