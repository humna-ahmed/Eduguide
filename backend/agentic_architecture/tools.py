# backend/agents/tools.py

from agents import function_tool
from typing import Dict, Any, Optional
import asyncio

# ============================================
# GLOBAL CONTEXT (for tools to access student_id and db_connection)
# ============================================

_current_student_id = None
_current_db_connection = None

def set_tool_context(student_id: int, db_connection):
    """Set global context before running agents"""
    global _current_student_id, _current_db_connection
    _current_student_id = student_id
    _current_db_connection = db_connection

def get_tool_context():
    """Get current context for tools"""
    return _current_student_id, _current_db_connection

# ============================================
# TOOLS WITH SIMPLE SIGNATURES (as OpenAI Agent SDK expects)
# ============================================

@function_tool
def get_course_data(course_name: str) -> Dict[str, Any]:
    """Get course data from database"""
    student_id, db_connection = get_tool_context()
    
    if not student_id or not db_connection:
        return {"error": "Context not set. Please ask your question again."}
    
    # Run async function synchronously (tools must be synchronous)
    return asyncio.run(_get_course_data_async(course_name, student_id, db_connection))

@function_tool
def get_performance_data(course_name: str) -> Dict[str, Any]:
    """Get performance data for predictions"""
    student_id, db_connection = get_tool_context()
    
    if not student_id or not db_connection:
        return {"error": "Context not set"}
    
    return asyncio.run(_get_performance_data_async(course_name, student_id, db_connection))

@function_tool
def get_course_analysis(course_name: Optional[str] = None) -> Dict[str, Any]:
    """Get course analysis for planning"""
    student_id, db_connection = get_tool_context()
    
    if not student_id or not db_connection:
        return {"error": "Context not set"}
    
    return asyncio.run(_get_course_analysis_async(course_name, student_id, db_connection))

# ============================================
# ASYNC IMPLEMENTATIONS (keep your existing code here)
# ============================================

async def _get_course_data_async(course_name: str, student_id: int, db_connection) -> Dict[str, Any]:
    """Get course data from database (Tool for LMS Agent)"""
    cursor = db_connection.cursor()
    
    # Get course_id
    cursor.execute("SELECT course_id FROM courses WHERE course_name = ?", (course_name,))
    course_result = cursor.fetchone()
    
    if not course_result:
        return {"error": f"Course '{course_name}' not found"}
    
    course_id = course_result[0]
    
    # Get all data
    data = {
        "course_name": course_name,
        "course_id": course_id,
        "quizzes": [],
        "assignments": [],
        "attendance": None,
        "midterm": None,
        "totals": {}
    }
    
    # Get quizzes
    cursor.execute("""
        SELECT quiz_name, marks_obtained, max_marks
        FROM quizzes
        WHERE student_id = ? AND course_id = ?
        ORDER BY quiz_name
    """, (student_id, course_id))
    
    quizzes = []
    quiz_total = 0
    for quiz_name, marks_obtained, max_marks in cursor.fetchall():
        quiz_data = {
            "name": quiz_name,
            "marks_obtained": float(marks_obtained),
            "max_marks": float(max_marks),
            "percentage": round((marks_obtained / max_marks) * 100, 2) if max_marks > 0 else 0
        }
        quizzes.append(quiz_data)
        quiz_total += float(marks_obtained)
    
    data["quizzes"] = quizzes
    data["totals"]["quiz_total"] = round(quiz_total, 2)
    data["totals"]["quiz_max"] = 10.0
    data["totals"]["quiz_percentage"] = round((quiz_total / 10) * 100, 2) if 10 > 0 else 0
    
    # Get assignments
    cursor.execute("""
        SELECT assignment_name, marks_obtained, max_marks
        FROM assignments
        WHERE student_id = ? AND course_id = ?
        ORDER BY assignment_name
    """, (student_id, course_id))
    
    assignments = []
    assign_total = 0
    for assign_name, marks_obtained, max_marks in cursor.fetchall():
        assign_data = {
            "name": assign_name,
            "marks_obtained": float(marks_obtained),
            "max_marks": float(max_marks),
            "percentage": round((marks_obtained / max_marks) * 100, 2) if max_marks > 0 else 0
        }
        assignments.append(assign_data)
        assign_total += float(marks_obtained)
    
    data["assignments"] = assignments
    data["totals"]["assignment_total"] = round(assign_total, 2)
    data["totals"]["assignment_max"] = 20.0
    data["totals"]["assignment_percentage"] = round((assign_total / 20) * 100, 2) if 20 > 0 else 0
    
    # Get attendance
    cursor.execute("""
        SELECT classes_attended, total_classes
        FROM attendance
        WHERE student_id = ? AND course_id = ?
    """, (student_id, course_id))
    
    attendance = cursor.fetchone()
    if attendance:
        attended, total = attendance
        data["attendance"] = {
            "classes_attended": attended,
            "total_classes": total,
            "percentage": round((attended / total) * 100, 2) if total > 0 else 0
        }
    
    # Get midterm
    cursor.execute("""
        SELECT midterm FROM marks
        WHERE student_id = ? AND course_id = ?
    """, (student_id, course_id))
    
    midterm_result = cursor.fetchone()
    if midterm_result and midterm_result[0]:
        midterm = float(midterm_result[0])
        data["midterm"] = {
            "marks_obtained": midterm,
            "max_marks": 20.0,
            "percentage": round((midterm / 20) * 100, 2)
        }
        data["totals"]["midterm_total"] = round(midterm, 2)
        data["totals"]["midterm_max"] = 20.0
        data["totals"]["midterm_percentage"] = round((midterm / 20) * 100, 2)
    
    # Calculate current total
    current_total = quiz_total + assign_total + (midterm if midterm_result and midterm_result[0] else 0)
    data["totals"]["current_total"] = round(current_total, 2)
    data["totals"]["current_max"] = 50.0
    data["totals"]["current_percentage"] = round((current_total / 50) * 100, 2) if 50 > 0 else 0
    
    return data

async def _get_performance_data_async(course_name: str, student_id: int, db_connection) -> Dict[str, Any]:
    """Get performance data for predictions (Tool for Prediction Agent)"""
    cursor = db_connection.cursor()
    
    # Get course_id
    cursor.execute("SELECT course_id FROM courses WHERE course_name = ?", (course_name,))
    course_result = cursor.fetchone()
    
    if not course_result:
        return {"error": f"Course '{course_name}' not found"}
    
    course_id = course_result[0]
    
    data = {}
    
    # Get quizzes
    cursor.execute("""
        SELECT marks_obtained, max_marks
        FROM quizzes
        WHERE student_id = ? AND course_id = ?
    """, (student_id, course_id))
    
    quiz_scores = []
    for obtained, max_marks in cursor.fetchall():
        if max_marks > 0:
            quiz_scores.append((obtained / max_marks) * 100)
    
    if quiz_scores:
        data["quiz_average"] = round(sum(quiz_scores) / len(quiz_scores), 2)
        # Calculate consistency (higher = more consistent)
        variance = sum((score - data["quiz_average"]) ** 2 for score in quiz_scores) / len(quiz_scores)
        data["quiz_consistency"] = round(max(0, 100 - (variance / 10)), 2)
        data["quiz_count"] = len(quiz_scores)
    
    # Get assignments
    cursor.execute("""
        SELECT marks_obtained, max_marks
        FROM assignments
        WHERE student_id = ? AND course_id = ?
    """, (student_id, course_id))
    
    assign_scores = []
    for obtained, max_marks in cursor.fetchall():
        if max_marks > 0:
            assign_scores.append((obtained / max_marks) * 100)
    
    if assign_scores:
        data["assignment_average"] = round(sum(assign_scores) / len(assign_scores), 2)
        variance = sum((score - data["assignment_average"]) ** 2 for score in assign_scores) / len(assign_scores)
        data["assignment_consistency"] = round(max(0, 100 - (variance / 10)), 2)
        data["assignment_count"] = len(assign_scores)
    
    # Get midterm
    cursor.execute("""
        SELECT midterm FROM marks
        WHERE student_id = ? AND course_id = ?
    """, (student_id, course_id))
    
    midterm_result = cursor.fetchone()
    if midterm_result and midterm_result[0]:
        data["midterm_score"] = round((midterm_result[0] / 20) * 100, 2)
        data["midterm_marks"] = round(float(midterm_result[0]), 2)
    
    # Get attendance
    cursor.execute("""
        SELECT classes_attended, total_classes
        FROM attendance
        WHERE student_id = ? AND course_id = ?
    """, (student_id, course_id))
    
    attendance = cursor.fetchone()
    if attendance:
        attended, total = attendance
        data["attendance_percentage"] = round((attended / total) * 100, 2) if total > 0 else 0
        data["attendance_attended"] = attended
        data["attendance_total"] = total
    
    # Calculate overall average
    components = []
    weights = []
    
    if "quiz_average" in data:
        components.append(data["quiz_average"])
        weights.append(0.2)  # 20% weight
    
    if "assignment_average" in data:
        components.append(data["assignment_average"])
        weights.append(0.3)  # 30% weight
    
    if "midterm_score" in data:
        components.append(data["midterm_score"])
        weights.append(0.5)  # 50% weight
    
    if components:
        weighted_sum = sum(comp * weight for comp, weight in zip(components, weights))
        total_weight = sum(weights)
        data["weighted_average"] = round(weighted_sum / total_weight, 2)
    
    return data

async def _get_course_analysis_async(course_name: Optional[str] = None, student_id: int = None, db_connection = None) -> Dict[str, Any]:
    """Get course analysis for planning (Tool for Planner Agent)"""
    cursor = db_connection.cursor()
    
    if course_name:
        # Single course analysis
        cursor.execute("SELECT course_id FROM courses WHERE course_name = ?", (course_name,))
        course_result = cursor.fetchone()
        
        if not course_result:
            return {"error": f"Course '{course_name}' not found"}
        
        course_id = course_result[0]
        return await _analyze_single_course(student_id, course_id, course_name, cursor)
    else:
        # All courses analysis
        cursor.execute("SELECT course_id, course_name FROM courses")
        courses = cursor.fetchall()
        
        analysis = []
        for course_id, cname in courses:
            course_analysis = await _analyze_single_course(student_id, course_id, cname, cursor)
            if course_analysis:
                analysis.append(course_analysis)
        
        return {"courses": analysis}

async def _analyze_single_course(student_id: int, course_id: int, course_name: str, cursor) -> Dict[str, Any]:
    """Analyze a single course"""
    analysis = {
        "course_name": course_name,
        "risk_level": "low",
        "priority": "low",
        "recommended_hours": 5,
        "issues": [],
        "strengths": []
    }
    
    # Check attendance
    cursor.execute("""
        SELECT classes_attended, total_classes
        FROM attendance
        WHERE student_id = ? AND course_id = ?
    """, (student_id, course_id))
    
    attendance = cursor.fetchone()
    if attendance:
        attended, total = attendance
        attendance_pct = round((attended / total) * 100, 2) if total > 0 else 0
        analysis["attendance_percentage"] = attendance_pct
        
        if attendance_pct < 75:
            analysis["risk_level"] = "high"
            analysis["recommended_hours"] += 3
            analysis["issues"].append(f"Low attendance ({attendance_pct}% < 75%)")
        else:
            analysis["strengths"].append(f"Good attendance ({attendance_pct}%)")
    
    # Check quizzes
    cursor.execute("""
        SELECT SUM(marks_obtained), SUM(max_marks)
        FROM quizzes
        WHERE student_id = ? AND course_id = ?
    """, (student_id, course_id))
    
    quiz_result = cursor.fetchone()
    if quiz_result and quiz_result[0] is not None and quiz_result[1]:
        quiz_total, quiz_max = quiz_result
        quiz_pct = round((quiz_total / quiz_max) * 100, 2) if quiz_max > 0 else 0
        analysis["quiz_percentage"] = quiz_pct
        
        if quiz_pct < 60:
            analysis["risk_level"] = "high" if analysis["risk_level"] != "high" else "high"
            analysis["recommended_hours"] += 2
            analysis["issues"].append(f"Poor quiz performance ({quiz_pct}%)")
        elif quiz_pct >= 80:
            analysis["strengths"].append(f"Strong quiz performance ({quiz_pct}%)")
    
    # Check assignments
    cursor.execute("""
        SELECT SUM(marks_obtained), SUM(max_marks)
        FROM assignments
        WHERE student_id = ? AND course_id = ?
    """, (student_id, course_id))
    
    assign_result = cursor.fetchone()
    if assign_result and assign_result[0] is not None and assign_result[1]:
        assign_total, assign_max = assign_result
        assign_pct = round((assign_total / assign_max) * 100, 2) if assign_max > 0 else 0
        analysis["assignment_percentage"] = assign_pct
        
        if assign_pct < 60:
            analysis["risk_level"] = "medium" if analysis["risk_level"] == "low" else analysis["risk_level"]
            analysis["recommended_hours"] += 2
            analysis["issues"].append(f"Poor assignment performance ({assign_pct}%)")
        elif assign_pct >= 80:
            analysis["strengths"].append(f"Strong assignment performance ({assign_pct}%)")
    
    # Check midterm
    cursor.execute("""
        SELECT midterm FROM marks
        WHERE student_id = ? AND course_id = ?
    """, (student_id, course_id))
    
    midterm_result = cursor.fetchone()
    if midterm_result and midterm_result[0]:
        midterm_pct = round((midterm_result[0] / 20) * 100, 2)
        analysis["midterm_percentage"] = midterm_pct
        
        if midterm_pct < 50:
            analysis["risk_level"] = "high"
            analysis["recommended_hours"] += 5
            analysis["issues"].append(f"Failed midterm ({midterm_pct}%)")
        elif midterm_pct < 60:
            analysis["risk_level"] = "medium" if analysis["risk_level"] == "low" else analysis["risk_level"]
            analysis["recommended_hours"] += 3
            analysis["issues"].append(f"Below average midterm ({midterm_pct}%)")
        elif midterm_pct >= 80:
            analysis["strengths"].append(f"Excellent midterm ({midterm_pct}%)")
    
    # Set priority based on risk
    if analysis["risk_level"] == "high":
        analysis["priority"] = "high"
        analysis["recommended_hours"] = max(analysis["recommended_hours"], 10)
    elif analysis["risk_level"] == "medium":
        analysis["priority"] = "medium"
        analysis["recommended_hours"] = max(analysis["recommended_hours"], 7)
    
    return analysis