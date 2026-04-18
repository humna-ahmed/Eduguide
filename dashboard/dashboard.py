# dashboard/dashboard.py
import streamlit as st
import sqlite3
import pandas as pd
import sys
import os
import asyncio


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
    
    page = st.radio(
        "Navigation",
        [
            "🏠 Dashboard",
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
    st.title("🤖 EduGuide-Academic AI Assistant")
    st.caption("Your intelligent companion for academic queries, predictions, and study planning.")

    # ----------------------------------
    # Initialize session state
    # ----------------------------------
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "welcome_shown" not in st.session_state:
        welcome_msg = (
            f"👋 **Hello {student_name.split()[0]}!** I'm your Academic AI Companion.\n\n"
            "I'm here to assist you with:\n\n"
            "🔍 **Information Retrieval** - Query your LMS data instantly\n\n"
            "📈 **Grade Predictions** - Forecast your final exam performance\n\n"
            "📝 **Study Plans** - Get personalized rescue and study strategies\n\n"
            "💡 **Academic Insights** - Receive tailored recommendations\n\n"
            "Feel free to ask me anything about your courses, grades, or study strategies!"
        )
        st.session_state.messages.append(
            {"role": "assistant", "content": welcome_msg}
        )
        st.session_state.welcome_shown = True

    # ----------------------------------
    # Display chat history
    # ----------------------------------
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ----------------------------------
    # User input
    # ----------------------------------
    prompt = st.chat_input("Type your question here...")

    if prompt:
        # Show user message
        st.session_state.messages.append(
            {"role": "user", "content": prompt}
        )
        with st.chat_message("user"):
            st.markdown(prompt)

        # ----------------------------------
        # AI response using OpenAI Agent SDK
        # ----------------------------------
        try:
            # Import the agent runner function
            from backend.agentic_architecture import run_agent_query
            
            with st.spinner("🤔 Analyzing with AI Agents..."):
                # Use the new agent system - Note: using asyncio.run() to handle async
                import asyncio
                # Build triage agent using new merged agent.py
                triage_agent = build_agents(student_id, conn)

                result = asyncio.run(
                    Runner.run(
                        starting_agent=triage_agent,
                        input=prompt,
                        run_config=config,
                        session=memory
                    )
                )

                bot_reply = result.final_output


        except ImportError as e:
            # Fallback if agent system is not available
            st.error(f"Agent system not available: {str(e)}")
            bot_reply = (
                f"⚠️ **Agent System Error**\n\n"
                f"The AI agent system is currently unavailable. Please try again later.\n\n"
                f"Error: `{str(e)}`"
            )
            
        except Exception as e:
            # General error handling
            import traceback
            error_details = traceback.format_exc()
            print(f"Agent Error in Dashboard: {str(e)}")
            print(error_details)
            
            bot_reply = (
                f"⚠️ **System Error**\n\n"
                f"I encountered an issue while processing your request: `{str(e)}`\n\n"
                f"Hi {student_name}! 👋 Please try:\n"
                f"1. Rephrasing your question\n"
                f"2. Specifying the course name clearly\n"
                f"3. Asking about a different aspect\n\n"
                f"Examples:\n"
                f"• \"What are my quiz marks in Calculus?\"\n"
                f"• \"Predict my final score in Physics\"\n"
                f"• \"Create a study plan for Programming\""
            )

        # Store and display assistant reply
        st.session_state.messages.append(
            {"role": "assistant", "content": bot_reply}
        )
        with st.chat_message("assistant"):
            st.markdown(bot_reply)
# --------------------------------------------------
# CLOSE DB
# --------------------------------------------------
conn.close()