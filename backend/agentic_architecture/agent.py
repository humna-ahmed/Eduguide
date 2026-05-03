# agent.py
import os
import io
import re
import base64
import asyncio
import sqlite3
import json
import sys
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import concurrent.futures
from agents import Agent, Runner, RunConfig, OpenAIChatCompletionsModel, SQLiteSession, function_tool
from openai import AsyncOpenAI
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ml_predictor import predict_final_exam_ml
load_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))      # backend/agentic_architecture
backend_dir = os.path.dirname(current_dir)                   # backend/
DB_PATH = os.path.join(backend_dir, "database", "lms.db")    # backend/database/lms.db

# =========================================================
# CLIENT & MODEL SETUP
# =========================================================

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

model = OpenAIChatCompletionsModel(
    model="gpt-4o-mini",
    openai_client=openai_client,
)

notes_model = OpenAIChatCompletionsModel(
    model="gpt-4o",
    openai_client=openai_client,
)

config = RunConfig(model=model)

# =========================================================
# SESSION MEMORY
# =========================================================

memory = SQLiteSession(session_id="conversation_123")

# =========================================================
# PREDICTION CACHE
# Keyed by (student_id, course_name_lowercase).
# Guarantees every agent sees identical predicted grades.
# Call clear_prediction_cache() at the start of a new session.
# =========================================================

_prediction_cache: Dict[tuple, Dict[str, Any]] = {}

def clear_prediction_cache() -> None:
    _prediction_cache.clear()

# =========================================================
# PURE MATH HELPERS  (no DB, no LLM)
# =========================================================


def get_grade_from_total(total: float) -> str:
    """Maps total percentage (0-100) to Bahria University Karachi letter grade."""
    if   total >= 85: return "A"
    elif total >= 80: return "A-"
    elif total >= 75: return "B+"
    elif total >= 71: return "B"
    elif total >= 68: return "B-"
    elif total >= 64: return "C+"
    elif total >= 60: return "C"
    elif total >= 57: return "C-"
    elif total >= 53: return "D+"
    elif total >= 50: return "D"
    else:             return "F"


GRADE_POINTS = {
    "A": 4.00, "A-": 3.67, "B+": 3.33, "B": 3.00, "B-": 2.67,
    "C+": 2.33, "C": 2.00, "C-": 1.67, "D+": 1.33, "D": 1.00, "F": 0.00,
}

def calculate_gpa_from_courses(courses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes weighted GPA from a list of courses.
    Each course dict needs: name, credit_hours, predicted_grade.
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
            "course":          course.get("name", "Unknown"),
            "credit_hours":    credit_hours,
            "predicted_grade": grade,
            "grade_points":    grade_point,
            "quality_points":  round(quality_pts, 2),
        })

    gpa = round(total_quality_points / total_credit_hours, 2) if total_credit_hours else 0.0

    if   gpa >= 3.67: standing = "Dean's List 🏆"
    elif gpa >= 3.00: standing = "Good Standing ✅"
    elif gpa >= 2.00: standing = "Satisfactory ⚠️"
    elif gpa >= 1.00: standing = "Academic Warning 🔴"
    else:             standing = "Academic Probation ❌"

    return {
        "gpa":                  gpa,
        "standing":             standing,
        "total_credit_hours":   total_credit_hours,
        "total_quality_points": round(total_quality_points, 2),
        "breakdown":            breakdown,
    }

# =========================================================
# DB HELPERS  (async, take db + student_id)
# =========================================================

def get_course_topics_from_db(course_name: str):
    """Get topics from database - synchronous version"""
    import sqlite3
    
    try:
        # Get correct database path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.dirname(current_dir)
        db_path = os.path.join(backend_dir, "database", "lms.db")
        
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Try exact match
        cur.execute("SELECT course_id, course_name FROM courses WHERE LOWER(course_name) = LOWER(?)", (course_name.strip(),))
        row = cur.fetchone()
        
        # Try partial match if exact fails
        if not row:
            cur.execute("SELECT course_id, course_name FROM courses WHERE LOWER(course_name) LIKE LOWER(?)", (f"%{course_name.strip()}%",))
            row = cur.fetchone()
        
        if not row:
            conn.close()
            courses = ["Operating Systems", "Database Management Systems", "Software Design and Architecture", "Design and Analysis of Algorithms", "Engineering Management"]
            return f"❌ Course '{course_name}' not found.\n\nAvailable courses:\n- " + "\n- ".join(courses)
        
        course_id, matched_name = row
        
        # Get topics
        cur.execute("""
            SELECT topic_name FROM course_outlines
            WHERE course_id = ?
            ORDER BY topic_number
        """, (course_id,))
        
        topics = [r[0] for r in cur.fetchall()]
        conn.close()
        
        if not topics:
            # Provide default topics if database doesn't have them
            return f"📚 **Topics for {matched_name}:**\n\n1. Course Introduction\n2. Core Concepts\n3. Advanced Topics\n4. Review\n\n💡 Note: Please run 'python complete_migration.py' to load full topics."
        
        formatted = "\n".join([f"{i+1}. {t}" for i, t in enumerate(topics)])
        return f"📚 **Topics for {matched_name}:**\n\n{formatted}"
        
    except Exception as e:
        return f"❌ Error fetching topics: {str(e)}"
    
async def _fetch_course_data(course_name: str, student_id: int, db: sqlite3.Connection) -> Dict[str, Any]:
    """Returns quizzes, assignments, attendance, and midterm for one course."""
    cursor = db.cursor()

    cursor.execute("SELECT course_id FROM courses WHERE LOWER(course_name) = LOWER(?)", (course_name.strip(),))
    row = cursor.fetchone()
    if not row:
        return {"error": f"Course '{course_name}' not found."}
    course_id = row[0]

    data = {"course_name": course_name, "quizzes": [], "assignments": [], "attendance": None, "midterm": None}

    cursor.execute(
        "SELECT quiz_name, marks_obtained, max_marks FROM quizzes WHERE student_id=? AND course_id=?",
        (student_id, course_id),
    )
    for name, obtained, maxm in cursor.fetchall():
        data["quizzes"].append({"name": name, "obtained": obtained, "max": maxm,
                                "percentage": round((obtained / maxm) * 100, 2) if maxm else 0})

    cursor.execute(
        "SELECT assignment_name, marks_obtained, max_marks FROM assignments WHERE student_id=? AND course_id=?",
        (student_id, course_id),
    )
    for name, obtained, maxm in cursor.fetchall():
        data["assignments"].append({"name": name, "obtained": obtained, "max": maxm,
                                    "percentage": round((obtained / maxm) * 100, 2) if maxm else 0})

    cursor.execute(
        "SELECT classes_attended, total_classes FROM attendance WHERE student_id=? AND course_id=?",
        (student_id, course_id),
    )
    att = cursor.fetchone()
    if att:
        data["attendance"] = round((att[0] / att[1]) * 100, 2) if att[1] else 0

    cursor.execute("SELECT midterm FROM marks WHERE student_id=? AND course_id=?", (student_id, course_id))
    mid = cursor.fetchone()
    if mid and mid[0] is not None:
        data["midterm"] = {"marks": mid[0], "percentage": round((mid[0] / 20) * 100, 2)}

    return data

async def _fetch_full_student_profile(
    student_id: int, db: sqlite3.Connection
) -> Dict[str, Any]:
    cursor = db.cursor()
    cursor.execute("SELECT course_id, course_name, credit_hours FROM courses")
    courses = cursor.fetchall()

    result = []

    for course_id, cname, ch in courses:

        cursor.execute("""
            SELECT COALESCE(SUM(marks_obtained),0), COALESCE(SUM(max_marks),0)
            FROM quizzes WHERE student_id=? AND course_id=?
        """, (student_id, course_id))
        q_obt, q_max = cursor.fetchone()
        quiz_total = round((q_obt / q_max) * 10, 2) if q_max > 0 else 0.0

        cursor.execute("""
            SELECT COALESCE(SUM(marks_obtained),0), COALESCE(SUM(max_marks),0)
            FROM assignments WHERE student_id=? AND course_id=?
        """, (student_id, course_id))
        a_obt, a_max = cursor.fetchone()
        assignment_total = round((a_obt / a_max) * 20, 2) if a_max > 0 else 0.0

        cursor.execute(
            "SELECT midterm FROM marks WHERE student_id=? AND course_id=?",
            (student_id, course_id)
        )
        mid_row = cursor.fetchone()
        midterm = float(mid_row[0]) if mid_row and mid_row[0] is not None else 0.0

        cursor.execute("""
            SELECT classes_attended, total_classes FROM attendance
            WHERE student_id=? AND course_id=?
        """, (student_id, course_id))
        att_row = cursor.fetchone()
        attendance_pct = round((att_row[0] / att_row[1]) * 100, 1) \
                         if att_row and att_row[1] else 0.0

        cache_key = (student_id, cname.strip().lower())
        if cache_key in _prediction_cache:
            cached          = _prediction_cache[cache_key]
            predicted_final = cached["predicted_final_exam"]
            predicted_grade = cached["grade"]
            total_marks     = cached["total_marks"]
        else:
            predicted_final = predict_final_exam_ml(
                quiz_total, assignment_total, midterm
            )
            total_marks     = round(
                quiz_total + assignment_total + midterm + predicted_final, 2
            )
            predicted_grade = get_grade_from_total(total_marks)
            _prediction_cache[cache_key] = {
                "predicted_final_exam": predicted_final,
                "grade":                predicted_grade,
                "total_marks":          total_marks,
                "percentage":           total_marks,
                "course":               cname,
            }

        result.append({
            "name":             cname,
            "credit_hours":     ch,
            "quiz_total":       quiz_total,
            "assignment_total": assignment_total,
            "midterm":          midterm,
            "attendance_pct":   attendance_pct,
            "predicted_final":  predicted_final,
            "predicted_grade":  predicted_grade,
            "total_marks":      total_marks,
            "percentage":       total_marks,
        })

    return {"courses": result}

async def _fetch_single_course_prediction(
    course_name: str, student_id: int, db: sqlite3.Connection
) -> Dict[str, Any]:
    cache_key = (student_id, course_name.strip().lower())
    if cache_key in _prediction_cache:
        return _prediction_cache[cache_key]

    cursor = db.cursor()
    cursor.execute(
        "SELECT course_id FROM courses WHERE LOWER(course_name) = LOWER(?)",
        (course_name.strip(),)
    )
    row = cursor.fetchone()
    if not row:
        return {"error": f"Course '{course_name}' not found in database."}
    course_id = row[0]

    cursor.execute("""
        SELECT COALESCE(SUM(marks_obtained),0), COALESCE(SUM(max_marks),0)
        FROM quizzes WHERE student_id=? AND course_id=?
    """, (student_id, course_id))
    q_obt, q_max = cursor.fetchone()
    quiz_total = round((q_obt / q_max) * 10, 2) if q_max > 0 else 0.0

    cursor.execute("""
        SELECT COALESCE(SUM(marks_obtained),0), COALESCE(SUM(max_marks),0)
        FROM assignments WHERE student_id=? AND course_id=?
    """, (student_id, course_id))
    a_obt, a_max = cursor.fetchone()
    assignment_total = round((a_obt / a_max) * 20, 2) if a_max > 0 else 0.0

    cursor.execute(
        "SELECT midterm FROM marks WHERE student_id=? AND course_id=?",
        (student_id, course_id)
    )
    mid_row  = cursor.fetchone()
    midterm  = float(mid_row[0]) if mid_row and mid_row[0] is not None else 0.0

    predicted_final = predict_final_exam_ml(quiz_total, assignment_total, midterm)
    total_marks     = round(quiz_total + assignment_total + midterm + predicted_final, 2)
    grade           = get_grade_from_total(total_marks)

    result = {
        "course":               course_name,
        "quiz_total":           quiz_total,
        "assignment_total":     assignment_total,
        "midterm":              midterm,
        "predicted_final_exam": predicted_final,
        "total_marks":          total_marks,
        "percentage":           total_marks,
        "grade":                grade,
    }
    _prediction_cache[cache_key] = result
    return result

# =========================================================
# NOTES AGENT — PAGE DATACLASS & FILE EXTRACTION
# =========================================================

@dataclass
class Page:
    page_number: int
    label:       str
    text:        str
    image_b64:   str = ""


def _pil_to_b64(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _extract_pdf(path: str) -> List[Page]:
    import fitz
    from PIL import Image as PILImage
    pages, doc = [], fitz.open(path)
    for i, pdf_page in enumerate(doc, start=1):
        text = pdf_page.get_text("text").strip()
        pix  = pdf_page.get_pixmap(dpi=150)
        img  = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
        pages.append(Page(i, f"Page {i}", text, _pil_to_b64(img)))
    doc.close()
    return pages


def _extract_pptx(path: str) -> List[Page]:
    from pptx import Presentation
    prs, pages = Presentation(path), []
    for i, slide in enumerate(prs.slides, start=1):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    line = " ".join(r.text for r in para.runs).strip()
                    if line:
                        texts.append(line)
            if shape.shape_type == 19:
                for row in shape.table.rows:
                    rt = " | ".join(c.text.strip() for c in row.cells)
                    if rt.strip():
                        texts.append(rt)
        pages.append(Page(i, f"Slide {i}", "\n".join(texts), ""))
    return pages


def _extract_docx(path: str) -> List[Page]:
    from docx import Document
    doc   = Document(path)
    paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            rt = " | ".join(c.text.strip() for c in row.cells)
            if rt.strip():
                paras.append(rt)
    WORDS_PER_PAGE = 500
    chunks, cur, cnt, num = [], [], 0, 1
    for para in paras:
        cur.append(para)
        cnt += len(para.split())
        if cnt >= WORDS_PER_PAGE:
            chunks.append((num, "\n".join(cur)))
            num += 1; cur = []; cnt = 0
    if cur:
        chunks.append((num, "\n".join(cur)))
    return [Page(n, f"Page {n}", t, "") for n, t in chunks] or [Page(1, "Page 1", "No text found.", "")]


def _extract_image(path: str) -> List[Page]:
    from PIL import Image as PILImage
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    text = ""
    try:
        import pytesseract
        text = pytesseract.image_to_string(PILImage.open(path)).strip()
    except Exception:
        pass
    return [Page(1, "Image", text, b64)]


def extract_pages_from_file(path: str) -> List[Page]:
    ext = os.path.splitext(path)[1].lower()
    if   ext == ".pdf":                              return _extract_pdf(path)
    elif ext == ".pptx":                             return _extract_pptx(path)
    elif ext == ".docx":                             return _extract_docx(path)
    elif ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp"): return _extract_image(path)
    else: raise ValueError(f"Unsupported file type: {ext}")

# =========================================================
# NOTES AGENT — IN-MEMORY STORE
# =========================================================

_notes_pages:    List[Page] = []
_notes_filename: str        = ""
_chroma_collection          = None


def load_notes_file(pages: List[Page], filename: str) -> None:
    global _notes_pages, _notes_filename
    _notes_pages    = pages
    _notes_filename = filename
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _index_pages_into_chromadb(pages, filename))
                future.result()
        else:
            loop.run_until_complete(_index_pages_into_chromadb(pages, filename))
    except RuntimeError:
        asyncio.run(_index_pages_into_chromadb(pages, filename))


def clear_notes_store() -> None:
    global _notes_pages, _notes_filename, _chroma_collection
    _notes_pages = []; _notes_filename = ""; _chroma_collection = None


def notes_file_loaded() -> bool:
    return len(_notes_pages) > 0


def get_notes_summary() -> str:
    if not _notes_pages:
        return "No file loaded."
    label = _notes_pages[0].label.split()[0]
    return f"'{_notes_filename}' — {len(_notes_pages)} {label}(s) loaded."

# =========================================================
# NOTES AGENT — CHROMADB + EMBEDDINGS
# =========================================================

import chromadb
from chromadb.config import Settings as ChromaSettings

_chroma_client = chromadb.PersistentClient(
    path="./chroma_store",
    settings=ChromaSettings(anonymized_telemetry=False),
)


def _sanitize_collection_name(filename: str) -> str:
    name = os.path.splitext(filename)[0]
    name = re.sub(r'[^a-zA-Z0-9]+', '-', name).strip('-').lower()[:60]
    return name if len(name) >= 3 else name + '-doc'


async def _embed_texts(texts: List[str]) -> List[List[float]]:
    embeddings = []
    for i in range(0, len(texts), 100):
        batch    = [t if t.strip() else 'empty page' for t in texts[i:i+100]]
        response = await openai_client.embeddings.create(model='text-embedding-3-small', input=batch)
        embeddings.extend([item.embedding for item in response.data])
    return embeddings


async def _index_pages_into_chromadb(pages: List[Page], filename: str) -> None:
    global _chroma_collection
    collection_name = _sanitize_collection_name(filename)
    try:
        _chroma_client.delete_collection(collection_name)
    except Exception:
        pass
    _chroma_collection = _chroma_client.create_collection(name=collection_name, metadata={'hnsw:space': 'cosine'})
    ids        = [str(p.page_number) for p in pages]
    texts      = [p.text if p.text.strip() else 'empty page' for p in pages]
    metadatas  = [{'label': p.label, 'page_number': p.page_number, 'has_image': bool(p.image_b64)} for p in pages]
    embeddings = await _embed_texts(texts)
    _chroma_collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)


async def _retrieve_pages_semantic(query: str, max_pages: int = 4) -> List[Page]:
    """Retrieves most relevant pages using ChromaDB semantic search with keyword overrides."""
    q = query.lower()

    # Rule 1: explicit page/slide number
    m = re.search(r'(slide|page|pg\.?)\s*(\d+)', q)
    if m:
        target  = int(m.group(2))
        matched = [p for p in _notes_pages if p.page_number == target]
        return matched if matched else [min(_notes_pages, key=lambda p: abs(p.page_number - target))]

    # Rule 2a: page-by-page → all pages
    if any(kw in q for kw in ['page by page','slide by slide','explain each','go through each','one by one','explain the whole','explain all','walk me through']):
        return _notes_pages

    # Rule 2b: full summary → all pages
    if any(kw in q for kw in ['summarize','summary','summarise','everything','whole','entire','all slides','all pages','overview','what is this about']):
        return _notes_pages

    # Rule 3: semantic search
    if _chroma_collection is None or not _notes_pages:
        return [_notes_pages[0]] if _notes_pages else []

    query_embedding = await _embed_texts([query])
    results         = _chroma_collection.query(query_embeddings=query_embedding, n_results=min(max_pages, len(_notes_pages)), include=['metadatas'])
    page_map        = {p.page_number: p for p in _notes_pages}
    retrieved       = [page_map[int(m['page_number'])] for m in results['metadatas'][0] if int(m['page_number']) in page_map]
    return retrieved if retrieved else [_notes_pages[0]]


async def _answer_notes_question(query: str) -> str:
    """Full RAG pipeline: retrieve relevant pages → build prompt → generate answer with GPT-4o."""
    if not _notes_pages:
        return "No file is uploaded yet. Please upload a PDF, PowerPoint, Word document, or image first."

    pages      = await _retrieve_pages_semantic(query)
    total_pages = len(pages)
    context     = "\n\n".join(f"--- {p.label} ---\n{p.text}" for p in pages if p.text)

    if total_pages > 4:
        instruction = (
            f"The student wants a full explanation of all {total_pages} pages/slides. "
            f"Go through EVERY page in order. For each page: use the page/slide number as a heading, "
            f"explain the content in simple words, and give an example if relevant. Do not skip any page."
        )
    else:
        instruction = "Answer the student's question using the content below."

    user_parts = [{"type": "text", "text": f"{instruction}\n\nContent:\n\n{context}\n\n---\nStudent question: {query}"}]
    for p in pages[:10]:
        if p.image_b64:
            user_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{p.image_b64}", "detail": "high"}})

    messages = [
        {"role": "system", "content": (
            f"You are a friendly academic tutor helping a student understand '{_notes_filename}'.\n"
            "Rules:\n"
            "- Explain clearly in simple words (tutor style, not textbook)\n"
            "- Use bullet points and real-world examples\n"
            "- Always reference the specific page or slide number\n"
            "- ONLY answer from the provided content — not from outside knowledge"
        )},
        {"role": "user", "content": user_parts},
    ]

    max_tok = min(1500 + (total_pages - 1) * 500, 8000)
    resp    = await openai_client.chat.completions.create(model="gpt-4o", messages=messages, max_tokens=max_tok, temperature=0.3)
    answer  = resp.choices[0].message.content
    page_refs = f"all {total_pages} pages" if total_pages > 4 else ", ".join(p.label for p in pages)
    return f"{answer}\n\n*📄 Retrieved via semantic search: {page_refs}*"

# =========================================================
# BUILD TOOLS
# All function tools live here. Each tool calls the
# appropriate helper above — no logic inside the tool itself.
# =========================================================

def build_tools(student_id: int, db: sqlite3.Connection):

    # ── LMS / Data tools ──────────────────────────────────────────────────────

    @function_tool
    async def get_course_data(course_name: str) -> Dict[str, Any]:
        """Fetches quizzes, assignments, attendance, and midterm for a specific course."""
        return await _fetch_course_data(course_name, student_id, db)

    # ── Prediction tools ──────────────────────────────────────────────────────

    @function_tool
    async def predict_single_course(course_name: str) -> str:
        """
        Predicts the final exam score and grade for ONE course.
        Uses Linear Regression ML model trained on 1000 student records.
        Results are cached for session consistency.
        """
        result = await _fetch_single_course_prediction(course_name, student_id, db)
        if "error" in result:
            return result["error"]

        quiz       = result["quiz_total"]
        assgn      = result["assignment_total"]
        mid        = result["midterm"]
        pred_final = result["predicted_final_exam"]
        total      = result["total_marks"]
        grade      = result["grade"]
        sessional  = round(quiz + assgn + mid, 2)
    
        return (
            f"📊 **{course_name}**\n"
            f"• Quiz Total       : {quiz}/10\n"
            f"• Assignment Total : {assgn}/20\n"
            f"• Midterm          : {mid}/20\n"
            f"• Sessional Total  : {sessional}/50\n\n"
            f"🔮 **Predicted Final Exam: {pred_final}/50**\n\n"
            f"performance (quizzes, assignments, midterm).\n\n"
            f"🏁 **Final Result:**\n"
            f"• Total Marks : {total}/100\n"
            f"• Percentage  : {total}%\n"
            f"• Grade       : {grade}"
        )
    
    @function_tool
    async def predict_all_courses() -> str:
        """
        Predicts final exam scores and grades for ALL enrolled courses.
        Uses Linear Regression ML model trained on 1000 student records.
        Results are cached for session consistency.
        """
        profile = await _fetch_full_student_profile(student_id, db)
    
        if "error" in profile:
            return profile["error"]
        
        blocks = []

        for c in profile["courses"]:
            quiz       = c["quiz_total"]
            assgn      = c["assignment_total"]
            mid        = c["midterm"]
            pred_final = c["predicted_final"]
            total      = c["total_marks"]
            grade      = c["predicted_grade"]
            sessional  = round(quiz + assgn + mid, 2)
    
            blocks.append(
                f"📊 **{c['name']}**\n"
                f"• Quiz Total       : {quiz}/10\n"
                f"• Assignment Total : {assgn}/20\n"
                f"• Midterm          : {mid}/20\n"
                f"• Sessional Total  : {sessional}/50\n\n"
                f"🔮 **Predicted Final Exam: {pred_final}/50**\n\n"
                f"performance (quizzes, assignments, midterm).\n\n"
                f"🏁 **Final Result:**\n"
                f"• Total Marks : {total}/100\n"
                f"• Percentage  : {total}%\n"
                f"• Grade       : {grade}"
            )
    
        return "\n\n---\n\n".join(blocks)

    # ── Planning & GPA tools ──────────────────────────────────────────────────

    # Global storage for planner data — defined at build_tools scope
    # so all tools share the same dict across the conversation
    planner_data = {
        "hours_per_day": None,
        "days":          None,
        "study_style":   None,
        "weak_topics":   [],
        "target_course": None,
    }
   
    _cached_profile = {"data": None}

    @function_tool
    async def get_course_prediction(course_name: str) -> str:
        """Get predicted grade for a specific course."""
        result = await _fetch_single_course_prediction(course_name, student_id, db)
        if "error" in result:
            return result["error"]
        return (
            f"📊 Predicted Result for {course_name}:\n"
            f"• Grade      : {result['grade']}\n"
            f"• Percentage : {result['percentage']}%"
        )

    @function_tool
    async def fetch_course_topics(course_name: str) -> str:
        """Get all topics for a specific course from course_outlines table."""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.dirname(current_dir)
            db_path     = os.path.join(backend_dir, "database", "lms.db")
    
            conn = sqlite3.connect(db_path)
            cur  = conn.cursor()

            # Exact match first
            cur.execute(
                "SELECT course_id, course_name FROM courses "
                "WHERE LOWER(course_name) = LOWER(?)",
                (course_name.strip(),)
            )
            row = cur.fetchone()
    
            # Fuzzy fallback
            if not row:
                cur.execute(
                    "SELECT course_id, course_name FROM courses "
                    "WHERE LOWER(course_name) LIKE LOWER(?)",
                    (f"%{course_name.strip()}%",)
                )
                row = cur.fetchone()

            if not row:
                conn.close()
                return (
                    f"❌ Course '{course_name}' not found.\n"
                    f"Available: Operating Systems, Database Management Systems, "
                    f"Software Design and Architecture, "
                    f"Design and Analysis of Algorithms, Engineering Management"
                )

            course_id, matched_name = row

            cur.execute(
                "SELECT topic_name FROM course_outlines "
                "WHERE course_id = ? ORDER BY topic_number",
                (course_id,)
            )
            topics = [r[0] for r in cur.fetchall()]
            conn.close()
    
            if not topics:
                return f"⚠️ No topics found for {matched_name}."
    
            formatted = "\n".join([f"{i+1}. {t}" for i, t in enumerate(topics)])
            return f"📚 Topics for {matched_name}:\n\n{formatted}"
    
        except Exception as e:
            return f"❌ Error fetching topics: {str(e)}"

    @function_tool
    def save_weak_topics(input_text: str, course_name: str = "") -> str:
        """
        Save weak topics. Resolves topic numbers to actual topic names from DB.
    
        Args:
            input_text: Topic numbers or names entered by student (e.g. "12, 7, 8")
            course_name: The course these topics belong to
        """
        raw_parts = [p.strip() for p in re.split(r'[,\s]+', input_text.strip()) if p.strip()]
    
        if not raw_parts:
            return "❌ No topics received. Please enter topic numbers or names."
    
        # Try to resolve numbers to actual topic names from DB
        resolved_topics = []
        
        if course_name:
            try:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                backend_dir = os.path.dirname(current_dir)
                db_path     = os.path.join(backend_dir, "database", "lms.db")
    
                conn = sqlite3.connect(db_path)
                cur  = conn.cursor()
    
                # Get course_id
                cur.execute(
                    "SELECT course_id FROM courses WHERE LOWER(course_name) = LOWER(?)",
                    (course_name.strip(),)
                )
                row = cur.fetchone()
                if not row:
                    cur.execute(
                        "SELECT course_id FROM courses WHERE LOWER(course_name) LIKE LOWER(?)",
                        (f"%{course_name.strip()}%",)
                    )
                    row = cur.fetchone()
    
                if row:
                    course_id = row[0]
                    # Fetch all topics as dict {number: name}
                    cur.execute(
                        "SELECT topic_number, topic_name FROM course_outlines "
                        "WHERE course_id = ? ORDER BY topic_number",
                        (course_id,)
                    )
                    topic_map = {str(r[0]): r[1] for r in cur.fetchall()}
    
                    for part in raw_parts:
                        if part in topic_map:
                            # It's a number — resolve to name
                            resolved_topics.append(topic_map[part])
                        else:
                            # It's already a name
                            resolved_topics.append(part)
    
                conn.close()

            except Exception as e:
                # If DB lookup fails, just use raw input
                resolved_topics = raw_parts
        else:
            resolved_topics = raw_parts

        if not resolved_topics:
            resolved_topics = raw_parts

        planner_data["weak_topics"]   = resolved_topics
        planner_data["target_course"] = course_name

        return (
            f"✅ Weak topics saved:\n"
            + "\n".join([f"   • {t}" for t in resolved_topics])
        )

    @function_tool
    def save_user_preferences(input_text: str) -> str:
        print(f"DEBUG save_user_preferences CALLED WITH: '{input_text}'")
        """
        Save study preferences.
        Accepts any of these formats:
          hours=3, days=5, style=mixed
          3, 5, mixed
          3 5 mixed
          hours=4 days=7 style=concept
        """
        text = input_text.lower().strip()
    
        # ── Extract hours ──────────────────────────────────────
        hours = None
        m = re.search(r'hours?\s*[=:]\s*(\d+)', text)
        if m:
            hours = int(m.group(1))
    
        # ── Extract days ───────────────────────────────────────
        days = None
        m = re.search(r'days?\s*[=:]\s*(\d+)', text)
        if m:
            days = int(m.group(1))
    
        # ── Positional fallback ONLY if named format not found ─
        if hours is None or days is None:
            nums = re.findall(r'\b(\d+)\b', text)
            if hours is None and len(nums) >= 1:
                hours = int(nums[0])
            if days is None and len(nums) >= 2:
                days = int(nums[1])
    
        # ── Extract style ──────────────────────────────────────
        style = "mixed"  # safe default
        if "concept" in text:
            style = "concept"
        elif "practice" in text:
            style = "practice"
        elif "mixed" in text:
            style = "mixed"
    
        # ── Validate ───────────────────────────────────────────
        errors = []
        if hours is None:
            errors.append("hours per day")
        if days is None:
            errors.append("number of days")
        if errors:
            return (
                f"❌ Could not parse: {', '.join(errors)}.\n"
                f"Please reply in this format: hours=3, days=5, style=mixed"
            )
    
        # ── Save ───────────────────────────────────────────────
        planner_data["hours_per_day"] = hours
        planner_data["days"]          = days
        planner_data["study_style"]   = style
    
        return (
            f"✅ Preferences saved!\n"
            f"• Hours/day  : {hours}\n"
            f"• Days       : {days}\n"
            f"• Study Style: {style}"
        )
        
    @function_tool
    def create_study_plan(hours_per_day: int, days: int, style: str) -> str:
        """
        Generate a detailed day-by-day study plan for a single course.
        Covers ALL course topics but gives extra focus to weak topics.

        Args:
            hours_per_day: Hours per day (1-6)
            days: Number of days (1-30)
            style: 'concept', 'practice', or 'mixed'
        """
        weak_topics   = planner_data.get("weak_topics", [])
        course_name   = planner_data.get("target_course", "")

        if not weak_topics:
            return "❌ No weak topics found. Please select your weak topics first."

        style         = style.lower().strip()
        if style not in ("concept", "practice", "mixed"):
            style = "mixed"
        hours_per_day = max(1, min(6, int(hours_per_day)))
        days          = max(1, min(30, int(days)))
    
        # ── Fetch ALL topics from DB ───────────────────────────
        all_topics = []
        if course_name:
            try:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                backend_dir = os.path.dirname(current_dir)
                db_path     = os.path.join(backend_dir, "database", "lms.db")
    
                conn = sqlite3.connect(db_path)
                cur  = conn.cursor()
    
                cur.execute(
                    "SELECT course_id FROM courses WHERE LOWER(course_name) = LOWER(?)",
                    (course_name.strip(),)
                )
                row = cur.fetchone()
                if not row:
                    cur.execute(
                        "SELECT course_id FROM courses WHERE LOWER(course_name) LIKE LOWER(?)",
                        (f"%{course_name.strip()}%",)
                    )
                    row = cur.fetchone()
    
                if row:
                    cur.execute(
                        "SELECT topic_name FROM course_outlines "
                        "WHERE course_id = ? ORDER BY topic_number",
                        (row[0],)
                    )
                    all_topics = [r[0] for r in cur.fetchall()]
    
                conn.close()
            except Exception:
                pass
    
        # Fallback: if no DB topics, use weak topics only
        if not all_topics:
            all_topics = weak_topics
    
        # ── Build topic schedule ───────────────────────────────
        # Each slot gets a topic. Weak topics appear more frequently.
        # Strategy: build a weighted pool then cycle through it.
        weak_set = set(weak_topics)
    
        # Weak topics appear 3x, other topics appear 1x
        weighted_pool = []
        for t in all_topics:
            if t in weak_set:
                weighted_pool.extend([t, t, t])  # 3x weight
            else:
                weighted_pool.append(t)           # 1x weight
    
        # ── Time slots ─────────────────────────────────────────
        all_slots = [
            "🌅 Morning       (9:00 AM  - 10:00 AM)",
            "📚 Late Morning  (11:00 AM - 12:00 PM)",
            "🕌 After Dhuhr   (1:00 PM  - 2:00 PM)",
            "☕ After Asr     (4:00 PM  - 5:00 PM)",
            "🌙 After Maghrib (6:00 PM  - 7:00 PM)",
            "⭐ After Isha    (8:00 PM  - 9:00 PM)",
        ]
        daily_slots = all_slots[:min(hours_per_day, len(all_slots))]
    
        # ── Build plan ─────────────────────────────────────────
        lines = []
        lines.append(f"📚 STUDY PLAN — {course_name.upper() if course_name else 'YOUR COURSE'}")
        lines.append(f"🎯 Weak Topics (Extra Focus):")
        for wt in weak_topics:
            lines.append(f"   ⚠️  {wt}")
        lines.append(f"⏰ Daily Study : {hours_per_day} hour(s)/day for {days} day(s)")
        lines.append(f"🎨 Study Style : {style.upper()}")
        lines.append(f"📖 Total Topics: {len(all_topics)} topics covered")
        lines.append("")
    
        slot_counter = 0  # global counter across all days to cycle weighted_pool
    
        for day in range(1, days + 1):
            lines.append(f"{'─' * 65}")
            lines.append(f"📅 DAY {day}")
            lines.append(f"{'─' * 65}")
    
            for slot_idx, slot in enumerate(daily_slots):
                topic      = weighted_pool[slot_counter % len(weighted_pool)]
                slot_counter += 1
                is_weak    = topic in weak_set
                weak_label = " ⚠️ WEAK TOPIC" if is_weak else ""
    
                if style == "concept":
                    activity = f"📖 Study: '{topic}'{weak_label}"
                    details  = (
                        "   • Read lecture notes\n"
                        "   • Watch explanation videos\n"
                        "   • Create concept maps"
                    )
                elif style == "practice":
                    activity = f"✍️ Practice: '{topic}'{weak_label}"
                    details  = (
                        "   • Solve exercises\n"
                        "   • Attempt past papers\n"
                        "   • Online quizzes"
                    )
                else:
                    if slot_idx % 2 == 0:
                        activity = f"📖 Learn: '{topic}'{weak_label}"
                        details  = (
                            "   • Understand fundamentals\n"
                            "   • Study examples and definitions"
                        )
                    else:
                        activity = f"✍️ Apply: '{topic}'{weak_label}"
                        details  = (
                            "   • Work through examples\n"
                            "   • Practice exercises"
                        )
    
                # YouTube search with course name + topic name
                search_query = f"{topic} in {course_name}".replace(" ", "+")
                yt = f"https://www.youtube.com/results?search_query={search_query}"
    
                lines.append(f"\n{slot}")
                lines.append(f"   → {activity}")
                lines.append(details)
                lines.append(f"   📺 Watch: {yt}")
    
            lines.append(f"\n🔄 End of Day {day} Review")
            lines.append("   • Summarise what you covered today")
            lines.append("   • Spend extra 15 min revisiting any weak topic")
            lines.append("   • Note anything unclear for tomorrow")
            lines.append("")
    
        lines.append("💡 STUDY TIPS")
        lines.append("• ⚠️ Weak topics appear 3x more often — don't skip them")
        lines.append("• All topics are covered — not just weak ones")
        lines.append("• Take 10-min breaks between sessions")
        lines.append("• Stay hydrated and get enough sleep")
        lines.append("• Consistency beats cramming every time")
        lines.append("\n🎯 You can do this! Stay consistent and good luck! 🌟")
    
        return "\n".join(lines)
    
    @function_tool
    async def get_all_courses_priorities() -> str:
        """Show all courses ranked by urgency based on predicted grade and credit hours."""
        profile = await _fetch_full_student_profile(student_id, db)
    
        if "error" in profile:
            return profile["error"]
        
        _cached_profile["data"] = profile
    
        grade_scores = {
            "F": 100, "D": 85, "D+": 80, "C-": 75, "C": 70,
            "C+": 65, "B-": 55, "B": 45, "B+": 35, "A-": 25, "A": 15,
        }
    
        courses_ranked = []
        for course in profile["courses"]:
            cursor = db.cursor()
            cursor.execute("""
                SELECT classes_attended, total_classes FROM attendance
                WHERE student_id=? AND course_id=(
                    SELECT course_id FROM courses WHERE course_name=?
                )
            """, (student_id, course["name"]))
            att = cursor.fetchone()
            att_pct = round((att[0] / att[1]) * 100, 1) if att and att[1] else 75
    
            grade_score       = grade_scores.get(course["predicted_grade"], 50)
            credit_score      = course["credit_hours"] * 10
            att_penalty       = max(0, (75 - att_pct) * 2) if att_pct < 75 else 0
            priority          = grade_score + credit_score + att_penalty
            needs_rescue      = course["predicted_grade"] in ["F","D","D+","C-","C"]
    
            courses_ranked.append({
                "name":         course["name"],
                "grade":        course["predicted_grade"],
                "percentage":   course["percentage"],
                "credit_hours": course["credit_hours"],
                "priority":     priority,
                "needs_rescue": needs_rescue,
                "att_pct":      att_pct,
            })

        courses_ranked.sort(key=lambda x: x["priority"], reverse=True)

        lines = ["📊 **COURSE PRIORITY RANKING**\n"]
        lines.append(f"{'#':<3} {'Course':<38} {'Grade':<6} {'%':<7} {'CH':<4} {'Urgency'}")
        lines.append("-" * 70)
    
        for i, c in enumerate(courses_ranked, 1):
            urgency = "🔴 CRITICAL" if c["needs_rescue"] else "🟡 IMPROVE"
            att_warn = " ⚠️" if c["att_pct"] < 75 else ""
            lines.append(
                f"{i:<3} {c['name']:<38} {c['grade']:<6} "
                f"{c['percentage']:<7} {c['credit_hours']:<4} {urgency}{att_warn}"
            )
    
        top = courses_ranked[0]
        lines.append(f"\n🎯 Most Urgent: {top['name']} (Grade: {top['grade']}, {top['percentage']}%)")
        lines.append("\nProvide your study preferences to generate a rescue plan.")
        lines.append("Format: hours=3, days=5, style=mixed")
    
        return "\n".join(lines)

    @function_tool
    async def create_rescue_plan_all(hours_per_day: int, days: int, style: str) -> str:
        """
        Generate a priority-based rescue plan for ALL courses.
        Critical courses get more time slots. Non-critical courses still appear.

        Args:
            hours_per_day: Hours per day (1-6)
            days: Number of days (1-30)
            style: 'concept', 'practice', or 'mixed'
        """
        style         = style.lower().strip()
        if style not in ("concept", "practice", "mixed"):
            style = "mixed"
        hours_per_day = max(1, min(6, int(hours_per_day)))
        days          = max(1, min(30, int(days)))
    
        # Use cached profile
        if _cached_profile["data"] is not None:
            profile = _cached_profile["data"]
        else:
            profile = await _fetch_full_student_profile(student_id, db)
    
        if "error" in profile:
            return profile["error"]
    
        grade_scores = {
            "F": 100, "D": 85, "D+": 80, "C-": 75, "C": 70,
            "C+": 65, "B-": 55, "B": 45, "B+": 35, "A-": 25, "A": 15,
        }
    
        courses_ranked = []
        for course in profile["courses"]:
            cursor = db.cursor()
            cursor.execute("""
                SELECT classes_attended, total_classes FROM attendance
                WHERE student_id=? AND course_id=(
                    SELECT course_id FROM courses WHERE course_name=?
                )
            """, (student_id, course["name"]))
            att     = cursor.fetchone()
            att_pct = round((att[0] / att[1]) * 100, 1) if att and att[1] else 75
    
            priority     = (
                grade_scores.get(course["predicted_grade"], 50)
                + course["credit_hours"] * 10
                + (max(0, (75 - att_pct) * 2) if att_pct < 75 else 0)
            )
            needs_rescue = course["predicted_grade"] in ["F", "D", "D+", "C-", "C"]
    
            courses_ranked.append({
                "name":         course["name"],
                "grade":        course["predicted_grade"],
                "percentage":   course["percentage"],
                "credit_hours": course["credit_hours"],
                "priority":     priority,
                "needs_rescue": needs_rescue,
            })
    
        courses_ranked.sort(key=lambda x: x["priority"], reverse=True)
    
        # ── Build weighted pool ────────────────────────────────
        # Critical courses get 3 slots, non-critical get 1 slot
        # This ensures ALL courses appear but urgent ones dominate
        weighted_courses = []
        for c in courses_ranked:
            if c["needs_rescue"]:
                weighted_courses.extend([c, c, c])   # 3x
            else:
                weighted_courses.append(c)            # 1x
    
        # ── Time slots ─────────────────────────────────────────
        all_slots = [
            "🌅 Morning       (8:00 AM  - 9:00 AM)",
            "📚 Late Morning  (10:00 AM - 11:00 AM)",
            "🕌 After Dhuhr   (1:00 PM  - 2:00 PM)",
            "☕ After Asr     (4:00 PM  - 5:00 PM)",
            "🌙 After Maghrib (6:00 PM  - 7:00 PM)",
            "⭐ After Isha    (8:00 PM  - 9:00 PM)",
        ]
        daily_slots = all_slots[:min(hours_per_day, len(all_slots))]
    
        # ── Build plan ─────────────────────────────────────────
        lines = []
        lines.append("=" * 75)
        lines.append("🚨 RESCUE PLAN — ALL COURSES")
        lines.append("=" * 75)
        lines.append(
            f"⏰ {hours_per_day} hour(s)/day  |  "
            f"{days} days  |  Style: {style.upper()}"
        )
        lines.append("")
        lines.append("📊 Priority Order (🔴 = 3x slots, 🟡 = 1x slot):")
        for i, c in enumerate(courses_ranked, 1):
            flag  = "🔴" if c["needs_rescue"] else "🟡"
            slots = "3x slots/day" if c["needs_rescue"] else "1x slot/day"
            lines.append(
                f"   {i}. {flag} {c['name']} "
                f"— {c['grade']} ({c['percentage']}%)  [{slots}]"
            )
        lines.append("")
    
        slot_counter = 0  # global across all days
    
        for day in range(1, days + 1):
            lines.append(f"{'─' * 75}")
            lines.append(f"📅 DAY {day}")
            lines.append(f"{'─' * 75}")
    
            for slot_idx, slot in enumerate(daily_slots):
                course     = weighted_courses[slot_counter % len(weighted_courses)]
                slot_counter += 1
                flag       = "🔴" if course["needs_rescue"] else "🟡"
    
                if style == "concept":
                    activity = f"📖 Study concepts: {course['name']} {flag}"
                    details  = (
                        "   • Review lecture notes\n"
                        "   • Watch explanation videos\n"
                        "   • Create concept summaries"
                    )
                elif style == "practice":
                    activity = f"✍️ Practice: {course['name']} {flag}"
                    details  = (
                        "   • Solve past papers\n"
                        "   • Take online quizzes\n"
                        "   • Practice exercises"
                    )
                else:
                    if slot_idx % 2 == 0:
                        activity = f"📖 Learn: {course['name']} {flag}"
                        details  = (
                            "   • Study theory and definitions\n"
                            "   • Understand core concepts"
                        )
                    else:
                        activity = f"✍️ Apply: {course['name']} {flag}"
                        details  = (
                            "   • Solve problems\n"
                            "   • Self-test with questions"
                        )
    
                yt = (
                    f"https://www.youtube.com/results?"
                    f"search_query={course['name'].replace(' ', '+')}+lecture+tutorial"
                )
                lines.append(f"\n{slot}")
                lines.append(f"   → {activity}")
                lines.append(details)
                lines.append(f"   📺 Watch: {yt}")
    
            lines.append(f"\n🔄 End of Day {day} Review")
            lines.append("   • Recap what you covered today")
            lines.append("   • Focus extra time on 🔴 topics if needed")
            lines.append("")
    
        lines.append("=" * 75)
        lines.append("💡 RESCUE TIPS")
        lines.append("=" * 75)
        lines.append("• 🔴 CRITICAL courses get 3x more time — they need it most")
        lines.append("• 🟡 courses still appear — don't neglect them")
        lines.append("• Use YouTube links — visual learning helps retention")
        lines.append("• Attend ALL remaining classes — every mark counts")
        lines.append("• Form study groups for challenging subjects")
        lines.append("\n🎯 You can turn this around! Start today! 💪")
    
        return "\n".join(lines)
            
    @function_tool
    async def get_semester_gpa() -> Dict[str, Any]:
        """
        Calculates predicted semester GPA using Bahria University Karachi grading.
        Internally fetches predicted grades and computes weighted GPA.
        """
        profile = await _fetch_full_student_profile(student_id, db)
        return calculate_gpa_from_courses(profile["courses"])

    # ── Notes tools ───────────────────────────────────────────────────────────

    @function_tool
    async def ask_notes(question: str) -> str:
        """
        Answers any question about the currently uploaded lecture file.
        Works for PDF, PowerPoint, Word, or image files.
        Uses semantic search + GPT-4o vision.
        """
        return await _answer_notes_question(question)

    @function_tool
    async def summarize_notes() -> str:
        """Summarizes the entire uploaded lecture file — all pages/slides."""
        return await _answer_notes_question(
            "Please summarize the entire document. Give me the main topics, "
            "key concepts, and anything important I should know for my exam."
        )

    @function_tool
    async def get_exam_topics() -> str:
        """Identifies topics from the uploaded file most likely to appear in a final exam."""
        return await _answer_notes_question(
            "Based on this material, what topics are most likely to appear "
            "in a university final exam? List them with brief explanations."
        )

    @function_tool
    async def check_notes_status() -> str:
        """Returns what file is currently uploaded, or asks the student to upload one."""
        return get_notes_summary() if notes_file_loaded() else "No file is currently uploaded."

    return {
        "lms":        [get_course_data],
        "prediction": [predict_single_course, predict_all_courses],
        "planner":    [save_user_preferences, get_course_prediction, fetch_course_topics, save_weak_topics, create_study_plan, create_rescue_plan_all, get_all_courses_priorities],
        "gpa":        [get_semester_gpa],
        "notes":      [ask_notes, summarize_notes, get_exam_topics, check_notes_status],
    }

# =========================================================
# BUILD AGENTS
# =========================================================

def build_agents(student_id: int, db: sqlite3.Connection) -> Agent:

    tools = build_tools(student_id, db)

    # ── LMS Data Agent ────────────────────────────────────────────────────────
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
        tools=tools["lms"],
    )

    # ── Prediction Agent ──────────────────────────────────────────────────────
    prediction_agent = Agent(
        name="Prediction Agent",
        model=model,
        instructions="""
        You are the Academic Prediction Agent for Bahria University Karachi. You predict final exam scores and grades using a trained Linear Regression ML model that considers the student's full academic history (Semesters 1-3) along with their current Semester 4 performance.

        ═══════════════════════════════════════════════
        STEP 1 — DECIDE: ALL COURSES or ONE COURSE?
        ═══════════════════════════════════════════════

        ALL COURSES — user says any of:
        "all courses", "all subjects", "everything", "all my grades", "predict everything", "show all predictions"
          → Call predict_all_courses() ONCE
          → Present the output EXACTLY as returned by the tool
          → Do NOT rewrite, summarise, or reformat anything

        ONE COURSE — user names a specific course:
          → Call predict_single_course(course_name) for that course
          → Present the output EXACTLY as returned by the tool
          → Do NOT rewrite, summarise, or reformat anything

        ═══════════════════════════════════════════════
        AVAILABLE COURSES (use exact spelling):
        ═══════════════════════════════════════════════
        - Operating Systems
        - Database Management Systems
        - Software Design and Architecture
        - Design and Analysis of Algorithms
        - Engineering Management

        ═══════════════════════════════════════════════
        HOW THE ML PREDICTION WORKS (for your awareness):
        ═══════════════════════════════════════════════
        The model uses these 8 features:
        1. Sem1_Marks       — Semester 1 total percentage
        2. Sem2_Marks       — Semester 2 total percentage
        3. Sem3_Marks       — Semester 3 total percentage
        4. Sem1_IA          — Semester 1 IA marks (out of 50)
        5. Sem2_IA          — Semester 2 IA marks (out of 50)
        6. Sem3_IA          — Semester 3 IA marks (out of 50)
        7. Sem4_IA          — Current semester IA (quiz + assignment + midterm)
        8. Pct_Upto_3Sem    — Average percentage across first 3 semesters
    
        This is more accurate than a fixed formula because it learns from 1000 real student records and accounts for each student's personal academic trajectory.
    
        ═══════════════════════════════════════════════
        IF USER ASKS HOW THE PREDICTION WORKS:
        ═══════════════════════════════════════════════
        Explain in simple terms:
        "Your predicted final exam score is calculated using a Machine Learnin model (Linear Regression) trained on 1000 student records. It looks at
        your performance across all 4 semesters — not just your current marks — to make a more accurate prediction. Students with consistently strong
        historical performance tend to perform better in finals, and the model captures this pattern."
    
        ═══════════════════════════════════════════════
        CRITICAL RULES — NEVER VIOLATE:
        ═══════════════════════════════════════════════
        - NEVER call both predict_single_course AND predict_all_courses
        - NEVER rewrite, round, or paraphrase tool output — show it verbatim
        - NEVER ask the student for their marks — the tools fetch everything
        - NEVER skip tool calls — always call the tool before responding
        - NEVER make up predictions — only use tool output
        - NEVER explain the calculation unless the student asks
        - If a course name is ambiguous, ask for clarification ONCE then call the tool with the clarified name
    
        ═══════════════════════════════════════════════
        TONE:
        ═══════════════════════════════════════════════
        - Professional but encouraging
        - If predicted grade is F or D: acknowledge it honestly, suggest they ask for a study plan
        - If predicted grade is A or B: acknowledge the strong performance
        - Keep any added commentary SHORT — the tool output is the main content
        """,
        handoff_description="Specialist agent for academic predictions and final exam forecasting",
        tools=tools["prediction"],
    )

    # ── Planner Agent ────────────────────────────────────────────────────────
    planner_agent = Agent(
        name="Planner Agent",
        model=model,
        instructions="""
    You are a Study Planner & Rescue Agent.

    ════════════════════════════════════════
    TWO MODES
    ════════════════════════════════════════

    MODE 1 — SINGLE COURSE (user names a course)
    MODE 2 — ALL COURSES   (user says "all", "everything", "rescue plan")

    ════════════════════════════════════════
    MODE 1 — SINGLE COURSE FLOW
    ════════════════════════════════════════

    STEP 1: Call get_course_prediction(course_name)
    STEP 2: Call fetch_course_topics(course_name)
            Show the numbered topic list to the student.
    STEP 3: Ask exactly this:
            "Which topics are you weak in? Enter numbers or names, separated by commas or spaces."
            Pass exactly what the user typed. Do not modify it.
    STEP 4: Call save_weak_topics(input_text=user_input, course_name=the_course_name)
            Pass the course name so topic numbers resolve to actual topic names.
            Example: save_weak_topics(input_text="12, 7, 8", course_name="Operating Systems")
    STEP 5: Ask: "How many hours per day, for how many days, and what style?
            (concept / practice / mixed)
            Example: hours=3, days=5, style=mixed"
    STEP 6: Extract hours, days, style from what the student types.
            Then call create_study_plan(hours_per_day=X, days=Y, style=Z)
            with the extracted values as typed parameters.

            Examples of how to extract:
            "4 5 concept"          → hours_per_day=4, days=5, style="concept"
            "hours=3, days=5"      → hours_per_day=3, days=5, style="mixed"
            "3, 5, mixed"          → hours_per_day=3, days=5, style="mixed"
            "4 hours 7 days mixed" → hours_per_day=4, days=7, style="mixed"

            First number = hours_per_day
            Second number = days
            Any style word = style (default "mixed" if not mentioned)

    STEP 7: Display the full plan output exactly as returned by the tool.

    CRITICAL FOR MODE 1:
    - NEVER call create_study_plan before save_weak_topics returns ✅
    - NEVER ask for weak topics again after save_weak_topics returns ✅
    - NEVER ask for preferences again after the student gives numbers
    - If save_weak_topics returns ✅, move IMMEDIATELY to asking for preferences
    - If the student gives you any two numbers, that is enough to call create_study_plan
    
    ════════════════════════════════════════
    MODE 2 — ALL COURSES FLOW
    ════════════════════════════════════════
    
    STEP 1: Call get_all_courses_priorities()
            Show the priority ranking to the student.
    STEP 2: Ask exactly this:
            "Please provide your study preferences.
            Example: hours=3, days=5, style=mixed"
    STEP 3: Call save_user_preferences(user_input)
            If the tool returns an error, show it and ask again.
    STEP 4: Call create_rescue_plan_all()
    STEP 5: Display the full rescue plan.
    
    ════════════════════════════════════════
    CRITICAL RULES — NEVER BREAK THESE
    ════════════════════════════════════════

    1. ALWAYS call save_user_preferences BEFORE calling create_study_plan
       or create_rescue_plan_all. Never skip this step.
    
    2. If any tool returns a message starting with ❌, STOP and show
       the error to the student. Ask for the correct input. Do NOT
       call the next tool until the error is resolved.
    
    3. Never generate a plan from your own knowledge.
       Always use the tools in the correct order.
    
    4. Never ask for weak topics in Mode 2.
    
    5. Accept topic input in ANY format — "1 3 5", "1,3,5",
       "Normalization, Transactions" — pass it all directly to save_weak_topics.
    
    6. Accept preferences in ANY format — "3 5 mixed", "hours=3, days=5, style=mixed",
       "3 hours, 5 days" — pass it all directly to save_user_preferences.

    ════════════════════════════════════════
    WHAT CAUSED MAX TURNS ERROR (avoid this)
    ════════════════════════════════════════

    ❌ Calling create_study_plan before save_user_preferences
    ❌ Retrying a failed tool call without fixing the input
    ❌ Skipping save_weak_topics and going straight to preferences
    ❌ Calling create_rescue_plan_all for single course
    ❌ Calling create_study_plan for all courses
    
    ════════════════════════════════════════
    TONE
    ════════════════════════════════════════
    Be encouraging, clear, and step-by-step.
    Never overwhelm the student with too many questions at once.
    One question per message. One step at a time.
    """,
        handoff_description="Specialist agent for study plans (single course with weak topics OR all courses priority-based rescue plan)",
        tools=tools["planner"],
    )

    # ── GPA Agent ─────────────────────────────────────────────────────────────
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

        STEP 1 → Call get_semester_gpa
                 This returns all courses with credit_hours, predicted_grade,
                 and the computed weighted GPA.
                 DO NOT ask the user for grades. The tool handles everything.

        STEP 2 → Present the result in the format below.

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
        - NEVER manually calculate GPA — always use get_semester_gpa tool
        - NEVER ask the user for their grades
        - NEVER predict individual course grades yourself
        - NEVER answer non-GPA questions; redirect to triage agent
        """,
        handoff_description="Specialist agent for semester GPA calculation based on predicted grades and credit hours (Bahria University Karachi grading scheme)",
        tools=tools["gpa"],
    )

    # ── Notes Agent ───────────────────────────────────────────────────────────
    notes_agent = Agent(
        name="Notes Agent",
        model=notes_model,
        instructions="""
        You are the **Notes & Study Material Agent** — a friendly academic tutor
        that helps students understand their own uploaded lecture files.

        ═══════════════════════════════════════════════
        WHAT YOU CAN DO:
        ═══════════════════════════════════════════════
        - Explain any page or slide in simple words
        - Summarize the entire document or specific sections
        - Answer any question about the content
        - Identify topics likely to appear in the final exam
        - Explain diagrams, formulas, or images (you can see them)

        ═══════════════════════════════════════════════
        WORKFLOW:
        ═══════════════════════════════════════════════

        STEP 1 → Check if a file is loaded using check_notes_status
                 If no file is loaded → tell the student to upload one first

        STEP 2 → Based on what the student asks:
          • "Summarize" / "what is this about" / "explain everything"
              → call summarize_notes()
          • "What will come in exam" / "exam topics" / "important topics"
              → call get_exam_topics()
          • Any specific question, page, slide, topic, formula, concept
              → call ask_notes(question) with the student's exact question

        STEP 3 → Present the answer clearly.
                 Always tell the student which page/slide the answer came from.

        ═══════════════════════════════════════════════
        TONE & STYLE:
        ═══════════════════════════════════════════════
        - Talk like a helpful senior student, not a textbook
        - Use simple words — assume the student is confused
        - Use bullet points and short sentences
        - Give real-world examples when explaining concepts
        - Be encouraging: "Great question!", "This is actually simple once you see it"

        ═══════════════════════════════════════════════
        STRICT RULES:
        ═══════════════════════════════════════════════
        - ALWAYS use tools — never answer from your own knowledge about the subject
        - The answer must come from the uploaded file, not from what you know generally
        - NEVER make up content that isn't in the file
        - If the student asks about something not in the file, say so honestly
        """,
        handoff_description=(
            "Specialist agent for understanding uploaded lecture files — "
            "PDFs, PowerPoints, Word docs, images. Explains slides, summarizes, "
            "answers questions about the content, identifies exam topics."
        ),
        tools=tools["notes"],
    )

    # ── Triage Agent (main entry point) ──────────────────────────────────────
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
        2. If course is missing AND the query is clearly about a SINGLE course → ASK:
           "Which course would you like that for?"
           BUT: if the user says "all courses", "all subjects", or "everything" →
           HANDOFF IMMEDIATELY — do NOT ask for clarification.
        3. Route queries properly:
           - Quiz / assignment / attendance → LMS Agent
           - Prediction / expected grade → Prediction Agent
           - Study plan / rescue plan → Planner Agent
           - GPA / semester GPA / overall GPA → GPA Agent
           - Uploaded file / lecture notes / slides / PDF / explain slide / summarize → Notes Agent
        4. Never answer academic data questions yourself.
        5. Never default to Calculus.
        
        If query is incomplete (single course implied, no course named):
        Example:
        User: "Show my quiz marks"
        You respond:
        "Sure! Which course would you like to see quiz marks for?"
        
        If query clearly covers ALL courses — handoff immediately:
        User: "Predict my final exam marks for all courses" → [Handoff to Prediction Agent]
        User: "Show me everything"                         → [Handoff to LMS Agent]
        User: "Make a plan for all my subjects"            → [Handoff to Planner Agent]
        
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

        5. **NOTES AGENT** (Handoff via `handoff to Notes Agent`)
           - CAPABILITIES: Reads uploaded lecture files (PDF, PPT, DOCX, images).
             Explains slides/pages, summarizes documents, answers content questions,
             identifies exam topics. Can READ images and diagrams using vision.
           - USE WHEN: Student mentions a file, slide, lecture, notes, "explain page X",
             "what is in slide 3", "summarize my notes", "what topics for exam",
             "uploaded", "my PDF", "my PowerPoint", or asks about subject content

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

        Is the query about UPLOADED FILES / LECTURE NOTES / SLIDES / EXPLAINING CONTENT?
        → YES → HANDOFF TO NOTES AGENT
        → NO → ↓

        → CLARIFY: "I can help you with checking your grades, predicting final scores,
          creating study plans, calculating your GPA, or explaining your uploaded lecture notes.
          Which one would you like help with?"
        ```
    
        🗣️ **GREETING PROTOCOL (First interaction only):**
    
        ```
        🎓 Hello! I'm your Academic AI Companion.
    
        I can help you with five things:
    
        📊 **Check Your Grades** - Quiz marks, assignment scores, attendance
        🔮 **Predict Final Scores** - Forecast your exam performance  
        📚 **Create Study Plans** - Personalized schedules and strategies
        🎓 **Calculate Your GPA** - Predicted semester GPA (Bahria University Karachi)
        📖 **Explain Your Notes** - Upload any lecture file and ask me anything about it
    
        What would you like help with today?
        ```
    
        🚫 **CRITICAL RULES - NEVER VIOLATE:**
        1. NEVER answer academic queries yourself. ALWAYS hand off to the appropriate specialist.
        2. NEVER display data, make predictions, give study advice, or compute GPA. You are a router.
        3. NEVER reveal that you're handing off.
        4. NEVER apologize for limitations.
        5. NEVER assume what the student wants. If unclear, present the options clearly.
        
        ✅ **CORRECT HANDOFF EXAMPLES:**
        
        User: "What's my quiz marks?"                          → [Immediate handoff to LMS Agent]
        User: "Will I pass calculus?"                          → [Immediate handoff to Prediction Agent]
        User: "Predict my final exam marks for all courses"    → [Immediate handoff to Prediction Agent]
        User: "Help me study"                                  → [Immediate handoff to Planner Agent]
        User: "What's my GPA?"                                 → [Immediate handoff to GPA Agent]
        User: "Calculate my semester GPA"                      → [Immediate handoff to GPA Agent]
        User: "Explain slide 3"                                → [Immediate handoff to Notes Agent]
        User: "Summarize my notes"                             → [Immediate handoff to Notes Agent]
        User: "What topics are important in my PDF?"           → [Immediate handoff to Notes Agent]
        User: "Explain page 5 in simple words"                 → [Immediate handoff to Notes Agent]
        
        ❌ **INCORRECT RESPONSES:**
        
        "Let me check your quiz marks..." → WRONG (you're not the LMS Agent)
        "I predict you'll get..."         → WRONG (you're not the Prediction Agent)
        "You should study..."             → WRONG (you're not the Planner Agent)
        "Your GPA is..."                  → WRONG (you're not the GPA Agent)
        "I'll transfer you to..."         → WRONG (don't mention handoffs)
        
        🎯 **YOUR ONLY JOB:**
        Identify the query type → Handoff to correct specialist → Stay silent otherwise.
        """,
        handoffs=[lms_agent, prediction_agent, planner_agent, gpa_agent, notes_agent],
    )

    return triage_agent