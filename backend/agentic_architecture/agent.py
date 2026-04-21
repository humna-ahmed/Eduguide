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
# GPA CALCULATION LOGIC
# =========================================================

# Bahria University Karachi grading scale
GRADE_POINTS = {
    "A":  4.00,
    "A-": 3.67,
    "B+": 3.33,
    "B":  3.00,
    "B-": 2.67,
    "C+": 2.33,
    "C":  2.00,
    "C-": 1.67,
    "D+": 1.33,
    "D":  1.00,
    "F":  0.00,
}

def calculate_gpa_from_courses(courses: list) -> Dict[str, Any]:
    """
    Given a list of dicts with 'name', 'credit_hours', 'predicted_grade',
    compute weighted GPA using Bahria University Karachi grading scale.

    GPA = sum(grade_points * credit_hours) / sum(credit_hours)
    """
    total_quality_points = 0.0
    total_credit_hours   = 0
    breakdown            = []

    for course in courses:
        grade        = course.get("predicted_grade", "F")
        credit_hours = int(course.get("credit_hours", 0))
        grade_point  = GRADE_POINTS.get(grade, 0.00)
        quality_pts  = grade_point * credit_hours

        total_quality_points += quality_pts
        total_credit_hours   += credit_hours

        breakdown.append({
            "course":        course.get("name", "Unknown"),
            "credit_hours":  credit_hours,
            "predicted_grade": grade,
            "grade_points":  grade_point,
            "quality_points": round(quality_pts, 2),
        })

    gpa = round(total_quality_points / total_credit_hours, 2) if total_credit_hours else 0.0

    # Determine GPA standing label
    if gpa >= 3.67:
        standing = "Dean's List 🏆"
    elif gpa >= 3.00:
        standing = "Good Standing ✅"
    elif gpa >= 2.00:
        standing = "Satisfactory ⚠️"
    elif gpa >= 1.00:
        standing = "Academic Warning 🔴"
    else:
        standing = "Academic Probation ❌"

    return {
        "gpa":                 gpa,
        "standing":            standing,
        "total_credit_hours":  total_credit_hours,
        "total_quality_points": round(total_quality_points, 2),
        "breakdown":           breakdown,
    }


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
        """
        Fetches all courses, calls the Prediction Agent for each,
        and returns a list of courses with predicted grades and credit hours.
        This is shared by both the Planner Agent AND the GPA Agent.
        """
        cursor = db.cursor()

        cursor.execute("""
            SELECT c.course_name, c.credit_hours
            FROM courses c
        """)
    
        courses = cursor.fetchall()
    
        result = []
    
        import json
    
        for cname, ch in courses:
            # Call prediction agent per course
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

    # ── NEW TOOL: GPA Calculator ──────────────────────────────────────────────
    @function_tool
    async def compute_gpa(courses: list):
        """
        Calculates the student's predicted semester GPA using Bahria University
        Karachi grading scheme.

        Expects a list of dicts, each with:
          - name           (str)  course name
          - credit_hours   (int)  weightage: 1 CH = weight 1, 3 CH = weight 3
          - predicted_grade (str) e.g. "A", "B+", "C-"

        Returns:
          - gpa                  weighted GPA (0.00 – 4.00)
          - standing             label (Dean's List, Good Standing, etc.)
          - total_credit_hours
          - total_quality_points
          - breakdown            per-course detail
        """
        return calculate_gpa_from_courses(courses)
    # ─────────────────────────────────────────────────────────────────────────

    return [
        get_course_data,
        get_performance_data,
        get_course_analysis,
        compute_final_result,
        get_full_student_profile,
        compute_course_priority,
        compute_gpa,            # ← new tool available to ALL agents
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

    # ── NEW: GPA Agent ────────────────────────────────────────────────────────
    gpa_agent = Agent(
        name="GPA Agent",
        model=model,
        instructions="""
        You are the **GPA Calculator Agent** for Bahria University Karachi Campus.

        YOUR SOLE PURPOSE:
        Calculate the student's predicted semester GPA based on their predicted
        grades across all enrolled courses, weighted by credit hours.

        ─────────────────────────────────────────────
        WORKFLOW (STRICT — NEVER SKIP STEPS):
        ─────────────────────────────────────────────

        STEP 1 → Call get_full_student_profile
                 This returns all courses with their credit_hours and predicted_grade.
                 DO NOT ask the user for grades. The tool handles everything.

        STEP 2 → Pass the courses list directly to compute_gpa
                 DO NOT modify, filter, or manually calculate anything.
                 The tool does the weighted GPA calculation for you.

        STEP 3 → Present the result in the format below.

        ─────────────────────────────────────────────
        BAHRIA UNIVERSITY KARACHI — GRADING SCALE:
        ─────────────────────────────────────────────
        A   → 4.00   |   A-  → 3.67
        B+  → 3.33   |   B   → 3.00   |   B-  → 2.67
        C+  → 2.33   |   C   → 2.00   |   C-  → 1.67
        D+  → 1.33   |   D   → 1.00   |   F   → 0.00

        Credit hour weightage: 1 CH = weight 1, 2 CH = weight 2, 3 CH = weight 3

        GPA Formula:
        GPA = Σ(Grade Points × Credit Hours) / Σ(Credit Hours)

        ─────────────────────────────────────────────
        OUTPUT FORMAT (use exactly this structure):
        ─────────────────────────────────────────────

        🎓 **Predicted Semester GPA — Bahria University Karachi**

        | Course | Credit Hours | Predicted Grade | Grade Points | Quality Points |
        |--------|-------------|-----------------|--------------|----------------|
        | [name] | [CH]        | [grade]         | [pts]        | [CH × pts]     |
        ...

        📊 **GPA Summary**
        • Total Credit Hours : X
        • Total Quality Points: X
        • **Predicted GPA    : X.XX / 4.00**
        • Standing           : [Dean's List 🏆 / Good Standing ✅ / Satisfactory ⚠️ / Academic Warning 🔴 / Academic Probation ❌]

        ─────────────────────────────────────────────
        AFTER THE TABLE — add a short personal note:
        ─────────────────────────────────────────────
        - If GPA ≥ 3.67 → Congratulate, encourage maintaining it
        - If GPA 3.00–3.66 → Positive but push for Dean's List
        - If GPA 2.00–2.99 → Motivate, mention 1–2 key courses dragging it down
        - If GPA < 2.00 → Serious tone, urge consulting advisor + rescue plan

        ─────────────────────────────────────────────
        STRICT RULES:
        ─────────────────────────────────────────────
        - NEVER manually calculate GPA — always use compute_gpa tool
        - NEVER ask the user for their grades
        - NEVER skip get_full_student_profile
        - NEVER predict individual course grades yourself
        - NEVER answer non-GPA questions; redirect to triage agent
        """,
        handoff_description="Specialist agent for semester GPA calculation based on predicted grades and credit hours (Bahria University Karachi grading scheme)",
        tools=tools,
    )
    # ─────────────────────────────────────────────────────────────────────────

    triage_agent = Agent(
        name="Academic AI Companion",
        model=model,
        instructions="""
        You are the **Primary Academic AI Companion** — the student's main assistant and gateway to all academic help.
    
        🎓 **YOUR IDENTITY:**
        You are NOT a data retrieval specialist, NOT a prediction expert, NOT a study planner, and NOT a GPA calculator.
        You are the **CONDUCTOR** of an orchestra of specialists. Your job is to understand what the student needs
        and route them to the perfect specialist.

        VERY IMPORTANT RULES:
    
        1. DO NOT assume any course.
        2. If course is missing in the query → ASK for clarification.
        3. Route queries properly:
           - Quiz / assignment / attendance → LMS Agent
           - Prediction / expected grade → Prediction Agent
           - Study plan / rescue plan → Planner Agent
           - GPA / semester GPA / overall GPA → GPA Agent
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

        4. **GPA AGENT** (Handoff via `handoff to GPA Agent`)
           - CAPABILITIES: Calculates predicted semester GPA using Bahria University Karachi grading
             scheme, weighted by credit hours
           - USE WHEN: Student asks "what's my GPA?", "calculate my GPA", "what GPA will I get?",
             "my semester GPA", or any mention of GPA / grade points / CGPA estimate
           
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

        Is the query about GPA / GRADE POINTS / SEMESTER STANDING?
        → YES → HANDOFF TO GPA AGENT
        → NO → ↓
        
        → CLARIFY: "I can help you with checking your grades, predicting final scores,
          creating study plans, or calculating your predicted GPA. Which one would you like help with?"
        ```
    
        🗣️ **GREETING PROTOCOL (First interaction only):**
    
        ```
        🎓 Hello! I'm your Academic AI Companion.
    
        I can help you with four things:
    
        📊 **Check Your Grades** - Quiz marks, assignment scores, attendance
        🔮 **Predict Final Scores** - Forecast your exam performance  
        📚 **Create Study Plans** - Personalized schedules and strategies
        🎓 **Calculate Your GPA** - Predicted semester GPA (Bahria University Karachi)
    
        What would you like help with today?
        ```
    
        🚫 **CRITICAL RULES - NEVER VIOLATE:**
        1. NEVER answer academic queries yourself. ALWAYS hand off to the appropriate specialist.
        2. NEVER display data, make predictions, give study advice, or compute GPA. You are a router.
        3. NEVER reveal that you're handing off.
        4. NEVER apologize for limitations.
        5. NEVER assume what the student wants. If unclear, present the four options clearly.
        
        ✅ **CORRECT HANDOFF EXAMPLES:**
        
        User: "What's my quiz marks?"        → [Immediate handoff to LMS Agent]
        User: "Will I pass calculus?"         → [Immediate handoff to Prediction Agent]
        User: "Help me study"                 → [Immediate handoff to Planner Agent]
        User: "What's my GPA?"               → [Immediate handoff to GPA Agent]
        User: "Calculate my semester GPA"    → [Immediate handoff to GPA Agent]
        
        ❌ **INCORRECT RESPONSES:**
        
        "Let me check your quiz marks..." → WRONG (you're not the LMS Agent)
        "I predict you'll get..."         → WRONG (you're not the Prediction Agent)
        "You should study..."             → WRONG (you're not the Planner Agent)
        "Your GPA is..."                  → WRONG (you're not the GPA Agent)
        "I'll transfer you to..."         → WRONG (don't mention handoffs)
        
        🎯 **YOUR ONLY JOB:**
        Identify the query type → Handoff to correct specialist → Stay silent otherwise.
        """,
        handoffs=[lms_agent, predictive_agent, planner_agent, gpa_agent]   # ← gpa_agent added
    )

    return triage_agent