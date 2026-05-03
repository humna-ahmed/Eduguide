# dashboard/dashboard.py
import streamlit as st
import sqlite3
import pandas as pd
import sys
import os
import asyncio
import datetime
import time

# --------------------------------------------------
# ADD PARENT DIRECTORY TO PYTHON PATH (for agents)
# --------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)


from backend.agentic_architecture.agent import build_agents, config, memory
from agents import Runner

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="Academic Portal | Student LMS",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --------------------------------------------------
# CUSTOM CSS FOR PROFESSIONAL STYLING
# --------------------------------------------------
st.markdown("""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Global Styles */
    * {
        font-family: 'Inter', sans-serif;
    }
    
    /* Main Container */
    .main {
        background-color: #f8f9fa;
        padding: 0 !important;
    }
    
    /* Fix main block padding */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e3a8a 0%, #1e40af 100%);
    }
    
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #ffffff;
        font-weight: 500;
    }
    
    /* Sidebar Title */
    [data-testid="stSidebar"] h1 {
        color: #ffffff;
        font-size: 1.5rem;
        font-weight: 700;
        padding: 1rem 0;
        border-bottom: 2px solid rgba(255,255,255,0.2);
        margin-bottom: 1.5rem;
    }
    
    /* Radio Buttons in Sidebar */
    [data-testid="stSidebar"] .stRadio > label {
        color: #ffffff !important;
        font-weight: 600;
        font-size: 1rem;
        margin-bottom: 0.5rem;
    }
    
    [data-testid="stSidebar"] .stRadio > div {
        gap: 0.5rem;
    }
    
    [data-testid="stSidebar"] .stRadio label {
        background-color: rgba(255,255,255,0.1);
        padding: 0.75rem 1rem;
        border-radius: 8px;
        color: #ffffff !important;
        cursor: pointer;
        transition: all 0.3s ease;
        border: 1px solid transparent;
    }
    
    [data-testid="stSidebar"] .stRadio label:hover {
        background-color: rgba(255,255,255,0.2);
        border-color: rgba(255,255,255,0.3);
    }
    
    /* Page Title */
    h1 {
        color: #1e293b;
        font-weight: 700;
        margin-bottom: 1.5rem;
        padding-bottom: 1rem;
        border-bottom: 3px solid #3b82f6;
    }
    
    /* Subheaders */
    h2, h3 {
        color: #334155;
        font-weight: 600;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    
    /* Metric Cards */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1e293b;
    }
    
    [data-testid="stMetricLabel"] {
        font-size: 0.875rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* Info Card */
    .info-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        margin-bottom: 1.5rem;
        border-left: 4px solid #3b82f6;
    }
    
    /* Course Card */
    .course-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.25rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Stats Card */
    .stats-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border: 1px solid #e2e8f0;
        height: 100%;
    }
    
    /* Personal Info Card */
    .personal-info-card {
        background: white;
        padding: 1.25rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border: 1px solid #e2e8f0;
        height: 100%;
        margin-bottom: 0.5rem;
    }
    
    /* Course Enrollment Card */
    .course-enroll-card {
        background: white;
        padding: 1.25rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border: 1px solid #e2e8f0;
        margin-bottom: 1rem;
    }
    
    /* Table Styling */
    [data-testid="stTable"] {
        background: white;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* Multiselect */
    .stMultiSelect > label {
        font-weight: 600;
        color: #334155;
        margin-bottom: 0.5rem;
    }
    
    /* Progress Bar */
    .stProgress > div > div {
        background-color: #3b82f6;
    }
    
    /* Chat Messages */
    [data-testid="stChatMessage"] {
        background-color: white;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(59,130,246,0.4);
    }
    
    /* Welcome Banner */
    .welcome-banner {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Info Box */
    .stAlert {
        border-radius: 8px;
        border-left: 4px solid #3b82f6;
    }
    
    /* Divider */
    hr {
        margin: 1.5rem 0;
        border: none;
        border-top: 2px solid #e2e8f0;
    }
    
    /* Remove extra spacing */
    .st-emotion-cache-1r4qj8v {
        padding-top: 1rem;
    }
    
    /* Fix for empty boxes */
    .st-emotion-cache-1r4qj8v > div:empty {
        display: none;
    }
        /* Live Clock Styling */
    .clock-container {
        background: rgba(255, 255, 255, 0.1);
        padding: 0.75rem 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        text-align: center;
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .clock-time {
        font-size: 1.5rem;
        font-weight: 700;
        color: #ffffff;
        margin: 0;
        line-height: 1.2;
        letter-spacing: 2px;
    }
    
    .clock-date {
        font-size: 0.85rem;
        color: rgba(255, 255, 255, 0.8);
        margin: 0.25rem 0 0 0;
        font-weight: 400;
    }
    
    .clock-label {
        font-size: 0.7rem;
        color: rgba(255, 255, 255, 0.6);
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.25rem;
    }
    /* Course Outline Styling */
.course-outline-topic {
    background: white;
    padding: 0.75rem 1rem;
    border-radius: 8px;
    margin-bottom: 0.5rem;
    border-left: 3px solid #3b82f6;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.course-outline-topic:hover {
    background: #f8fafc;
    transform: translateX(5px);
    transition: all 0.2s ease;
}
    /* ── Lectures Page Styling ── */
    .lecture-row {
        background: white;
        padding: 1rem 1.25rem;
        border-radius: 12px;
        margin-bottom: 0.75rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: all 0.2s ease;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    .lecture-row:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        border-color: #3b82f6;
        transform: translateX(3px);
    }
    
    .lecture-icon {
        font-size: 2rem;
        min-width: 50px;
        text-align: center;
    }
    
    .lecture-info {
        flex: 1;
    }
    
    .lecture-info h4 {
        margin: 0 0 0.25rem 0;
        color: #1e293b;
        font-size: 1rem;
        font-weight: 600;
    }
    
    .lecture-info p {
        margin: 0;
        color: #64748b;
        font-size: 0.85rem;
    }
    
    .lecture-download-btn {
        min-width: 120px;
    }
    
    /* Select box styling */
    .stSelectbox > label {
        font-weight: 600;
        color: #334155;
        font-size: 1rem;
    }
    
    /* Lecture count badge */
    .lecture-count-badge {
        display: inline-block;
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-left: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# HELPER FUNCTION
# --------------------------------------------------
def fmt(x):
    return f"{float(x):.2f}"

# --------------------------------------------------
# DATABASE PATH
# --------------------------------------------------
DB_PATH = os.path.join(PROJECT_ROOT, "backend", "database", "lms.db")

# --------------------------------------------------
# AUTH CHECK
# --------------------------------------------------
student_id = st.query_params.get("student_id")

# ── Clear cache when a new student session starts ────────────────────────
from backend.agentic_architecture.agent import clear_prediction_cache, clear_notes_store

if student_id and st.session_state.get("current_student_id") != student_id:
    clear_prediction_cache()
    clear_notes_store()
    st.session_state.current_student_id = student_id
    st.session_state.messages = []
    st.session_state.welcome_shown = False
    st.session_state.notes_filename = ""
# ─────────────────────────────────────────────────────────────────────────

if not student_id:
    st.error("🔒 Unauthorized Access")
    st.warning("Please login through the authentication portal to access your dashboard.")
    st.stop()

# --------------------------------------------------
# CONNECT TO DATABASE
# --------------------------------------------------
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# --------------------------------------------------
# FETCH STUDENT INFO
# --------------------------------------------------
cur.execute("""
    SELECT name, registration_no, semester
    FROM students
    WHERE student_id = ?
""", (student_id,))
student = cur.fetchone()

if not student:
    st.error("❌ Student Record Not Found")
    st.info("Please contact the administration for assistance.")
    st.stop()

student_name, registration_no, semester = student

# --------------------------------------------------
# FETCH COURSES
# --------------------------------------------------
cur.execute("""
    SELECT DISTINCT c.course_id, c.course_name
    FROM courses c
    JOIN marks m ON m.course_id = c.course_id
    WHERE m.student_id = ?
""", (student_id,))
courses = cur.fetchall()
course_map = {name: cid for cid, name in courses}
course_names = list(course_map.keys())

# --------------------------------------------------
# SIDEBAR NAVIGATION
# --------------------------------------------------
with st.sidebar:
    st.markdown("# 🎓 Academic Portal")
    st.markdown(f"**Welcome, {student_name.split()[0]}!**")
    st.markdown(f"*{registration_no}*")
    st.markdown("---")
    
    # Live Clock Display - Updates on every page interaction
    current_time = datetime.datetime.now()
    time_str = current_time.strftime("%H:%M:%S")
    date_str = current_time.strftime("%A, %B %d, %Y")
        # Add a small refresh button for the clock
    if st.button("🔄 Refresh Time", key="refresh_clock", use_container_width=True):
        st.rerun()
    st.markdown(f"""
    <div class="clock-container">
        <div class="clock-label">⏰ CURRENT TIME</div>
        <div class="clock-time">{time_str}</div>
        <div class="clock-date">{date_str}</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    page = st.radio(
        "Navigation",
        [
            "🏠 Dashboard",
            "📋 Course Outline",  # Added new page
            "📚 Lectures",  # Added lectures page
            "👤 Personal Info",
            "📝 Quizzes",
            "📂 Assignments",
            "📅 Attendance",
            "🤖 AI Assistant"
        ],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown(f"**Semester:** {semester}")
    st.markdown(f"**Enrolled Courses:** {len(course_names)}")

# --------------------------------------------------
# HELPER: PAGE-SCOPED COURSE SELECTOR
# --------------------------------------------------
def course_selector(page_key):
    selector_key = f"courses_{page_key}"
    options = ["Select All Courses"] + course_names

    selected = st.multiselect(
        "📚 Select course(s) to view",
        options=options,
        key=selector_key
    )

    if "Select All Courses" in selected:
        return course_names

    return selected

# ==================================================
# PAGE: DASHBOARD
# ==================================================
if page == "🏠 Dashboard":
    st.title("📊 Academic Dashboard")
    
    # Welcome Banner - more compact
    st.markdown(f"""
    <div class="welcome-banner">
        <h3 style="margin:0; color: white;">Welcome back, {student_name}! 👋</h3>
        <p style="margin:0.5rem 0 0 0; opacity: 0.9; font-size: 0.95rem;">Here's your academic overview for Semester {semester}</p>
    </div>
    """, unsafe_allow_html=True)
    
    selected_courses = course_selector("dashboard")

    if not selected_courses:
        st.info("📚 Please select one or more courses to view your academic performance.")
    else:
        for course_name in selected_courses:
            course_id = course_map[course_name]
            
            # Fetch credit hours for the course
            cur.execute("""
                SELECT credit_hours
                FROM courses
                WHERE course_id = ?
            """, (course_id,))
            credit_result = cur.fetchone()
            credit_hours = credit_result[0] if credit_result else 3
            
            # Display course card with credit hours
            st.markdown(f"""
            <div class="course-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h4 style="margin:0; color: white;">📖 {course_name}</h4>
                    <span style="background: rgba(255,255,255,0.2); padding: 4px 8px; border-radius: 6px; font-size: 0.8rem;">
                        {credit_hours} Credit Hours
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            cur.execute("""
                SELECT classes_attended, total_classes
                FROM attendance
                WHERE student_id = ? AND course_id = ?
            """, (student_id, course_id))
            att = cur.fetchone()
            attendance_pct = round((att[0] / att[1]) * 100, 2) if att else 0

            # Fetch quiz total from new quizzes table
            cur.execute("""
                SELECT SUM(marks_obtained)
                FROM quizzes
                WHERE student_id = ? AND course_id = ?
            """, (student_id, course_id))
            quiz_result = cur.fetchone()
            quiz_total = round(quiz_result[0], 2) if quiz_result[0] else 0
            quiz_percentage = round((quiz_total / 10) * 100, 2)  # Out of 10

            # Fetch assignment total from new assignments table
            cur.execute("""
                SELECT SUM(marks_obtained)
                FROM assignments
                WHERE student_id = ? AND course_id = ?
            """, (student_id, course_id))
            assign_result = cur.fetchone()
            assignment_total = round(assign_result[0], 2) if assign_result[0] else 0
            assign_percentage = round((assignment_total / 20) * 100, 2)  # Out of 20

            # Fetch ONLY midterm from marks table (final is NULL)
            cur.execute("""
                SELECT midterm
                FROM marks
                WHERE student_id = ? AND course_id = ?
            """, (student_id, course_id))
            marks_result = cur.fetchone()
            midterm = round(marks_result[0], 2) if marks_result else 0
            midterm_percentage = round((midterm / 20) * 100, 2)  # Out of 20

            # Calculate current total (without final)
            current_total = quiz_total + assignment_total + midterm
            current_percentage = round((current_total / 50) * 100, 2)  # Out of 50 (10+20+20)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Attendance", f"{fmt(attendance_pct)}%", 
                         delta="Good" if attendance_pct >= 75 else "Low")
            with col2:
                st.metric("Quizzes", f"{fmt(quiz_total)}/10", f"{fmt(quiz_percentage)}%")
            with col3:
                st.metric("Assignments", f"{fmt(assignment_total)}/20", f"{fmt(assign_percentage)}%")
            with col4:
                st.metric("Midterm", f"{fmt(midterm)}/20", f"{fmt(midterm_percentage)}%")

            # Show current performance (without final)
            st.markdown(f"**Current Performance: {fmt(current_total)}/50 ({fmt(current_percentage)}%)**")
            st.caption("Final exam (50 marks) is pending - Ask the AI Assistant for predictions")
            
            # Progress bar for current marks
            st.progress(current_percentage / 100)
            
            chart_df = pd.DataFrame({
                "Assessment": ["Quizzes", "Assignments", "Midterm"],
                "Score": [quiz_total, assignment_total, midterm],
                "Max": [10, 20, 20]
            })
            
            # Create a bar chart for current assessments only
            st.bar_chart(chart_df.set_index("Assessment")[["Score", "Max"]], use_container_width=True)
            
            st.markdown("---")
# ==================================================
# PAGE: COURSE OUTLINE
# ==================================================
elif page == "📋 Course Outline":
    st.title("📋 Course Outlines")
    
    selected_courses = course_selector("outlines")

    if not selected_courses:
        st.info("📚 Please select one or more courses to view course outlines.")
    else:
        for course_name in selected_courses:
            course_id = course_map[course_name]
            
            # Fetch credit hours
            cur.execute("""
                SELECT credit_hours
                FROM courses
                WHERE course_id = ?
            """, (course_id,))
            credit_result = cur.fetchone()
            credit_hours = credit_result[0] if credit_result else 3
            
            st.markdown(f"""
            <div class="course-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h4 style="margin:0; color: white;">📖 {course_name}</h4>
                    <span style="background: rgba(255,255,255,0.2); padding: 4px 8px; border-radius: 6px; font-size: 0.8rem;">
                        {credit_hours} Credit Hours
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Fetch course outline topics from database
            cur.execute("""
                SELECT topic_number, topic_name
                FROM course_outlines
                WHERE course_id = ?
                ORDER BY topic_number
            """, (course_id,))
            topics = cur.fetchall()

            if topics:
                # Create a nice table/display for topics
                topic_data = []
                for topic_num, topic_name in topics:
                    topic_data.append({
                        "Week/Topic #": f"Topic {topic_num}",
                        "Topic Name": topic_name
                    })
                
                df = pd.DataFrame(topic_data)
                
                # Display total topics count
                st.markdown(f"**Total Topics: {len(topics)}**")
                
                # Display topics in a styled table
                st.dataframe(
                    df, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Week/Topic #": st.column_config.TextColumn(
                            "Week/Topic #",
                            width="small",
                        ),
                        "Topic Name": st.column_config.TextColumn(
                            "Topic Name",
                            width="large",
                        ),
                    }
                )
                
                # Alternative: Display as expandable sections
                with st.expander("📑 View as List"):
                    for topic_num, topic_name in topics:
                        st.markdown(f"**Topic {topic_num}:** {topic_name}")
            else:
                st.info(f"No course outline available for {course_name}.")
            
            st.markdown("---")
# ==================================================
# PAGE: LECTURES
# ==================================================
elif page == "📚 Lectures":
    st.title("📚 Course Lectures")
    
    # Single course selection
    selected_course = st.selectbox(
        "📖 Select a course to view lectures",
        options=["-- Select a course --"] + course_names,
        key="lectures_course_selector"
    )
    
    if selected_course == "-- Select a course --":
        st.info("📚 Please select a course to display the respective lectures.")
    else:
        course_id = course_map[selected_course]
        
        # Fetch credit hours
        cur.execute("""
            SELECT credit_hours
            FROM courses
            WHERE course_id = ?
        """, (course_id,))
        credit_result = cur.fetchone()
        credit_hours = credit_result[0] if credit_result else 3
        
        # Course header
        st.markdown(f"""
        <div class="course-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h4 style="margin:0; color: white;">📖 {selected_course}</h4>
                <span style="background: rgba(255,255,255,0.2); padding: 4px 8px; border-radius: 6px; font-size: 0.8rem;">
                    {credit_hours} Credit Hours
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Fetch lectures for selected course
        cur.execute("""
            SELECT lecture_id, lecture_number, lecture_title, file_name, 
                   file_data, file_type, file_size
            FROM lectures
            WHERE course_id = ?
            ORDER BY lecture_number
        """, (course_id,))
        lectures = cur.fetchall()
        
        if lectures:
            # Lecture count with styled badge
            st.markdown(f"""
            <h3 style="margin-bottom: 1rem;">
                📑 Available Lectures 
                <span class="lecture-count-badge">{len(lectures)} lectures</span>
            </h3>
            """, unsafe_allow_html=True)
            
            # Display lectures in a clean layout
            for lecture in lectures:
                lecture_id, lecture_num, lecture_title, file_name, file_data, file_type, file_size = lecture
                
                # Format file size
                if file_size:
                    if file_size < 1024 * 1024:
                        size_str = f"{file_size / 1024:.1f} KB"
                    else:
                        size_str = f"{file_size / (1024 * 1024):.1f} MB"
                else:
                    size_str = "Unknown"
                
                # File type icon
                file_icons = {
                    'PDF': '📕',
                    'PPTX': '📊',
                    'PPT': '📊'
                }
                file_icon = file_icons.get(file_type, '📄')
                
                # MIME type for download
                mime_map = {
                    'PDF': 'application/pdf',
                    'PPTX': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                    'PPT': 'application/vnd.ms-powerpoint'
                }
                mime_type = mime_map.get(file_type, 'application/octet-stream')
                
                # Create a nice card-like row using columns
                col1, col2, col3 = st.columns([0.5, 4, 1])
                
                with col1:
                    st.markdown(f"<div class='lecture-icon'>{file_icon}</div>", unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"""
                    <div class='lecture-info'>
                        <h4>Lecture {lecture_num}: {lecture_title}</h4>
                        <p>{file_type} • {size_str} • {file_name}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col3:
                    st.download_button(
                        label="⬇️ Download",
                        data=file_data,
                        file_name=file_name,
                        mime=mime_type,
                        key=f"dl_{lecture_id}",
                        use_container_width=True
                    )
                
                # Subtle separator
                st.markdown("<hr style='margin: 0.5rem 0; border-color: #f1f5f9;'>", unsafe_allow_html=True)
        else:
            st.warning("📭 No lectures available for this course yet.")
            st.info("Lectures will be uploaded by the administration soon.")
# ==================================================
# PAGE: PERSONAL INFO
# ==================================================
elif page == "👤 Personal Info":
    st.title("👤 Student Profile")
    
    # Personal Information Section - Fixed layout
    st.markdown("### Personal Information")
    
    col1, col2 = st.columns(2, gap="medium")
    
    with col1:
        st.markdown("""
        <div class="personal-info-card">
            <div style="margin-bottom: 1rem;">
                <p style="margin:0; font-size: 0.9rem; color: #64748b; font-weight: 600;">FULL NAME</p>
                <h3 style="margin:0; color: #1e293b;">{}</h3>
            </div>
            <div>
                <p style="margin:0; font-size: 0.9rem; color: #64748b; font-weight: 600;">REGISTRATION NUMBER</p>
                <h3 style="margin:0; color: #1e293b;">{}</h3>
            </div>
        </div>
        """.format(student_name, registration_no), unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="personal-info-card">
            <div style="margin-bottom: 1rem;">
                <p style="margin:0; font-size: 0.9rem; color: #64748b; font-weight: 600;">CURRENT SEMESTER</p>
                <h3 style="margin:0; color: #1e293b;">{}</h3>
            </div>
            <div>
                <p style="margin:0; font-size: 0.9rem; color: #64748b; font-weight: 600;">STUDENT ID</p>
                <h3 style="margin:0; color: #1e293b;">{}</h3>
            </div>
        </div>
        """.format(semester, student_id), unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Course Enrollment Section with Credit Hours
    st.markdown("### 📚 Course Enrollment")
    
    if course_names:
        # Fetch credit hours for courses
        credit_hours_dict = {}
        for course_name in course_names:
            cur.execute("""
                SELECT credit_hours
                FROM courses
                WHERE course_name = ?
            """, (course_name,))
            result = cur.fetchone()
            credit_hours_dict[course_name] = result[0] if result else 3
        
        # Create columns for courses (3 per row)
        cols = st.columns(3, gap="medium")
        
        for idx, course in enumerate(course_names):
            with cols[idx % 3]:
                st.markdown(f"""
                <div class="course-enroll-card">
                    <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
                        <div style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); 
                                    color: white; width: 32px; height: 32px; border-radius: 8px; 
                                    display: flex; align-items: center; justify-content: center; 
                                    font-weight: bold;">
                            {idx + 1}
                        </div>
                        <h4 style="margin:0; color: #1e293b;">Course {idx + 1}</h4>
                    </div>
                    <p style="margin:0; font-size: 1rem; font-weight: 600; color: #334155;">{course}</p>
                    <p style="margin:0.5rem 0 0 0; font-size: 0.85rem; color: #64748b;">
                        ⏱️ Credit Hours: {credit_hours_dict[course]}
                    </p>
                </div>
                """, unsafe_allow_html=True)
        
        # Calculate and show total credit hours
        total_credits = sum(credit_hours_dict.values())
        st.info(f"📊 **Total Credit Hours this semester: {total_credits}**")
        
    else:
        st.info("No courses enrolled for this semester.")
# ==================================================
# PAGE: QUIZZES
# ==================================================
elif page == "📝 Quizzes":
    st.title("📝 Quiz Performance")
    
    selected_courses = course_selector("quizzes")

    if not selected_courses:
        st.info("📚 Please select one or more courses to view quiz results.")
    else:
        for course_name in selected_courses:
            course_id = course_map[course_name]
            
            st.markdown(f"""
            <div class="course-card">
                <h4 style="margin:0; color: white;">📖 {course_name}</h4>
            </div>
            """, unsafe_allow_html=True)

            # Fetch quiz marks from new quizzes table
            cur.execute("""
                SELECT quiz_name, marks_obtained, max_marks
                FROM quizzes
                WHERE student_id = ? AND course_id = ?
                ORDER BY quiz_name
            """, (student_id, course_id))
            quizzes = cur.fetchall()

            if quizzes:
                # Convert to DataFrame
                quiz_data = []
                total_obtained = 0
                total_max = 0
                
                for quiz_name, marks_obtained, max_marks in quizzes:
                    quiz_data.append({
                        "Quiz": quiz_name,
                        "Marks Obtained": fmt(marks_obtained),
                        "Max Marks": fmt(max_marks),
                        "Percentage": fmt((marks_obtained / max_marks) * 100) + "%"
                    })
                    total_obtained += marks_obtained
                    total_max += max_marks
                
                df = pd.DataFrame(quiz_data)
                
                col1, col2 = st.columns([2, 1], gap="medium")
                with col1:
                    st.dataframe(df, use_container_width=True, hide_index=True)
                with col2:
                    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
                    st.metric("Total Obtained", f"{fmt(total_obtained)}/10")
                    st.metric("Average per Quiz", fmt(total_obtained / 4))
                    st.metric("Quiz Percentage", fmt((total_obtained / 10) * 100) + "%")
            else:
                st.info("No quiz data available for this course.")
            
            st.markdown("---")
# ==================================================
# PAGE: ASSIGNMENTS
# ==================================================
elif page == "📂 Assignments":
    st.title("📂 Assignment Performance")
    
    selected_courses = course_selector("assignments")

    if not selected_courses:
        st.info("📚 Please select one or more courses to view assignment results.")
    else:
        for course_name in selected_courses:
            course_id = course_map[course_name]
            
            st.markdown(f"""
            <div class="course-card">
                <h4 style="margin:0; color: white;">📖 {course_name}</h4>
            </div>
            """, unsafe_allow_html=True)

            # Fetch assignment marks from new assignments table
            cur.execute("""
                SELECT assignment_name, marks_obtained, max_marks
                FROM assignments
                WHERE student_id = ? AND course_id = ?
                ORDER BY assignment_name
            """, (student_id, course_id))
            assignments = cur.fetchall()

            if assignments:
                # Convert to DataFrame
                assign_data = []
                total_obtained = 0
                total_max = 0
                
                for assign_name, marks_obtained, max_marks in assignments:
                    assign_data.append({
                        "Assignment": assign_name,
                        "Marks Obtained": fmt(marks_obtained),
                        "Max Marks": fmt(max_marks),
                        "Percentage": fmt((marks_obtained / max_marks) * 100) + "%"
                    })
                    total_obtained += marks_obtained
                    total_max += max_marks
                
                df = pd.DataFrame(assign_data)
                
                col1, col2 = st.columns([2, 1], gap="medium")
                with col1:
                    st.dataframe(df, use_container_width=True, hide_index=True)
                with col2:
                    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
                    st.metric("Total Obtained", f"{fmt(total_obtained)}/20")
                    st.metric("Average per Assignment", fmt(total_obtained / 4))
                    st.metric("Assignment Percentage", fmt((total_obtained / 20) * 100) + "%")
            else:
                st.info("No assignment data available for this course.")
            
            st.markdown("---")
# ==================================================
# PAGE: ATTENDANCE
# ==================================================
elif page == "📅 Attendance":
    st.title("📅 Attendance Records")
    
    selected_courses = course_selector("attendance")

    if not selected_courses:
        st.info("📚 Please select one or more courses to view attendance records.")
    else:
        for course_name in selected_courses:
            course_id = course_map[course_name]
            
            st.markdown(f"""
            <div class="course-card">
                <h4 style="margin:0; color: white;">📖 {course_name}</h4>
            </div>
            """, unsafe_allow_html=True)

            cur.execute("""
                SELECT classes_attended, total_classes
                FROM attendance
                WHERE student_id = ? AND course_id = ?
            """, (student_id, course_id))
            att = cur.fetchone()

            if att:
                attendance_pct = round((att[0] / att[1]) * 100, 2) if att else 0
                
                col1, col2, col3 = st.columns(3, gap="medium")
                with col1:
                    st.metric("Classes Attended", att[0])
                with col2:
                    st.metric("Total Classes", att[1])
                with col3:
                    st.metric("Attendance Percentage", f"{fmt(attendance_pct)}%")
                
                st.progress(int(attendance_pct) / 100)
                
                if attendance_pct < 75:
                    st.warning("⚠️ Your attendance is below the required 75%. Please attend classes regularly.")
                else:
                    st.success("✅ Great! Your attendance meets the requirement.")
            else:
                st.info("No attendance data available for this course.")
            
            st.markdown("---")

            # ==================================================
# PAGE: AI ASSISTANT (CHATBOT)
# ==================================================
elif page == "🤖 AI Assistant":

    # --------------------------------------------------
    # CSS — ONLY targets the sidebar upload widget.
    # The main chat area is left completely untouched.
    # --------------------------------------------------
    st.markdown("""
    <style>
        /* ── File uploader box: visible on dark-blue sidebar ── */
        section[data-testid="stSidebar"] [data-testid="stFileUploader"] {
            background: rgba(255, 255, 255, 0.12) !important;
            border: 1.5px dashed rgba(255, 255, 255, 0.45) !important;
            border-radius: 10px !important;
            padding: 6px !important;
        }

        /* ── All text inside the uploader ── */
        section[data-testid="stSidebar"] [data-testid="stFileUploader"] label,
        section[data-testid="stSidebar"] [data-testid="stFileUploader"] span,
        section[data-testid="stSidebar"] [data-testid="stFileUploader"] p,
        section[data-testid="stSidebar"] [data-testid="stFileUploader"] small,
        section[data-testid="stSidebar"] [data-testid="stFileUploader"] div {
            color: #ffffff !important;
            opacity: 1 !important;
        }

        /* ── "Browse files" / "Upload" button ── */
        section[data-testid="stSidebar"] [data-testid="stFileUploader"] button {
            background: rgba(255, 255, 255, 0.20) !important;
            color: #ffffff !important;
            border: 1px solid rgba(255, 255, 255, 0.40) !important;
            border-radius: 7px !important;
            font-weight: 600 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stFileUploader"] button:hover {
            background: rgba(255, 255, 255, 0.32) !important;
        }

        /* ── st.info / st.success / st.error in sidebar ── */
        section[data-testid="stSidebar"] [data-testid="stAlert"] {
            background: rgba(255, 255, 255, 0.12) !important;
            border: 1px solid rgba(255, 255, 255, 0.25) !important;
            border-radius: 9px !important;
        }
        section[data-testid="stSidebar"] [data-testid="stAlert"] p,
        section[data-testid="stSidebar"] [data-testid="stAlert"] span,
        section[data-testid="stSidebar"] [data-testid="stAlert"] div {
            color: #ffffff !important;
        }

        /* ── "Remove File" button in sidebar ── */
        section[data-testid="stSidebar"] .stButton > button {
            background: rgba(239, 68, 68, 0.18) !important;
            border: 1.5px solid rgba(239, 68, 68, 0.50) !important;
            color: #fca5a5 !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
        }
        section[data-testid="stSidebar"] .stButton > button:hover {
            background: rgba(239, 68, 68, 0.35) !important;
            color: #ffffff !important;
        }
    </style>
    """, unsafe_allow_html=True)

    st.title("🤖 EduGuide-Academic AI Assistant")
    st.caption("Your intelligent companion for academic queries, predictions, and study planning.")

    # ----------------------------------
    # Import notes functions from agent.py
    # ----------------------------------
    from backend.agentic_architecture.agent import (
        extract_pages_from_file,
        load_notes_file,
        clear_notes_store,
        notes_file_loaded,
        get_notes_summary,
    )

    # ----------------------------------
    # Sidebar: File Upload for Notes Agent
    # ----------------------------------
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 📖 Upload Lecture Notes")
        st.caption("Upload any file and ask me to explain it.")

        # ── Fix text visibility in dark sidebar ───────────────
        st.markdown("""
            <style>
            /* File uploader label text */
            [data-testid="stFileUploaderDropzoneInstructions"] p,
            [data-testid="stFileUploaderDropzoneInstructions"] span,
            [data-testid="stFileUploaderDropzone"] p,
            [data-testid="stFileUploaderDropzone"] span,
            [data-testid="stFileUploaderDropzone"] small,
            .stFileUploader label,
            .stFileUploader p,
            .stFileUploader span,
            section[data-testid="stSidebar"] .stFileUploader label p,
            section[data-testid="stSidebar"] .stFileUploader span {
                color: #FFFFFF !important;
                opacity: 1 !important;
            }
            /* Browse files button */
            section[data-testid="stSidebar"] .stFileUploader button {
                color: #FFFFFF !important;
                border-color: #FFFFFF !important;
                background-color: transparent !important;
            }
            /* Drag and drop zone border */
            section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
                border-color: rgba(255, 255, 255, 0.4) !important;
            }
            /* Caption text */
            section[data-testid="stSidebar"] .stCaption p {
                color: rgba(255, 255, 255, 0.7) !important;
                }
            /* Success and info messages */
            section[data-testid="stSidebar"] .stSuccess p,
            section[data-testid="stSidebar"] .stInfo p {
                color: #FFFFFF !important;
            }
            
            section[data-testid="stSidebar"] * {
                color: #FFFFFF !important;
            }
            
            
            </style>
        """, unsafe_allow_html=True)

        uploaded_file = st.file_uploader(
            "Supported: PDF, PowerPoint (.pptx), Word (.docx), Images",
            type=["pdf", "pptx", "docx", "png", "jpg", "jpeg", "webp"],
            key="notes_uploader",
        )

        if uploaded_file is not None:
            if st.session_state.get("notes_filename") != uploaded_file.name:
                with st.spinner(f"Reading '{uploaded_file.name}'..."):
                    try:
                        import tempfile
                        import os
    
                        suffix = os.path.splitext(uploaded_file.name)[1]

                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                            tmp.write(uploaded_file.read())
                            tmp_path = tmp.name

                        pages = extract_pages_from_file(tmp_path)
                        os.unlink(tmp_path)

                        load_notes_file(pages, uploaded_file.name)
                        st.session_state.notes_filename = uploaded_file.name

                        st.success(
                            f"✅ **{uploaded_file.name}**\n\n"
                            f"{len(pages)} "
                            f"{'slide' if uploaded_file.name.endswith('.pptx') else 'page'}(s) loaded. "
                            f"Now ask me anything about it!"
                        )
    
                    except Exception as e:
                        st.error(f"Could not read file: {e}")
    
        if notes_file_loaded():
            st.info(f"📄 **Loaded:** {get_notes_summary()}")
    
            if st.button("🗑️ Remove File", use_container_width=True):
                clear_notes_store()
                st.session_state.notes_filename = ""
                st.rerun()

    # ----------------------------------
    # Initialize session state
    # FIX: initialise messages AND welcome together in one block
    # so the welcome message is always present on first load.
    # ----------------------------------
    if "messages" in st.session_state:
        welcome_msg = (
            f"👋 **Hello {student_name.split()[0]}!** I'm your Academic AI Companion.\n\n"
            "I'm here to assist you with:\n\n"
            "🔍 **Information Retrieval** - Query your LMS data instantly\n\n"
            "📈 **Grade Predictions** - Forecast your final exam performance\n\n"
            "📝 **Study Plans** - Get personalized rescue and study strategies\n\n"
            "🎓 **GPA Calculator** - Predict your semester GPA\n\n"
            "📖 **Notes Assistant** - Upload any lecture file and ask me to explain it\n\n"
            "💡 **Academic Insights** - Receive tailored recommendations\n\n"
            "Feel free to ask me anything about your courses, grades, or study strategies!\n\n"
            "_💡 Tip: Upload a lecture file from the sidebar to get started with Notes Assistant._"
        )
        st.session_state.messages = [{"role": "assistant", "content": welcome_msg}]

    # ----------------------------------
    # Display chat history
    # ----------------------------------
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ----------------------------------
    # User input
    # ----------------------------------
    if notes_file_loaded():
        chat_placeholder = "Ask about your notes, grades, predictions... e.g. 'Explain slide 3'"
    else:
        chat_placeholder = "Ask about your grades, predictions, study plans..."

    prompt = st.chat_input(chat_placeholder)

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        # ----------------------------------
        # AI response using OpenAI Agent SDK
        # ----------------------------------
        try:
            with st.spinner("🤔 Analyzing with AI Agents..."):
                import asyncio

                triage_agent = build_agents(student_id, conn)

                result = asyncio.run(
                    Runner.run(
                        starting_agent=triage_agent,
                        input=prompt,
                        run_config=config,
                        session=memory,
                        max_turns=25
                    )
                )

                bot_reply = result.final_output

        except ImportError as e:
            bot_reply = (
                "⚠️ **Agent System Error**\n\n"
                "The AI agent system is currently unavailable. Please try again later.\n\n"
                f"Error: `{str(e)}`"
            )

        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            print(f"Agent Error in Dashboard: {str(e)}")
            print(error_details)

            bot_reply = (
                "⚠️ **System Error**\n\n"
                f"I encountered an issue while processing your request: `{str(e)}`\n\n"
                f"Hi {student_name}! 👋 Please try:\n"
                "1. Rephrasing your question\n"
                "2. Specifying the course name clearly\n"
                "3. Asking about a different aspect\n\n"
                "Examples:\n"
                "• \"What are my quiz marks in Calculus?\"\n"
                "• \"Predict my final score in Physics\"\n"
                "• \"Create a study plan for Programming\"\n"
                "• \"Explain slide 3 of my uploaded notes\""
            )

        st.session_state.messages.append({"role": "assistant", "content": bot_reply})

        with st.chat_message("assistant"):
            st.markdown(bot_reply)
            
            
# --------------------------------------------------
# CLOSE DB
# --------------------------------------------------
conn.close()