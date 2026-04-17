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

predictive_ft_model = OpenAIChatCompletionsModel(
    model="ft:gpt-4o-mini-2024-07-18:personal::DUsZGTcV",
    openai_client=openai_client
)


planner_ft_model = OpenAIChatCompletionsModel(
    model="ft:gpt-4o-mini-2024-07-18:personal::DVVFYRLI",
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

async def run_prediction_agent(course_name: str, student_id: int, db):
    # Rebuild tools for prediction agent
    tools = build_tools(student_id, db)

    predictive_agent = Agent(
        name="Prediction Agent",
        model=predictive_ft_model,
        instructions="""
        You are the Academic Prediction Agent.

        Your job is to:
        1. Predict the student's final exam score (out of 50)
        2. Then compute final total marks and grade USING A TOOL

        WORKFLOW (STRICT):
        1. ALWAYS call get_course_data first
        2. Calculate totals
        3. Predict final exam marks
        4. CALL compute_final_result tool
        5. RETURN OUTPUT IN JSON FORMAT:

        {
          "course": "...",
          "predicted_final_exam": number,
          "total_marks": number,
          "percentage": number,
          "grade": "A/B/C"
        }
        """,
        tools=tools
    )

    result = await Runner.run(
        predictive_agent,
        input=f"Predict my final result for {course_name}"
    )

    return result.final_output

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
        
        
    @function_tool
    async def get_full_student_profile():
        cursor = db.cursor()

        cursor.execute("""
            SELECT c.course_name, c.credit_hours
            FROM courses c
        """)
    
        courses = cursor.fetchall()
    
        result = []
    
        import json
    
        for cname, ch in courses:
            # 🔥 CALL prediction agent
            prediction_output = await run_prediction_agent(cname, student_id, db)
    
            # Default fallback
            predicted_grade = "C"
    
            try:
                data = json.loads(prediction_output)
                predicted_grade = data.get("grade", "C")
            except:
                pass  # keep fallback if parsing fails
    
            result.append({
                "name": cname,
                "credit_hours": ch,
                "predicted_grade": predicted_grade
            })

        return {"courses": result}

    @function_tool
    async def compute_course_priority(courses: list):
        grade_map = {
            "A": 10, "A-": 9, "B+": 8, "B": 7,
            "B-": 6, "C+": 5, "C": 4,
            "C-": 3, "D+": 2, "D": 1, "F": 0
        }

        result = []

        for course in courses:
            grade_score = grade_map.get(course["predicted_grade"], 0)
            priority_score = course["credit_hours"] * (10 - grade_score)
    
            result.append({
                "course": course["name"],
                "priority_score": priority_score
            })

        return sorted(result, key=lambda x: x["priority_score"], reverse=True)    

    return [
        get_course_data,
        get_performance_data,
        get_course_analysis,
        compute_final_result,
        get_full_student_profile,
        compute_course_priority
    ]


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
        model=predictive_ft_model,
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
        model=planner_ft_model,
        instructions="""
        You are the Academic Planning Agent.

        CRITICAL BEHAVIOR:

        1. ALWAYS call get_full_student_profile first
        2. This tool already includes predicted grades (DO NOT ask user)
        3. Then call compute_course_priority
        4. Then generate a personalized plan
        
        ---

        TYPES OF REQUESTS:

        1. If user mentions a course:
           → Generate plan ONLY for that course
        
        2. If user asks general plan:
           → Generate plan for ALL courses
        
        ---
        
        PLANNING LOGIC:
        
        - Higher credit hours = higher importance
        - Lower predicted grade = higher urgency
        - Combine BOTH to decide time allocation
        
        Example:
        - Programming (3 CH, B) → HIGH priority
        - Calculus (1 CH, C+) → LOWER priority than programming
        
        ---
        
        OUTPUT MUST INCLUDE:
        
        1. 🎯 Goal (Reach A grade)
        2. ⚠️ Current Situation (based on predicted grade)
        3. 📊 Priority Level
        4. 📅 Weekly Study Hours Allocation
        5. 🧠 Strategy (specific to course)
        6. 📆 Weekly Timetable
        
        ---
        
        TONE:
        
        - Highly personalized
        - Direct ("You need to focus...")
        - No generic advice
        - Clear, actionable steps
        
        ---
        
        DO NOT:
        
        - Ask user for grades
        - Assume performance
        - Skip tool usage
        """,
        handoff_description="Specialist agent for study planning, scheduling, and rescue plans",
        tools=tools
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