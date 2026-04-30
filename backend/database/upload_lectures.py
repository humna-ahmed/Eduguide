"""
Lecture Upload Script
=====================
Place your lecture files in organized folders and run this script to upload them to the database.

Folder Structure Expected:
--------------------------
lectures/
├── Operating Systems/
│   ├── Lecture 1 - Introduction to OS.pdf
│   ├── Lecture 2 - Process Management.pptx
│   └── ...
├── Database Management Systems/
│   ├── Lecture 1 - DBMS Overview.pdf
│   └── ...
└── ... (same for other courses)

Usage:
------
1. Create a 'lectures' folder in the same directory as this script
2. Inside 'lectures', create subfolders for each course (exact course names)
3. Place lecture files (PDF/PPTX/PPT) in respective course folders
4. Name files as: "Lecture X - Title.extension" (e.g., "Lecture 1 - Introduction.pdf")
5. Run: python upload_lectures.py
"""

import sqlite3
import os
import sys

# Add parent directory to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lms.db")
LECTURES_DIR = os.path.join(BASE_DIR, "lectures")

def upload_lectures():
    """Upload all lecture files from organized folders to database."""
    
    if not os.path.exists(LECTURES_DIR):
        print(f"❌ Lectures directory not found: {LECTURES_DIR}")
        print("Please create a 'lectures' folder with course subfolders.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Get all courses from database
    cur.execute("SELECT course_id, course_name FROM courses")
    courses = {name: cid for cid, name in cur.fetchall()}
    
    if not courses:
        print("❌ No courses found in database. Run complete_migration.py first.")
        conn.close()
        return
    
    print(f"📚 Found {len(courses)} courses in database")
    print(f"📁 Scanning lectures directory: {LECTURES_DIR}\n")
    
    total_uploaded = 0
    total_errors = 0
    
    # Process each course folder
    for folder_name in os.listdir(LECTURES_DIR):
        folder_path = os.path.join(LECTURES_DIR, folder_name)
        
        if not os.path.isdir(folder_path):
            continue
        
        # Check if folder name matches a course
        if folder_name not in courses:
            print(f"⚠️  Skipping '{folder_name}' - not found in database courses")
            continue
        
        course_id = courses[folder_name]
        print(f"📖 Processing: {folder_name}")
        
        # Get all lecture files in the course folder
        files = sorted([f for f in os.listdir(folder_path) 
                       if f.lower().endswith(('.pdf', '.pptx', '.ppt'))])
        
        if not files:
            print(f"   No lecture files found in {folder_name}/")
            continue
        
        for file_name in files:
            file_path = os.path.join(folder_path, file_name)
            
            # Parse lecture number and title from filename
            # Expected format: "Lecture X - Title.extension"
            try:
                name_parts = file_name.split(' - ', 1)
                lecture_num_str = name_parts[0].replace('Lecture ', '').strip()
                lecture_number = int(lecture_num_str)
                
                if len(name_parts) > 1:
                    lecture_title = name_parts[1].rsplit('.', 1)[0]
                else:
                    lecture_title = file_name.rsplit('.', 1)[0]
            except (ValueError, IndexError):
                print(f"   ⚠️  Invalid filename format: {file_name}")
                print(f"      Expected: 'Lecture X - Title.extension'")
                total_errors += 1
                continue
            
            # Determine file type
            ext = os.path.splitext(file_name)[1].lower()
            file_type_map = {
                '.pdf': 'PDF',
                '.pptx': 'PPTX',
                '.ppt': 'PPT'
            }
            file_type = file_type_map.get(ext, ext.upper().replace('.', ''))
            
            # Read file data
            try:
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                
                file_size = len(file_data)
                
                # Check if lecture number already exists for this course
                cur.execute("""
                    SELECT lecture_id FROM lectures 
                    WHERE course_id = ? AND lecture_number = ?
                """, (course_id, lecture_number))
                
                existing = cur.fetchone()
                
                if existing:
                    # Update existing lecture
                    cur.execute("""
                        UPDATE lectures 
                        SET lecture_title = ?, file_name = ?, file_data = ?, 
                            file_type = ?, file_size = ?
                        WHERE course_id = ? AND lecture_number = ?
                    """, (lecture_title, file_name, file_data, file_type, 
                          file_size, course_id, lecture_number))
                    print(f"   ✅ Updated: Lecture {lecture_number} - {lecture_title} ({file_type})")
                else:
                    # Insert new lecture
                    cur.execute("""
                        INSERT INTO lectures 
                        (course_id, lecture_number, lecture_title, file_name, 
                         file_data, file_type, file_size)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (course_id, lecture_number, lecture_title, file_name, 
                          file_data, file_type, file_size))
                    print(f"   ✅ Uploaded: Lecture {lecture_number} - {lecture_title} ({file_type})")
                
                total_uploaded += 1
                
            except Exception as e:
                print(f"   ❌ Error processing {file_name}: {str(e)}")
                total_errors += 1
        
        print()  # Empty line between courses
    
    conn.commit()
    conn.close()
    
    print("=" * 60)
    print(f"✅ Upload complete!")
    print(f"   Successfully uploaded: {total_uploaded} lectures")
    if total_errors > 0:
        print(f"   Errors: {total_errors}")
    print("=" * 60)

def show_lecture_summary():
    """Display summary of uploaded lectures."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT c.course_name, COUNT(l.lecture_id) as lecture_count
        FROM courses c
        LEFT JOIN lectures l ON c.course_id = l.course_id
        GROUP BY c.course_id, c.course_name
        ORDER BY c.course_name
    """)
    
    print("\n📊 Lecture Summary by Course:")
    print("-" * 40)
    for course_name, count in cur.fetchall():
        print(f"   {course_name}: {count} lectures")
    
    cur.execute("SELECT COUNT(*) FROM lectures")
    total = cur.fetchone()[0]
    print(f"\n   Total Lectures: {total}")
    
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--summary":
        show_lecture_summary()
    else:
        upload_lectures()
        print()
        show_lecture_summary()