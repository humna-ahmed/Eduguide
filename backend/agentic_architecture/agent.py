# agent.py
import os
import asyncio
import sqlite3
from typing import Dict, Any, Optional

from agents import (
    Agent,
    Runner,
    RunConfig,
    OpenAIChatCompletionsModel,
    SQLiteSession,
    function_tool
)
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
# =========================================================
# MODEL SETUP (OPENAI - CLEAN)
# =========================================================

from openai import AsyncOpenAI

# Use OpenAI directly (no base_url needed)
openai_client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY") 
)

# Choose a model (recommended: gpt-4o-mini for cost efficiency)
model = OpenAIChatCompletionsModel(
    model="gpt-4o-mini",
    openai_client=openai_client
)

config = RunConfig(model=model)

ft_model = OpenAIChatCompletionsModel(
    model="ft:gpt-4o-mini-2024-07-18:personal::DUsZGTcV",
    openai_client=openai_client
)

# =========================================================
# SESSION MEMORY
# =========================================================

memory = SQLiteSession(session_id="conversation_123")

# =========================================================
# ASYNC DB LOGIC (WRAPS SQLITE – SAFE)
# =========================================================

async def _get_course_data_async(
    course_name: str,
    student_id: int,
    db: sqlite3.Connection
) -> Dict[str, Any]:
    course_name = course_name.strip() 

    cursor = db.cursor()

    cursor.execute(
        "SELECT course_id FROM courses WHERE LOWER(course_name) = LOWER(?)",
        (course_name,)
    )
    course = cursor.fetchone()

    if not course:
        return {"error": f"Course '{course_name}' not found"}

    course_id = course[0]

    data = {
        "course_name": course_name,
        "quizzes": [],
        "assignments": [],
        "attendance": None,
        "midterm": None
    }

    # Quizzes
    cursor.execute("""
        SELECT quiz_name, marks_obtained, max_marks
        FROM quizzes
        WHERE student_id=? AND course_id=?
    """, (student_id, course_id))

    for name, obtained, maxm in cursor.fetchall():
        data["quizzes"].append({
            "name": name,
            "obtained": obtained,
            "max": maxm,
            "percentage": round((obtained / maxm) * 100, 2) if maxm else 0
        })

    # Assignments
    cursor.execute("""
        SELECT assignment_name, marks_obtained, max_marks
        FROM assignments
        WHERE student_id=? AND course_id=?
    """, (student_id, course_id))

    for name, obtained, maxm in cursor.fetchall():
        data["assignments"].append({
            "name": name,
            "obtained": obtained,
            "max": maxm,
            "percentage": round((obtained / maxm) * 100, 2) if maxm else 0
        })

    # Attendance
    cursor.execute("""
        SELECT classes_attended, total_classes
        FROM attendance
        WHERE student_id=? AND course_id=?
    """, (student_id, course_id))

    att = cursor.fetchone()
    if att:
        attended, total = att
        data["attendance"] = round((attended / total) * 100, 2) if total else 0

    # Midterm
    cursor.execute("""
        SELECT midterm FROM marks
        WHERE student_id=? AND course_id=?
    """, (student_id, course_id))

    mid = cursor.fetchone()
    if mid and mid[0] is not None:
        data["midterm"] = {
            "marks": mid[0],
            "percentage": round((mid[0] / 20) * 100, 2)
        }

    return data


async def _get_performance_data_async(
    course_name: str,
    student_id: int,
    db: sqlite3.Connection
) -> Dict[str, Any]:
    course_name = course_name.strip() 

    cursor = db.cursor()

    cursor.execute(
        "SELECT course_id FROM courses WHERE LOWER(course_name) = LOWER(?)",
        (course_name,)
    )
    course = cursor.fetchone()

    if not course:
        return {"error": "Course not found"}

    course_id = course[0]

    scores = []

    cursor.execute("""
        SELECT marks_obtained, max_marks
        FROM quizzes
        WHERE student_id=? AND course_id=?
    """, (student_id, course_id))

    for o, m in cursor.fetchall():
        if m:
            scores.append((o / m) * 100)

    avg = round(sum(scores) / len(scores), 2) if scores else 0

    return {
        "quiz_average": avg,
        "consistency": round(100 - (max(scores) - min(scores)), 2) if scores else 0
    }


async def _get_course_analysis_async(
    course_name: Optional[str],
    student_id: int,
    db: sqlite3.Connection
) -> Dict[str, Any]:
    course_name = course_name.strip() 

    cursor = db.cursor()

    if course_name:
        cursor.execute(
            "SELECT course_id FROM courses WHERE LOWER(course_name) = LOWER(?)",
            (course_name,)
        )
        course = cursor.fetchone()

        if not course:
            return {"error": "Course not found"}

        course_ids = [(course[0], course_name)]
    else:
        cursor.execute("SELECT course_id FROM courses WHERE LOWER(course_name) = LOWER(?)")
        course_ids = cursor.fetchall()

    analysis = []

    for cid, cname in course_ids:
        cursor.execute("""
            SELECT classes_attended, total_classes
            FROM attendance
            WHERE student_id=? AND course_id=?
        """, (student_id, cid))

        att = cursor.fetchone()
        pct = round((att[0] / att[1]) * 100, 2) if att and att[1] else 0

        analysis.append({
            "course": cname,
            "attendance": pct,
            "risk": "high" if pct < 75 else "low"
        })

    return {"analysis": analysis}


# =========================================================
# TOOL BUILDER (SYNC ONLY – SAFE)
# =========================================================

def build_tools(student_id: int, db: sqlite3.Connection):
    # Your existing tools should work with this db connection
    @function_tool
    async def get_course_data(course_name: str):
        return await _get_course_data_async(course_name, student_id, db)  # Uses passed db

    @function_tool
    async def get_performance_data(course_name: str):
        return await _get_performance_data_async(course_name, student_id, db)

    @function_tool
    async def get_course_analysis(course_name: Optional[str] = None):
        return await _get_course_analysis_async(course_name, student_id, db)
    
    @function_tool
    async def compute_final_result(
        quiz_total: float,
        assignment_total: float,
        midterm_marks: float,
        predicted_final_exam: float
    ):
        total = quiz_total + assignment_total + midterm_marks + predicted_final_exam
        percentage = total  # already out of 100
    
        if percentage >= 85:
            grade = "A"
        elif percentage >= 80:
            grade = "A-"
        elif percentage >= 75:
            grade = "B+"
        elif percentage >= 71:
            grade = "B"
        elif percentage >= 68:
            grade = "B-"
        elif percentage >= 64:
            grade = "C+"
        elif percentage >= 60:
            grade = "C"
        elif percentage >= 57:
            grade = "C-"
        elif percentage >= 53:
            grade = "D+"
        elif percentage >= 50:
            grade = "D"
        else:
            grade = "F"
    
        return {
            "total_marks": round(total, 2),
            "percentage": round(percentage, 2),
            "grade": grade
        }

    return [get_course_data, get_performance_data, get_course_analysis, compute_final_result]


# =========================================================
# AGENT SETUP
# =========================================================

def build_agents(student_id: int, db):

    tools = build_tools(student_id, db)
    
    lms_agent = Agent(
        name="LMS Data Agent",
        model=model,
        instructions="""
    You are the **LMS Data Retrieval Agent** — a specialist in fetching and explaining academic records.
    
    🎯 **YOUR CORE PURPOSE:**
    You help students understand their current academic standing by retrieving precise data from the LMS database. You NEVER predict, plan, or give study advice. Your job is strictly data retrieval and presentation.
    
    STRICT RULES:

1. NEVER assume a course name.
2. If the user does not mention a course explicitly, ASK:
   "Which course would you like information about?"
3. Only retrieve data for the exact course mentioned.
4. If the course does not exist in the database, say:
   "The course '<course_name>' was not found."

YOU MUST NOT default to Calculus or any course.
    
    📋 **WHAT YOU CAN DO:**
    - Fetch quiz marks for specific quizzes or all quizzes in a course
    - Fetch assignment scores for specific assignments or all assignments
    - Show attendance percentages and records
    - Display midterm exam marks
    - Calculate current totals and percentages
    - Compare performance across different assessments
    
    📊 **DATA STRUCTURE YOU MUST UNDERSTAND:**
    - Quizzes: 4 quizzes per course, each worth 2.5 marks → Total 10 marks
    - Assignments: 4 assignments per course, each worth 5 marks → Total 20 marks
    - Midterm: Worth 20 marks
    - Current Total: Quizzes (10) + Assignments (20) + Midterm (20) = 50/100 marks
    - Final Exam: Worth 50 marks (NOT in your scope)
    
    🔍 **QUERY HANDLING RULES:**
    
    1. FOR SPECIFIC ASSESSMENTS:
       - When asked about "quiz 1", show ONLY quiz 1
       - When asked about "assignment 3", show ONLY assignment 3
       - When asked about "midterm", show ONLY midterm marks
       - Do NOT add extra assessments the user didn't ask for
    
    2. FOR COMPLETE OVERVIEWS:
       - When asked "all quizzes" or "show my quizzes", show ALL 4 quizzes
       - When asked "all assignments", show ALL 4 assignments
       - When asked for "full course data", show everything
    
    3. FOR ATTENDANCE:
       - Always show both percentage and the raw numbers (X/Y classes)
       - If attendance < 75%, add a clear ⚠️ WARNING
    
    ✅ **RESPONSE FORMAT REQUIREMENTS:**
    
    Use clear markdown with emojis:
    
    ```
    📊 **Course: [Course Name]**
    
    **Quizzes** (Total: X/10)
    • Quiz 1: X/2.5 (X%)
    • Quiz 2: X/2.5 (X%)
    • Quiz 3: X/2.5 (X%)
    • Quiz 4: X/2.5 (X%)
    
    **Assignments** (Total: X/20)
    • Assignment 1: X/5 (X%)
    • Assignment 2: X/5 (X%)
    • Assignment 3: X/5 (X%)
    • Assignment 4: X/5 (X%)
    
    **Midterm**: X/20 (X%)
    
    **Attendance**: X% (X/X classes) ⚠️
    **Current Total**: X/50 (X%)
    ```
    
    🚫 **WHAT YOU NEVER DO:**
    - Never predict final exam scores
    - Never create study plans
    - Never suggest improvement strategies
    - Never hand off to other agents
    - Never answer non-LMS questions
    
    If asked about predictions or study plans, respond: "I'm the Data Retrieval Agent specialized in showing your current marks. For predictions or study plans, please ask a general question and our main assistant will route you to the right specialist."
    """,
        handoff_description="Specialist agent for academic data retrieval (quizzes, assignments, attendance)",
        tools=tools
    )
    
    predictive_agent = Agent(
        name="Prediction Agent",
        model=ft_model,
        instructions="""
        You are the Academic Prediction Agent.

        Your job is to:
        1. Predict the student's final exam score (out of 50)
        2. Then compute final total marks and grade USING A TOOL

        WORKFLOW (STRICT):

        1. ALWAYS call get_course_data first
        2. From the result, calculate:
           - total quiz marks (out of 10)
           - total assignment marks (out of 20)
           - midterm marks (out of 20)

        3. Predict final exam marks (out of 50) using:
           - performance trends
           - consistency
           - attendance
        
        4. AFTER prediction → CALL compute_final_result tool
        
        5. NEVER manually calculate final grade yourself
        
        OUTPUT FORMAT:
        
        📊 Current Performance Summary  
        🔮 Predicted Final Exam Score (range)  
        🏁 Final Result (from tool):
        - Total Marks: X/100  
        - Percentage: X%  
        - Grade: X  
        
        IMPORTANT RULES:
        
        - ALWAYS use tools for calculations
        - NEVER guess totals manually
        - NEVER skip tool usage
        """,
        handoff_description="Specialist agent for academic predictions and final exam forecasting",
        tools=tools
    )

    planner_agent = Agent(
        name="Planner Agent",
        model=model,
        instructions="""
        You are the Academic Planning Agent.
    
        RESPONSIBILITIES:
        1. Create personalized study plans based on academic performance
        2. Generate rescue plans for struggling students
        3. Allocate study hours based on course difficulty and performance
        4. Suggest specific focus areas and study techniques
        5. Provide weekly study schedules and revision strategies
    
        PLAN TYPES:
        1. RESCUE PLAN: For high-risk courses (attendance < 75% or performance < 60%)
        2. IMPROVEMENT PLAN: For medium-risk courses (performance 60-75%)
        3. MAINTENANCE PLAN: For low-risk courses (performance > 75%)
        4. COMPREHENSIVE PLAN: For all courses combined
    
        CONSIDERATIONS:
        - Time until finals (assume 4-6 weeks)
        - Current performance levels
        - Learning patterns and consistency
        - Course priorities and risk levels
        - Student's available time (assume 3-4 hours daily)
    
        RESPONSE FORMAT:
        1. Course-wise prioritization with risk levels
        2. Recommended weekly study hours per course
        3. Specific focus areas for improvement
        4. Weekly study schedule template
        5. Study strategies and techniques
        6. Progress tracking suggestions
    
        STUDY STRATEGIES TO RECOMMEND:
        - Active recall and spaced repetition
        - Pomodoro technique (25/5 intervals)
        - Interleaving different subjects
        - Practice testing with past papers
        - Teaching concepts to peers
    
        IMPORTANT:
        - Be realistic about time commitments
        - Include breaks and self-care
        - Emphasize consistency over cramming
        - Provide actionable steps
        """,
        handoff_description="Specialist agent for study planning, scheduling, and rescue plans",
        tools=[tools[0], tools[2]]
    )

    triage_agent = Agent(
        name="Academic AI Companion",
        model=model,
        instructions="""
    You are the **Primary Academic AI Companion** — the student's main assistant and gateway to all academic help.
    
    🎓 **YOUR IDENTITY:**
    You are NOT a data retrieval specialist, NOT a prediction expert, and NOT a study planner. You are the **CONDUCTOR** of an orchestra of specialists. Your job is to understand what the student needs and route them to the perfect specialist.

VERY IMPORTANT RULES:

1. DO NOT assume any course.
2. If course is missing in the query → ASK for clarification.
3. Route queries properly:
   - Quiz / assignment / attendance → LMS Agent
   - Prediction / expected grade → Prediction Agent
   - Study plan / rescue plan → Planner Agent
4. Never answer academic data questions yourself.
5. Never default to Calculus.

If query is incomplete:
Example:
User: "Show my quiz marks"
You respond:
"Sure! Which course would you like to see quiz marks for?"
    
    🤝 **THE SPECIALISTS YOU CAN ACCESS:**
    
    1. **LMS DATA AGENT** (Handoff via `handoff to LMS Data Agent`)
       - CAPABILITIES: Shows quiz marks, assignment scores, attendance, midterm marks
       - USE WHEN: Student asks about grades, marks, scores, percentages, "how did I do in...", "show my..."
    
    2. **PREDICTION AGENT** (Handoff via `handoff to Prediction Agent`)
       - CAPABILITIES: Predicts final exam scores, analyzes performance patterns
       - USE WHEN: Student asks about future performance, "what if", predictions, forecasts
    
    3. **PLANNER AGENT** (Handoff via `handoff to Planner Agent`)
       - CAPABILITIES: Creates study plans, rescue plans, schedules, strategies
       - USE WHEN: Student asks for help studying, planning, schedules, "how to improve"
       
    ⚡ **DECISION TREE - READ CAREFULLY:**
    
    ```
    Is the query about GRADES/MARKS/SCORES? 
    → YES → HANDOFF TO LMS DATA AGENT
    → NO → ↓
    
    Is the query about FUTURE/PREDICTIONS/FORECAST?
    → YES → HANDOFF TO PREDICTION AGENT
    → NO → ↓
    
    Is the query about STUDYING/PLANNING/SCHEDULING?
    → YES → HANDOFF TO PLANNER AGENT
    → NO → ↓
    
    → CLARIFY: "I can help you with checking your grades, predicting final scores, or creating study plans. Which one would you like help with?"
    ```
    
    🗣️ **GREETING PROTOCOL (First interaction only):**
    
    ```
    🎓 Hello! I'm your Academic AI Companion.
    
    I can help you with three things:
    
    📊 **Check Your Grades** - Quiz marks, assignment scores, attendance
    🔮 **Predict Final Scores** - Forecast your exam performance  
    📚 **Create Study Plans** - Personalized schedules and strategies
    
    What would you like help with today?
    ```
    
    🚫 **CRITICAL RULES - NEVER VIOLATE:**
    1. NEVER answer academic queries yourself. ALWAYS hand off to the appropriate specialist.
    2. NEVER display data, make predictions, or give study advice. You are a router, not a specialist.
    3. NEVER reveal that you're handing off. Don't say "I'm transferring you" or "Let me get the specialist".
    4. NEVER apologize for limitations. Just clarify what you CAN do and ask which they want.
    5. NEVER assume what the student wants. If unclear, present the three options clearly.
    
    ✅ **CORRECT HANDOFF EXAMPLES:**
    
    User: "What's my quiz marks?"
    You: [Immediate handoff to LMS Agent] - NO verbal acknowledgment
    
    User: "Will I pass calculus?"
    You: [Immediate handoff to Prediction Agent] - NO verbal acknowledgment
    
    User: "Help me study"
    You: [Immediate handoff to Planner Agent] - NO verbal acknowledgment
    
    ❌ **INCORRECT RESPONSES:**
    
    "Let me check your quiz marks..." → WRONG (you're not the LMS Agent)
    "I predict you'll get..." → WRONG (you're not the Prediction Agent)
    "You should study..." → WRONG (you're not the Planner Agent)
    "I'll transfer you to..." → WRONG (don't mention handoffs)
    
    🎯 **YOUR ONLY JOB:**
    Identify the query type → Handoff to correct specialist → Stay silent otherwise.
    """,
        handoffs=[lms_agent, predictive_agent, planner_agent]
    )

    return triage_agent


# =========================================================
# MAIN
# =========================================================

# In agent.py, modify the main() function:

async def main():
    import os
    import sys
    
    # Get the correct path to the database
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up one level from agentic_architecture to backend, then to database folder
    backend_dir = os.path.dirname(current_dir)
    db_path = os.path.join(backend_dir, "database", "lms.db")
    
    print(f"Looking for database at: {db_path}")
    print(f"Database exists: {os.path.exists(db_path)}")
    
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"❌ ERROR: Database not found at {db_path}")
        print("Please ensure you have run init_db.py in the database folder")
        print("Run: cd backend/database && python init_db.py")
        return
    
    print("✅ Database found!")
    
    try:
        # Connect to the correct database
        db = sqlite3.connect(db_path)
        print("✅ Database connected successfully!")
        
        # Verify data exists
        cursor = db.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM courses")
        course_count = cursor.fetchone()[0]
        print(f"📚 Found {course_count} courses in database")
        
        if course_count == 0:
            print("⚠️  WARNING: No courses found!")
            print("Please add courses to the database")
        
        cursor.execute("SELECT course_name FROM courses")
        courses = cursor.fetchall()
        print(f"📋 Course list: {[c[0] for c in courses]}")
        
        cursor.execute("SELECT student_id, name, registration_no FROM students")
        students = cursor.fetchall()
        print(f"👨‍🎓 Found {len(students)} students: {students}")
        
        if not students:
            print("❌ ERROR: No students found in database!")
            print("Please add students to the database")
            db.close()
            return
        
        # Use the first student or a specific one
        student_id = students[1][0]  # First student in the list
        student_name = students[1][1]
        student_reg = students[1][2]
        print(f"👤 Using student_id: {student_id} - Name: {student_name} - Reg: {student_reg}")
        
        # Check if this student has data for Calculus
        cursor.execute("""
            SELECT course_id FROM courses WHERE course_name = 'Calculus'
        """)
        calc_course = cursor.fetchone()
        
        if calc_course:
            course_id = calc_course[0]
            cursor.execute("""
                SELECT COUNT(*) FROM quizzes 
                WHERE student_id = ? AND course_id = ?
            """, (student_id, course_id))
            quiz_count = cursor.fetchone()[0]
            print(f"📊 Student has {quiz_count} quiz records for Calculus")
        
        print("\n" + "="*50)
        print("🤖 INITIALIZING AGENT...")
        print("="*50 + "\n")
        
        # Build and run the agent
        triage_agent = build_agents(student_id, db)
        
        result = await Runner.run(
            starting_agent=triage_agent,
            input="Show quiz 1 marks in Calculus",
            run_config=config,
            session = memory
        )
        
        print("\n" + "="*50)
        print("🤖 AGENT RESPONSE:")
        print("="*50)
        print(result.final_output)
        
        db.close()
        print("\n✅ Script completed successfully!")
        
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        

       
if __name__ == "__main__":
    asyncio.run(main())