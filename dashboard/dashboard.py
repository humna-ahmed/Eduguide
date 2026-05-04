# dashboard/dashboard.py
import streamlit as st
import streamlit.components.v1 as components
import sqlite3
import pandas as pd
import sys
import os
import asyncio
import datetime

# --------------------------------------------------
# ADD PARENT DIRECTORY TO PYTHON PATH
# --------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from backend.agentic_architecture.agent import build_agents, config, memory
from agents import Runner

# --------------------------------------------------
# PAGE CONFIG — sidebar ALWAYS expanded
# --------------------------------------------------
st.set_page_config(
    page_title="Academic Portal | Student LMS",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --------------------------------------------------
# CSS
# --------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&family=Lato:wght@300;400;700&display=swap');

#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* ── Sidebar Toggle Button - Always Visible ── */
[data-testid="collapsedControl"] {
    visibility: visible !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    position: fixed !important;
    top: 70px !important;
    left: 10px !important;
    z-index: 999999 !important;
    background: #E8A020 !important;
    color: white !important;
    border-radius: 8px !important;
    width: 32px !important;
    height: 32px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
    cursor: pointer !important;
    border: 2px solid #C8860A !important;
    opacity: 1 !important;
    min-width: 32px !important;
    min-height: 32px !important;
}

[data-testid="collapsedControl"]:hover {
    transform: scale(1.1) !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4) !important;
}

[data-testid="collapsedControl"] * {
    visibility: visible !important;
    opacity: 1 !important;
}

/* ── Sidebar Styling ── */
[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 2px solid #e2e8f0 !important;
}

[data-testid="stSidebar"] > div:first-child {
    padding-top: 0.5rem !important;
}

[data-testid="stSidebar"] h1 {
    font-family: 'Poppins', sans-serif !important;
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    color: #1e293b !important;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 0.5rem;
    margin-bottom: 0.5rem !important;
}

[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label {
    color: #4a5568 !important;
}

[data-testid="stSidebar"] strong { 
    color: #1e293b !important; 
}

[data-testid="stSidebar"] em { 
    color: #94a3b8 !important; 
    font-size: 0.82rem !important; 
}

[data-testid="stSidebar"] .stRadio > div {
    gap: 2px !important;
    width: 100% !important;                    /* ADD THIS */

}

[data-testid="stSidebar"] .stRadio label {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;                    /* ADD THIS - Full width */
    box-sizing: border-box !important;         /* ADD THIS - Include padding in width */
    padding: 0.6rem 1rem !important;
    border-radius: 8px !important;
    border-left: 3px solid transparent !important;
    font-size: 0.93rem !important;
    font-weight: 500 !important;
    cursor: pointer !important;
    transition: background 0.15s, border-color 0.15s !important;
    background: transparent !important;
    color: #4a5568 !important;
    margin-bottom: 1px !important;
}

[data-testid="stSidebar"] .stRadio label:hover {
    background: #FFF3DC !important;
    border-left-color: #E8A020 !important;
    color: #C8860A !important;
    width: 100% !important;                    /* ADD THIS */
    box-sizing: border-box !important;         /* ADD THIS */
}

[data-testid="stSidebar"] .stRadio [data-baseweb="radio"] > div:first-child {
    display: none !important;
}

/* ── Main content area ── */
.main { background: #f4f6f9 !important; }

.main .block-container {
    padding-top: 0.5rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 100% !important;
}

h1 {
    color: #1e293b !important;
    font-weight: 700 !important;
    border-bottom: 3px solid #E8A020 !important;
    padding-bottom: 0.7rem !important;
    margin-bottom: 1.2rem !important;
}

h2, h3 { color: #334155 !important; font-weight: 600 !important; }

[data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 700 !important; color: #1e293b !important; }
[data-testid="stMetricLabel"] { font-size: 0.82rem !important; font-weight: 600 !important; color: #64748b !important; text-transform: uppercase !important; letter-spacing: .05em !important; }

.stProgress > div > div { background-color: #E8A020 !important; }

section.main .stButton > button {
    background: linear-gradient(135deg, #C8860A 0%, #E8A020 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}

.stAlert { border-radius: 8px !important; border-left: 4px solid #E8A020 !important; }

.welcome-banner {
    background: linear-gradient(135deg, #C8860A 0%, #E8A020 100%);
    color: white; padding: 1.4rem; border-radius: 12px;
    margin-bottom: 1.5rem; box-shadow: 0 4px 12px rgba(200,120,0,0.25);
}

.course-card {
    background: linear-gradient(135deg, #C8860A 0%, #E8A020 100%);
    padding: 1.1rem; border-radius: 12px; color: white;
    margin-bottom: 1.2rem; box-shadow: 0 3px 10px rgba(200,120,0,0.2);
}

.personal-info-card, .course-enroll-card {
    background: white; padding: 1.2rem; border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07); border: 1px solid #e2e8f0;
    margin-bottom: 0.5rem;
}

.lecture-count-badge {
    display: inline-block;
    background: linear-gradient(135deg, #C8860A, #E8A020);
    color: white; padding: .2rem .7rem; border-radius: 20px;
    font-size: .82rem; font-weight: 600; margin-left: .5rem;
}

[data-testid="stChatMessage"] {
    background: white !important; border-radius: 12px !important;
    padding: 1rem !important; margin-bottom: .8rem !important;
    box-shadow: 0 1px 3px rgba(0,0,0,.07) !important;
}

/* Ensure iframe takes full width */
.stApp > header + div > div > iframe {
    width: 100% !important;
}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# HELPER
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

from backend.agentic_architecture.agent import clear_prediction_cache, clear_notes_store

if student_id and st.session_state.get("current_student_id") != student_id:
    clear_prediction_cache()
    clear_notes_store()
    st.session_state.current_student_id = student_id
    st.session_state.messages = []
    st.session_state.welcome_shown = False
    st.session_state.notes_filename = ""

if not student_id:
    st.error("🔒 Unauthorized Access")
    st.warning("Please login through the authentication portal.")
    st.stop()

# --------------------------------------------------
# DATABASE
# --------------------------------------------------
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# --------------------------------------------------
# FETCH STUDENT INFO
# --------------------------------------------------
cur.execute("SELECT name, registration_no, semester FROM students WHERE student_id = ?", (student_id,))
student = cur.fetchone()

if not student:
    st.error("❌ Student Record Not Found")
    st.stop()

student_name, registration_no, semester = student

# --------------------------------------------------
# FETCH COURSES
# --------------------------------------------------
cur.execute("""
    SELECT DISTINCT c.course_id, c.course_name
    FROM courses c JOIN marks m ON m.course_id = c.course_id
    WHERE m.student_id = ?
""", (student_id,))
courses = cur.fetchall()
course_map   = {name: cid for cid, name in courses}
course_names = list(course_map.keys())

# --------------------------------------------------
# INITIALS
# --------------------------------------------------
parts    = student_name.strip().split()
initials = (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")).upper()

# --------------------------------------------------
# TOP NAVBAR - Fixed layout, proper logout redirect
# --------------------------------------------------
navbar_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box;font-family:'Poppins',sans-serif;}}
body{{background:transparent;overflow:hidden;margin:0;}}
.bar{{
    width:100%;height:60px;
    background:linear-gradient(90deg,#C8860A 0%,#E8A020 55%,#F5B93A 100%);
    display:flex;align-items:center;justify-content:space-between;
    padding:0 20px 0 16px;
    box-shadow:0 3px 10px rgba(150,80,0,.35);
    gap:8px;
}}
.left{{display:flex;align-items:center;gap:10px;flex:0 0 auto;min-width:0;}}
.logo{{
    width:40px;height:40px;border-radius:50%;background:#1B2A6B;
    border:2px solid rgba(255,255,255,.6);display:flex;align-items:center;
    justify-content:center;font-size:15px;font-weight:800;color:#E8A020;flex-shrink:0;
}}
.brand-text{{display:flex;flex-direction:column;line-height:1.25;}}
.uname{{font-size:14px;font-weight:700;color:#fff;text-shadow:0 1px 3px rgba(0,0,0,.25);white-space:nowrap;}}
.usub{{font-size:11px;color:rgba(255,255,255,.85);white-space:nowrap;}}
.center{{
    flex:1 1 auto;
    text-align:center;
    font-size:16px;font-weight:700;color:#fff;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
    text-shadow:0 1px 4px rgba(0,0,0,.22);
    padding:0 8px;
    min-width:0;
}}
.right{{display:flex;align-items:center;gap:14px;flex:0 0 auto;}}
.clock{{
    background:#1a3300;border:2px solid rgba(0,0,0,.4);border-radius:9px;
    padding:4px 12px;text-align:center;min-width:76px;
    box-shadow:inset 0 2px 4px rgba(0,0,0,.3);cursor:default;
}}
.ct{{display:block;font-size:16px;font-weight:700;color:#fff;letter-spacing:1px;line-height:1.1;}}
.ca{{display:block;font-size:9px;font-weight:600;color:rgba(255,255,255,.72);letter-spacing:1.5px;}}
.bell{{font-size:17px;color:rgba(255,255,255,.88);cursor:default;}}
.pb{{
    display:flex;align-items:center;gap:8px;cursor:pointer;
    background:none;border:none;padding:5px 8px;border-radius:8px;
    transition:background .2s;color:white;
}}
.pb:hover{{background:rgba(255,255,255,.18);}}
.pi{{
    width:31px;height:31px;border-radius:50%;background:#1B2A6B;
    border:2px solid rgba(255,255,255,.6);display:flex;align-items:center;
    justify-content:center;font-size:12px;font-weight:700;color:#fff;flex-shrink:0;
}}
.pn{{font-size:13px;font-weight:600;color:#fff;letter-spacing:.4px;white-space:nowrap;}}
.ar{{font-size:9px;color:rgba(255,255,255,.8);transition:transform .25s;display:inline-block;}}
@media(max-width:900px){{.center{{display:none;}}}}
@media(max-width:600px){{.pn{{display:none;}}}}

.dropdown{{
    display:none;position:fixed;z-index:99999;
    background:#fff;border-radius:12px;
    box-shadow:0 12px 40px rgba(0,0,0,0.3);
    border:1px solid #e2e8f0;min-width:220px;overflow:hidden;
}}
.dd-header{{
    padding:14px 16px 12px;
    background:linear-gradient(135deg,#1B2A6B,#2A3F8F);
}}
.dd-name{{font-size:15px;font-weight:700;color:#fff;margin-bottom:2px;}}
.dd-reg{{font-size:12px;color:rgba(255,255,255,.75);}}
.logout-btn{{
    display:flex;align-items:center;gap:10px;
    width:100%;padding:14px 16px;
    font-size:14px;font-weight:600;color:#dc2626;
    border:none;border-top:1px solid #e2e8f0;
    background:#fff;cursor:pointer;
    font-family:'Poppins',sans-serif;
    text-align:left;
    transition:background .15s;
}}
.logout-btn:hover{{background:#fff1f1;}}
</style>
</head>
<body>
<nav class="bar">
  <div class="left">
    <div class="logo">{initials[0]}</div>
    <div class="brand-text">
      <span class="uname">Bahria University</span>
      <span class="usub">Learning Portal</span>
    </div>
  </div>

  <div class="center">Learning Management System</div>

  <div class="right">
    <div class="clock">
      <span class="ct" id="ct">--:--</span>
      <span class="ca" id="ca">--</span>
    </div>
    <span class="bell">🔔</span>
    <button class="pb" id="profileBtn" onclick="toggleDropdown()">
      <div class="pi">{initials}</div>
      <span class="pn">{student_name.upper()}</span>
      <span class="ar" id="arrow">▼</span>
    </button>
  </div>
</nav>


<script>
function tick(){{
    var n=new Date(),h=n.getHours(),m=n.getMinutes();
    var a=h>=12?'PM':'AM';h=h%12||12;
    document.getElementById('ct').textContent=String(h).padStart(2,'0')+':'+String(m).padStart(2,'0');
    document.getElementById('ca').textContent=a;
}}
tick();setInterval(tick,1000);

var isOpen=false;
var parentDd=null;

function createParentDropdown(){{
    if(parentDd)return;
    var pdoc=window.parent.document;

    parentDd=pdoc.createElement('div');
    parentDd.id='lms_dropdown';
    parentDd.innerHTML=`
        <div style="background:linear-gradient(135deg,#1B2A6B,#2A3F8F);padding:14px 16px 12px;border-radius:12px 12px 0 0;">
            <div style="font-size:15px;font-weight:700;color:#fff;margin-bottom:2px;">{student_name}</div>
            <div style="font-size:12px;color:rgba(255,255,255,.75);">REG: {registration_no}</div>
        </div>
        <button id="lms_logout_btn"
            style="display:flex;align-items:center;gap:10px;width:100%;padding:14px 16px;
                   font-size:14px;font-weight:600;color:#dc2626;border:none;
                   border-top:1px solid #e2e8f0;background:#fff;cursor:pointer;
                   font-family:Poppins,sans-serif;text-align:left;border-radius:0 0 12px 12px;"
            onmouseover="this.style.background='#fff1f1'"
            onmouseout="this.style.background='#fff'">
            🚪 &nbsp;Logout
        </button>
    `;
    parentDd.style.cssText=`
        display:none;
        position:fixed;
        z-index:2147483647;
        background:#fff;
        border-radius:12px;
        box-shadow:0 12px 40px rgba(0,0,0,0.3);
        border:1px solid #e2e8f0;
        min-width:220px;
        overflow:hidden;
    `;
    pdoc.body.appendChild(parentDd);

    pdoc.getElementById('lms_logout_btn').addEventListener('click',function(){{
        parentDd.style.display='none';
        isOpen=false;
        window.parent.postMessage('lms_logout', '*');
    }});

    pdoc.addEventListener('click',function(e){{
        if(!isOpen)return;
        if(parentDd.contains(e.target))return;
        closeDropdown();
    }},true);
}}

function getIframeOffset(){{
    var iframes=window.parent.document.getElementsByTagName('iframe');
    for(var i=0;i<iframes.length;i++){{
        try{{
            if(iframes[i].contentWindow===window){{
                return iframes[i].getBoundingClientRect();
            }}
        }}catch(e){{}}
    }}
    return {{top:0,left:0,right:0,bottom:0}};
}}

function positionDropdown(){{
    var ir=getIframeOffset();
    var btn=document.getElementById('profileBtn');
    var br=btn.getBoundingClientRect();
    var absTop=ir.top+br.bottom+5;
    var absRight=window.parent.innerWidth-(ir.left+br.right);
    parentDd.style.top=absTop+'px';
    parentDd.style.right=absRight+'px';
    parentDd.style.left='auto';
}}

function openDropdown(){{
    createParentDropdown();
    positionDropdown();
    parentDd.style.display='block';
    document.getElementById('arrow').style.transform='rotate(180deg)';
    isOpen=true;
}}

function closeDropdown(){{
    if(parentDd)parentDd.style.display='none';
    document.getElementById('arrow').style.transform='rotate(0deg)';
    isOpen=false;
}}

function toggleDropdown(){{
    if(isOpen){{closeDropdown();}}else{{openDropdown();}}
}}

document.addEventListener('keydown',function(e){{
    if(e.key==='Escape'&&isOpen)closeDropdown();
}});

window.addEventListener('resize',function(){{
    if(isOpen)positionDropdown();
}});
</script>
<script>
// This runs in the PARENT window context via postMessage
window.parent.addEventListener('message', function(e) {{
    if (e.data === 'lms_logout') {{
        window.location.href = 'http://127.0.0.1:5000/';
    }}
}});
</script>
</body>
</html>"""

components.html(navbar_html, height=62, scrolling=False)

# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------
# Add this in the sidebar section (around line 400-420 in your code)
with st.sidebar:
    st.markdown("# 🎓 Academic Portal")
    st.markdown(f"**Welcome, {student_name.split()[0]}!**")
    st.markdown(f"*{registration_no}*")
    st.markdown("---")
    
    page = st.radio(
        "Navigation",
        [
            "🏠 Dashboard",
            "📋 Course Outline",
            "📚 Lectures",
            "👤 Personal Info",
            "📝 Quizzes",
            "📂 Assignments",
            "📅 Attendance",
            "🤖 AI Assistant",
        ],
        label_visibility="collapsed",
    )

     # ADD THIS LOGOUT BUTTON
    if st.button("🚪 Logout", use_container_width=True, type="primary"):
        # Clear session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        # Redirect to login
        st.markdown('<meta http-equiv="refresh" content="0; url=http://127.0.0.1:5000/">', unsafe_allow_html=True)
        st.stop()
    
    st.markdown("---")
    
# --------------------------------------------------
# HELPER: course selector
# --------------------------------------------------
def course_selector(page_key):
    options = ["Select All Courses"] + course_names
    selected = st.multiselect(
        "📚 Select course(s) to view", options=options, key=f"courses_{page_key}"
    )
    return course_names if "Select All Courses" in selected else selected

# ==================================================
# PAGE: DASHBOARD
# ==================================================
if page == "🏠 Dashboard":
    st.title("📊 Academic Dashboard")

    st.markdown(f"""
    <div class="welcome-banner">
        <h3 style="margin:0;color:white;">Welcome back, {student_name}! 👋</h3>
        <p style="margin:.4rem 0 0;opacity:.9;font-size:.93rem;">Here's your academic overview for Semester {semester}</p>
    </div>
    """, unsafe_allow_html=True)

    selected_courses = course_selector("dashboard")

    if not selected_courses:
        st.info("📚 Please select one or more courses to view your academic performance.")
    else:
        for course_name in selected_courses:
            course_id = course_map[course_name]

            cur.execute("SELECT credit_hours FROM courses WHERE course_id=?", (course_id,))
            cr = cur.fetchone(); credit_hours = cr[0] if cr else 3

            st.markdown(f"""
            <div class="course-card">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <h4 style="margin:0;color:white;">📖 {course_name}</h4>
                <span style="background:rgba(255,255,255,.2);padding:4px 10px;border-radius:6px;font-size:.8rem;">{credit_hours} Credit Hours</span>
              </div>
            </div>
            """, unsafe_allow_html=True)

            cur.execute("SELECT classes_attended,total_classes FROM attendance WHERE student_id=? AND course_id=?", (student_id, course_id))
            att = cur.fetchone(); att_pct = round((att[0]/att[1])*100, 2) if att and att[1] > 0 else 0

            cur.execute("SELECT SUM(marks_obtained) FROM quizzes WHERE student_id=? AND course_id=?", (student_id, course_id))
            qr = cur.fetchone(); q_tot = round(qr[0], 2) if qr[0] else 0

            cur.execute("SELECT SUM(marks_obtained) FROM assignments WHERE student_id=? AND course_id=?", (student_id, course_id))
            ar = cur.fetchone(); a_tot = round(ar[0], 2) if ar[0] else 0

            cur.execute("SELECT midterm FROM marks WHERE student_id=? AND course_id=?", (student_id, course_id))
            mr = cur.fetchone(); mid = round(mr[0], 2) if mr else 0

            cur_tot = q_tot + a_tot + mid
            cur_pct = round((cur_tot/50)*100, 2)

            c1,c2,c3,c4 = st.columns(4)
            with c1: st.metric("Attendance",  f"{fmt(att_pct)}%", delta="Good" if att_pct>=75 else "Low")
            with c2: st.metric("Quizzes",     f"{fmt(q_tot)}/10",  f"{fmt(round(q_tot/10*100,2))}%")
            with c3: st.metric("Assignments", f"{fmt(a_tot)}/20",  f"{fmt(round(a_tot/20*100,2))}%")
            with c4: st.metric("Midterm",     f"{fmt(mid)}/20",    f"{fmt(round(mid/20*100,2))}%")

            st.markdown(f"**Current Performance: {fmt(cur_tot)}/50 ({fmt(cur_pct)}%)**")
            st.caption("Final exam (50 marks) pending — Ask AI Assistant for predictions")
            st.progress(cur_pct/100)

            st.bar_chart(
                pd.DataFrame({"Assessment":["Quizzes","Assignments","Midterm"],"Score":[q_tot,a_tot,mid],"Max":[10,20,20]}).set_index("Assessment")[["Score","Max"]],
                use_container_width=True
            )
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
            cur.execute("SELECT credit_hours FROM courses WHERE course_id=?", (course_id,))
            cr = cur.fetchone(); credit_hours = cr[0] if cr else 3

            st.markdown(f"""<div class="course-card">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <h4 style="margin:0;color:white;">📖 {course_name}</h4>
                <span style="background:rgba(255,255,255,.2);padding:4px 10px;border-radius:6px;font-size:.8rem;">{credit_hours} Credit Hours</span>
              </div></div>""", unsafe_allow_html=True)

            cur.execute("SELECT topic_number,topic_name FROM course_outlines WHERE course_id=? ORDER BY topic_number", (course_id,))
            topics = cur.fetchall()

            if topics:
                df = pd.DataFrame([{"Week/Topic #": f"Topic {n}", "Topic Name": nm} for n,nm in topics])
                st.markdown(f"**Total Topics: {len(topics)}**")
                st.dataframe(df, use_container_width=True, hide_index=True,
                    column_config={
                        "Week/Topic #": st.column_config.TextColumn("Week/Topic #", width="small"),
                        "Topic Name":   st.column_config.TextColumn("Topic Name",   width="large"),
                    })
                with st.expander("📑 View as List"):
                    for n,nm in topics:
                        st.markdown(f"**Topic {n}:** {nm}")
            else:
                st.info(f"No course outline available for {course_name}.")
            st.markdown("---")

# ==================================================
# PAGE: LECTURES
# ==================================================
elif page == "📚 Lectures":
    st.title("📚 Course Lectures")

    selected_course = st.selectbox(
        "📖 Select a course to view lectures",
        options=["-- Select a course --"] + course_names,
        key="lectures_course_selector"
    )

    if selected_course == "-- Select a course --":
        st.info("📚 Please select a course to display the respective lectures.")
    else:
        course_id = course_map[selected_course]
        cur.execute("SELECT credit_hours FROM courses WHERE course_id=?", (course_id,))
        cr = cur.fetchone(); credit_hours = cr[0] if cr else 3

        st.markdown(f"""<div class="course-card">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <h4 style="margin:0;color:white;">📖 {selected_course}</h4>
            <span style="background:rgba(255,255,255,.2);padding:4px 10px;border-radius:6px;font-size:.8rem;">{credit_hours} Credit Hours</span>
          </div></div>""", unsafe_allow_html=True)

        cur.execute("""SELECT lecture_id,lecture_number,lecture_title,file_name,file_data,file_type,file_size
            FROM lectures WHERE course_id=? ORDER BY lecture_number""", (course_id,))
        lectures = cur.fetchall()

        if lectures:
            st.markdown(f"""<h3>📑 Available Lectures <span class="lecture-count-badge">{len(lectures)} lectures</span></h3>""", unsafe_allow_html=True)
            for lid,lnum,ltitle,fname,fdata,ftype,fsize in lectures:
                size_str = (f"{fsize/1024:.1f} KB" if fsize and fsize<1024*1024 else f"{fsize/(1024*1024):.1f} MB") if fsize else "Unknown"
                ficon = {'PDF':'📕','PPTX':'📊','PPT':'📊'}.get(ftype,'📄')
                mime  = {'PDF':'application/pdf','PPTX':'application/vnd.openxmlformats-officedocument.presentationml.presentation','PPT':'application/vnd.ms-powerpoint'}.get(ftype,'application/octet-stream')
                c1,c2,c3 = st.columns([0.5,4,1])
                with c1: st.markdown(f"<div style='font-size:2rem;text-align:center;'>{ficon}</div>", unsafe_allow_html=True)
                with c2: st.markdown(f"<h4 style='margin:0 0 4px;color:#1e293b;'>Lecture {lnum}: {ltitle}</h4><p style='margin:0;color:#64748b;font-size:.85rem;'>{ftype} • {size_str} • {fname}</p>", unsafe_allow_html=True)
                with c3: st.download_button("⬇️ Download", data=fdata, file_name=fname, mime=mime, key=f"dl_{lid}", use_container_width=True)
                st.markdown("<hr style='margin:.4rem 0;border-color:#f1f5f9;'>", unsafe_allow_html=True)
        else:
            st.warning("📭 No lectures available for this course yet.")

# ==================================================
# PAGE: PERSONAL INFO
# ==================================================
elif page == "👤 Personal Info":
    st.title("👤 Student Profile")
    st.markdown("### Personal Information")

    c1,c2 = st.columns(2, gap="medium")
    with c1:
        st.markdown(f"""<div class="personal-info-card">
          <div style="margin-bottom:1rem;">
            <p style="margin:0;font-size:.85rem;color:#64748b;font-weight:600;">FULL NAME</p>
            <h3 style="margin:0;color:#1e293b;">{student_name}</h3>
          </div>
          <div>
            <p style="margin:0;font-size:.85rem;color:#64748b;font-weight:600;">REGISTRATION NUMBER</p>
            <h3 style="margin:0;color:#1e293b;">{registration_no}</h3>
          </div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="personal-info-card">
          <div style="margin-bottom:1rem;">
            <p style="margin:0;font-size:.85rem;color:#64748b;font-weight:600;">CURRENT SEMESTER</p>
            <h3 style="margin:0;color:#1e293b;">{semester}</h3>
          </div>
          <div>
            <p style="margin:0;font-size:.85rem;color:#64748b;font-weight:600;">STUDENT ID</p>
            <h3 style="margin:0;color:#1e293b;">{student_id}</h3>
          </div></div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📚 Course Enrollment")

    if course_names:
        ch_dict = {}
        for cn in course_names:
            cur.execute("SELECT credit_hours FROM courses WHERE course_name=?", (cn,))
            r = cur.fetchone(); ch_dict[cn] = r[0] if r else 3

        cols = st.columns(3, gap="medium")
        for idx, course in enumerate(course_names):
            with cols[idx % 3]:
                st.markdown(f"""<div class="course-enroll-card">
                  <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.7rem;">
                    <div style="background:linear-gradient(135deg,#C8860A,#E8A020);color:white;width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:bold;">{idx+1}</div>
                    <h4 style="margin:0;color:#1e293b;">Course {idx+1}</h4>
                  </div>
                  <p style="margin:0;font-size:1rem;font-weight:600;color:#334155;">{course}</p>
                  <p style="margin:.4rem 0 0;font-size:.85rem;color:#64748b;">⏱️ Credit Hours: {ch_dict[course]}</p>
                </div>""", unsafe_allow_html=True)

        st.info(f"📊 **Total Credit Hours this semester: {sum(ch_dict.values())}**")
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
            st.markdown(f"""<div class="course-card"><h4 style="margin:0;color:white;">📖 {course_name}</h4></div>""", unsafe_allow_html=True)

            cur.execute("SELECT quiz_name,marks_obtained,max_marks FROM quizzes WHERE student_id=? AND course_id=? ORDER BY quiz_name", (student_id, course_id))
            quizzes = cur.fetchall()

            if quizzes:
                rows=[]; tot=0
                for qn,mo,mm in quizzes:
                    rows.append({"Quiz":qn,"Marks Obtained":fmt(mo),"Max Marks":fmt(mm),"Percentage":fmt((mo/mm)*100)+"%"})
                    tot+=mo
                c1,c2=st.columns([2,1],gap="medium")
                with c1: st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
                with c2:
                    st.metric("Total Obtained",  f"{fmt(tot)}/10")
                    st.metric("Average per Quiz", fmt(tot/4) if quizzes else "0")
                    st.metric("Quiz Percentage",  fmt((tot/10)*100)+"%")
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
            st.markdown(f"""<div class="course-card"><h4 style="margin:0;color:white;">📖 {course_name}</h4></div>""", unsafe_allow_html=True)

            cur.execute("SELECT assignment_name,marks_obtained,max_marks FROM assignments WHERE student_id=? AND course_id=? ORDER BY assignment_name", (student_id, course_id))
            assignments = cur.fetchall()

            if assignments:
                rows=[]; tot=0
                for an,mo,mm in assignments:
                    rows.append({"Assignment":an,"Marks Obtained":fmt(mo),"Max Marks":fmt(mm),"Percentage":fmt((mo/mm)*100)+"%"})
                    tot+=mo
                c1,c2=st.columns([2,1],gap="medium")
                with c1: st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
                with c2:
                    st.metric("Total Obtained",         f"{fmt(tot)}/20")
                    st.metric("Average per Assignment", fmt(tot/4) if assignments else "0")
                    st.metric("Assignment Percentage",  fmt((tot/20)*100)+"%")
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
            st.markdown(f"""<div class="course-card"><h4 style="margin:0;color:white;">📖 {course_name}</h4></div>""", unsafe_allow_html=True)

            cur.execute("SELECT classes_attended,total_classes FROM attendance WHERE student_id=? AND course_id=?", (student_id, course_id))
            att = cur.fetchone()

            if att and att[1] > 0:
                pct = round((att[0]/att[1])*100,2)
                c1,c2,c3 = st.columns(3,gap="medium")
                with c1: st.metric("Classes Attended",      att[0])
                with c2: st.metric("Total Classes",         att[1])
                with c3: st.metric("Attendance Percentage", f"{fmt(pct)}%")
                st.progress(int(pct)/100)
                if pct < 75:
                    st.warning("⚠️ Your attendance is below the required 75%.")
                else:
                    st.success("✅ Your attendance meets the requirement.")
            elif att and att[1] == 0:
                st.info("No classes held yet for this course.")
            else:
                st.info("No attendance data available.")
            st.markdown("---")

# ==================================================
# PAGE: AI ASSISTANT
# ==================================================
elif page == "🤖 AI Assistant":
    st.title("🤖 EduGuide — Academic AI Assistant")
    st.caption("Your intelligent companion for academic queries, predictions, and study planning.")

    from backend.agentic_architecture.agent import (
        extract_pages_from_file, load_notes_file, clear_notes_store,
        notes_file_loaded, get_notes_summary,
    )

    with st.sidebar:
        st.markdown("---")
        st.markdown("### 📖 Upload Lecture Notes")
        st.caption("Upload any file and ask me to explain it.")

        uploaded_file = st.file_uploader(
            "PDF, PowerPoint, Word, or Image",
            type=["pdf","pptx","docx","png","jpg","jpeg","webp"],
            key="notes_uploader",
        )

        if uploaded_file is not None:
            if st.session_state.get("notes_filename") != uploaded_file.name:
                with st.spinner(f"Reading '{uploaded_file.name}'..."):
                    try:
                        import tempfile
                        suffix = os.path.splitext(uploaded_file.name)[1]
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                            tmp.write(uploaded_file.read()); tmp_path = tmp.name
                        pages = extract_pages_from_file(tmp_path)
                        os.unlink(tmp_path)
                        load_notes_file(pages, uploaded_file.name)
                        st.session_state.notes_filename = uploaded_file.name
                        st.success(f"✅ **{uploaded_file.name}** — {len(pages)} page(s) loaded.")
                    except Exception as e:
                        st.error(f"Could not read file: {e}")

        if notes_file_loaded():
            st.info(f"📄 **Loaded:** {get_notes_summary()}")
            if st.button("🗑️ Remove File", use_container_width=True):
                clear_notes_store(); st.session_state.notes_filename = ""; st.rerun()

    if "messages" not in st.session_state or not st.session_state.messages:
        welcome_msg = (
            f"👋 **Hello {student_name.split()[0]}!** I'm your Academic AI Companion.\n\n"
            "🔍 **Information Retrieval** — Query your LMS data instantly\n\n"
            "📈 **Grade Predictions** — Forecast your final exam performance\n\n"
            "📝 **Study Plans** — Personalized rescue and study strategies\n\n"
            "🎓 **GPA Calculator** — Predict your semester GPA\n\n"
            "📖 **Notes Assistant** — Upload any lecture file and ask me to explain it\n\n"
            "_💡 Tip: Upload a lecture file from the sidebar to get started._"
        )
        st.session_state.messages = [{"role": "assistant", "content": welcome_msg}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input(
        "Ask about your notes, grades, predictions..." if notes_file_loaded()
        else "Ask about your grades, predictions, study plans..."
    )

    if prompt:
        st.session_state.messages.append({"role":"user","content":prompt})
        with st.chat_message("user"): st.markdown(prompt)

        try:
            with st.spinner("🤔 Analyzing with AI Agents..."):
                triage_agent = build_agents(student_id, conn)
                result = asyncio.run(Runner.run(
                    starting_agent=triage_agent, input=prompt,
                    run_config=config, session=memory, max_turns=25
                ))
                bot_reply = result.final_output
        except ImportError as e:
            bot_reply = f"⚠️ **Agent System Error**\n\nError: `{str(e)}`"
        except Exception as e:
            import traceback; print(traceback.format_exc())
            bot_reply = f"⚠️ **Error:** `{str(e)}`\n\nPlease try rephrasing your question."

        st.session_state.messages.append({"role":"assistant","content":bot_reply})
        with st.chat_message("assistant"): st.markdown(bot_reply)

# --------------------------------------------------
# CLOSE DB
# --------------------------------------------------
conn.close()