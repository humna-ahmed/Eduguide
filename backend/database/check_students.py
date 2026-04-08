import sqlite3

conn = sqlite3.connect("backend/database/lms.db")
cur = conn.cursor()

cur.execute("SELECT registration_no, name FROM students")
rows = cur.fetchall()

for row in rows:
    print(row)

conn.close()
