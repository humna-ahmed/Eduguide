import sqlite3

conn = sqlite3.connect("backend/database/lms.db")
cur = conn.cursor()

cur.execute("DELETE FROM students WHERE registration_no = ?", ("2021-CS-001",))
conn.commit()
conn.close()

print("Old test student deleted")
