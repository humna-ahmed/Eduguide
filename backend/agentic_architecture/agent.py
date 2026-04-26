# agent.py
import os
import io
import re
import base64
import asyncio
import sqlite3
import tempfile
from dataclasses import dataclass
from typing import Dict, Any, Optional, List

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
    openai_client=openai_client,
)

# RunConfig with temperature=0 is passed to Runner.run for the prediction agent.
# temperature=0 → deterministic output (same input = same grade every time).
# This is the FIRST layer of consistency; the cache below is the SECOND.
predictive_run_config = RunConfig(
    model=predictive_ft_model,
    model_settings={"temperature": 0.0},
)

planner_ft_model = OpenAIChatCompletionsModel(
    model="ft:gpt-4o-mini-2024-07-18:personal::DVVFYRLI",
    openai_client=openai_client
)

# GPT-4o is used exclusively by the Notes Agent because it supports
# vision (reading images, scanned PDFs, PowerPoint slides as images).
notes_model = OpenAIChatCompletionsModel(
    model="gpt-4o",
    openai_client=openai_client
)

# =========================================================
# PREDICTION CACHE  ← SECOND LAYER OF CONSISTENCY PROTECTION
# =========================================================
# Keyed by (student_id, course_name_lowercase).
# Populated on the FIRST call to run_prediction_agent for a given course.
# Every subsequent call — whether from Prediction Agent, Planner Agent,
# or GPA Agent — returns the cached result WITHOUT calling the LLM again.
# This guarantees that the same grade is used everywhere in one session.
# Call clear_prediction_cache() at the start of a new conversation.
_prediction_cache: Dict[tuple, Dict[str, Any]] = {}

def clear_prediction_cache() -> None:
    """Call this at the start of each new student session."""
    _prediction_cache.clear()

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
    if course_name:
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
# NOTES AGENT — PAGE DATACLASS
# =========================================================

@dataclass
class Page:
    """Represents one page (PDF), slide (PPTX), or chunk (DOCX/image)."""
    page_number: int
    label: str        # e.g. "Page 3" or "Slide 5"
    text: str         # extracted text content
    image_b64: str = ""   # base64 PNG — set for PDFs and images (GPT-4o vision)


# =========================================================
# NOTES AGENT — FILE EXTRACTION (all formats)
# =========================================================

def _pil_to_b64(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _extract_pdf(path: str) -> List[Page]:
    import fitz  # pymupdf
    pages = []
    doc = fitz.open(path)
    for i, pdf_page in enumerate(doc, start=1):
        text = pdf_page.get_text("text").strip()
        pix  = pdf_page.get_pixmap(dpi=150)
        from PIL import Image as PILImage
        img  = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
        pages.append(Page(i, f"Page {i}", text, _pil_to_b64(img)))
    doc.close()
    return pages


def _extract_pptx(path: str) -> List[Page]:
    from pptx import Presentation
    prs   = Presentation(path)
    pages = []
    for i, slide in enumerate(prs.slides, start=1):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    line = " ".join(r.text for r in para.runs).strip()
                    if line:
                        texts.append(line)
            if shape.shape_type == 19:          # TABLE
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
    """Main entry point — detects file type and extracts pages."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _extract_pdf(path)
    elif ext == ".pptx":
        return _extract_pptx(path)
    elif ext == ".docx":
        return _extract_docx(path)
    elif ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
        return _extract_image(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


# =========================================================
# NOTES AGENT — IN-MEMORY STORE (session-scoped)
# =========================================================
# Holds the currently uploaded file for the session.
# Reset via clear_notes_store() when a new file is uploaded.

_notes_pages: List[Page] = []
_notes_filename: str = ""


def load_notes_file(pages: List[Page], filename: str) -> None:
    """
    Called by the Streamlit UI after file processing.
    Stores pages in memory AND triggers ChromaDB indexing (embedding).
    Streamlit is synchronous so we run the async indexing via asyncio.
    """
    global _notes_pages, _notes_filename
    _notes_pages    = pages
    _notes_filename = filename
    import asyncio as _asyncio
    try:
        loop = _asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(_asyncio.run, index_pages_into_chromadb(pages, filename))
                future.result()
        else:
            loop.run_until_complete(index_pages_into_chromadb(pages, filename))
    except RuntimeError:
        _asyncio.run(index_pages_into_chromadb(pages, filename))


def clear_notes_store() -> None:
    global _notes_pages, _notes_filename, _chroma_collection
    _notes_pages       = []
    _notes_filename    = ""
    _chroma_collection = None


def notes_file_loaded() -> bool:
    return len(_notes_pages) > 0


def get_notes_summary() -> str:
    if not _notes_pages:
        return "No file loaded."
    label = _notes_pages[0].label.split()[0]
    return f"'{_notes_filename}' — {len(_notes_pages)} {label}(s) loaded."


# =========================================================
# NOTES AGENT — VECTOR DATABASE SETUP (ChromaDB)
# =========================================================
# ChromaDB is a local persistent vector database.
# It stores page text + embeddings on disk (./chroma_store/)
# so they survive app restarts.
#
# Each uploaded file gets its own isolated collection,
# named by a sanitized version of the filename.
#
# EMBEDDING MODEL: text-embedding-3-small (OpenAI)
#   Converts text into a 1536-dimensional float vector.
#   Similar meaning = vectors close together in vector space.
#   Enables semantic search: synonyms and paraphrases still match.
#
# RETRIEVAL: ChromaDB cosine similarity search
#   Query is embedded -> nearest page vectors found -> pages returned.

import chromadb
from chromadb.config import Settings as ChromaSettings

# Persistent ChromaDB client — writes to ./chroma_store/ automatically
_chroma_client = chromadb.PersistentClient(
    path="./chroma_store",
    settings=ChromaSettings(anonymized_telemetry=False),
)

# Active ChromaDB collection for the currently loaded file
_chroma_collection = None


def _sanitize_collection_name(filename: str) -> str:
    """
    ChromaDB collection names: 3-63 chars, alphanumeric + hyphens only.
    e.g. 'Waves Physics.pdf' -> 'waves-physics'
    """
    import re as _re
    name = os.path.splitext(filename)[0]
    name = _re.sub(r'[^a-zA-Z0-9]+', '-', name)
    name = name.strip('-').lower()[:60]
    return name if len(name) >= 3 else name + '-doc'


# =========================================================
# NOTES AGENT — EMBEDDING (text-embedding-3-small)
# =========================================================

async def _embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Embed a batch of strings using OpenAI text-embedding-3-small.
    Returns a list of 1536-dimensional float vectors.
    Batches up to 100 texts per API call (OpenAI rate limit).
    """
    embeddings = []
    for i in range(0, len(texts), 100):
        batch = [t if t.strip() else 'empty page' for t in texts[i:i+100]]
        response = await openai_client.embeddings.create(
            model='text-embedding-3-small',
            input=batch,
        )
        embeddings.extend([item.embedding for item in response.data])
    return embeddings


# =========================================================
# NOTES AGENT — INDEXING (embed pages -> store in ChromaDB)
# =========================================================

async def index_pages_into_chromadb(pages: List[Page], filename: str) -> None:
    """
    Called once when a file is uploaded. Full indexing pipeline:

      1. Create (or reset) a ChromaDB collection for this file
      2. Embed all page texts using text-embedding-3-small
      3. Store text + embedding + metadata in ChromaDB

    Note: Images stay in _notes_pages (in memory) — ChromaDB stores
    vectors and text only. Images are attached separately for GPT-4o vision.
    """
    global _chroma_collection

    collection_name = _sanitize_collection_name(filename)

    # Delete existing collection for this filename (handles re-uploads)
    try:
        _chroma_client.delete_collection(collection_name)
    except Exception:
        pass

    _chroma_collection = _chroma_client.create_collection(
        name=collection_name,
        metadata={'hnsw:space': 'cosine'},
    )

    ids        = [str(p.page_number) for p in pages]
    texts      = [p.text if p.text.strip() else 'empty page' for p in pages]
    metadatas  = [
        {'label': p.label, 'page_number': p.page_number, 'has_image': bool(p.image_b64)}
        for p in pages
    ]

    embeddings = await _embed_texts(texts)

    _chroma_collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )


# =========================================================
# NOTES AGENT — RAG: RETRIEVAL (semantic search via ChromaDB)
# =========================================================

async def _retrieve_pages_semantic(query: str, max_pages: int = 4) -> List[Page]:
    """
    Semantic retrieval using embedding cosine similarity.

    Pipeline:
      1. Embed the student query using text-embedding-3-small
      2. Query ChromaDB for nearest page embeddings
      3. Return those Page objects (including their images for GPT-4o)

    Why better than keyword search:
      'area under a curve' finds 'integration' pages
      'rate of change' finds 'derivative' pages
      Works across synonyms, paraphrases, conceptual similarity.

    Three-rule cascade (page number and summarize override semantic search):
      Rule 1 — Explicit page/slide number  -> return that exact page
      Rule 2 — Full-document keywords      -> return first 8 pages
      Rule 3 — Semantic search via ChromaDB
    """
    global _chroma_collection

    q = query.lower()

    # Rule 1: explicit page number
    m = re.search(r'(slide|page|pg\.?)\s*(\d+)', q)
    if m:
        target  = int(m.group(2))
        matched = [p for p in _notes_pages if p.page_number == target]
        if matched:
            return matched
        nearest = min(_notes_pages, key=lambda p: abs(p.page_number - target))
        return [nearest]

    # Rule 2a: page-by-page — return ALL pages in order
    page_by_page_kw = [
        'page by page', 'slide by slide', 'page-by-page', 'slide-by-slide',
        'explain each page', 'explain each slide', 'explain every page',
        'explain every slide', 'go through each', 'one by one',
        'walk me through each', 'explain the whole pdf',
        'explain the whole ppt', 'explain the whole presentation',
        'explain all pages', 'explain all slides',
    ]
    if any(kw in q for kw in page_by_page_kw):
        return _notes_pages   # ALL pages — no cap

    # Rule 2b: full-document summary — return ALL pages (no cap)
    full_doc_kw = [
        'summarize', 'summary', 'summarise', 'everything', 'whole',
        'entire', 'all slides', 'all pages', 'overview',
        'what is this about', 'explain the whole', 'explain all', 'explain everything',
    ]
    if any(kw in q for kw in full_doc_kw):
        return _notes_pages   # ALL pages — no cap

    # Rule 3: ChromaDB semantic search
    if _chroma_collection is None or not _notes_pages:
        return [_notes_pages[0]] if _notes_pages else []

    query_embedding = await _embed_texts([query])

    results = _chroma_collection.query(
        query_embeddings=query_embedding,
        n_results=min(max_pages, len(_notes_pages)),
        include=['metadatas', 'documents', 'distances'],
    )

    retrieved_page_numbers = [
        int(meta['page_number']) for meta in results['metadatas'][0]
    ]

    page_map  = {p.page_number: p for p in _notes_pages}
    retrieved = [page_map[num] for num in retrieved_page_numbers if num in page_map]
    return retrieved if retrieved else [_notes_pages[0]]


# =========================================================
# NOTES AGENT — RAG: GENERATION (build GPT-4o message)
# =========================================================

def _build_notes_messages(query: str, pages: List[Page]) -> list:
    """
    Builds the OpenAI messages payload.
    Retrieved page text (from ChromaDB) is included as context.
    Base64 images attached for GPT-4o vision where available.

    This is the AUGMENTED GENERATION step:
    LLM answers using retrieved context, not training knowledge.
    """
    system = (
        f"You are a friendly academic tutor helping a university student understand "
        f"their course material from '{_notes_filename}'.\n\n"
        "Rules:\n"
        "- Explain clearly and simply — tutor style, not textbook\n"
        "- Use bullet points and plain language\n"
        "- Give a real-world example when explaining a concept\n"
        "- When summarizing, be concise but complete\n"
        "- When asked about exam topics, highlight repeated concepts\n"
        "- Always reference the specific page or slide number\n"
        "- Be warm and encouraging\n"
        "- ONLY answer from the provided content — not from outside knowledge"
    )

    user_parts = []
    total_pages = len(pages)
    page_by_page_mode = total_pages > 4

    context = "\n\n".join(
        f"--- {p.label} ---\n{p.text}" for p in pages if p.text
    )

    if context:
        if page_by_page_mode:
            instruction = (
                f"The student wants a full explanation of all {total_pages} pages/slides. "
                f"Go through EVERY page in order. "
                f"For each page: use the page/slide number as a heading, "
                f"explain the content in simple words, and give an example if relevant. "
                f"Do not skip any page."
            )
        else:
            instruction = "Answer the student's question using the content below."

        user_parts.append({
            "type": "text",
            "text": (
                f"{instruction}\n\n"
                f"Content from the uploaded file:\n\n{context}"
                f"\n\n---\nStudent question: {query}"
            )
        })
    else:
        user_parts.append({"type": "text", "text": f"Student question: {query}"})

    # Attach images for vision — capped at 10 to stay within token budget
    images_attached = 0
    for p in pages:
        if p.image_b64 and images_attached < 10:
            user_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{p.image_b64}", "detail": "high"}
            })
            images_attached += 1

    return [
        {"role": "system", "content": system},
        {"role": "user",   "content": user_parts},
    ]


# =========================================================
# NOTES AGENT — CORE ASYNC FUNCTION
# =========================================================

async def _answer_notes_question_async(query: str) -> str:
    """
    Full RAG pipeline: RETRIEVE -> AUGMENT -> GENERATE

      RETRIEVE  : ChromaDB semantic search finds most relevant pages
      AUGMENT   : Retrieved pages become context in the LLM prompt
      GENERATE  : GPT-4o answers using only the retrieved context
    """
    if not _notes_pages:
        return (
            "No file is uploaded yet. Please upload a PDF, PowerPoint, "
            "Word document, or image first, then ask your question."
        )

    pages    = await _retrieve_pages_semantic(query)
    messages = _build_notes_messages(query, pages)

    # Scale max_tokens with number of pages retrieved:
    # few pages -> 1500 tokens, full document -> up to 8000 tokens
    max_tok = min(1500 + (len(pages) - 1) * 500, 8000)

    resp = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=max_tok,
        temperature=0.3,
    )

    answer    = resp.choices[0].message.content
    page_refs = (
        f"all {len(pages)} pages"
        if len(pages) > 4
        else ", ".join(p.label for p in pages)
    )
    return f"{answer}\\n\\n*📄 Retrieved via semantic search: {page_refs}*"


# =========================================================
# PREDICTION FORMULA (Python — deterministic, no LLM needed)
# =========================================================

def predict_final_exam(quiz_total: float, assignment_total: float, midterm: float) -> int:
    """
    Computes predicted final exam score (out of 50) using the same
    weighted formula used to build the training dataset:
      - Midterm     → 60% weight  (strongest predictor)
      - Quizzes     → 20% weight
      - Assignments → 20% weight

    Inputs are already on their natural scales:
      quiz_total:        0–10
      assignment_total:  0–20
      midterm:           0–20

    Returns an integer 5–50.
    """
    q_norm = quiz_total / 10        # 0.0–1.0
    a_norm = assignment_total / 20  # 0.0–1.0
    m_norm = midterm / 20           # 0.0–1.0

    raw = (m_norm * 0.60 + q_norm * 0.20 + a_norm * 0.20) * 50

    # Small deterministic noise (same as dataset generation — keeps model aligned)
    noise = ((round(quiz_total) * 3 + round(assignment_total) * 7 + round(midterm) * 13) % 5) - 2

    return max(5, min(50, round(raw + noise)))


def get_grade_from_total(total: float) -> str:
    """Maps total percentage (0–100) to Bahria University Karachi grade."""
    if total >= 85:  return "A"
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

def calculate_gpa_from_courses(courses: List[Dict[str, Any]]) -> Dict[str, Any]:
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
    """
    Predicts the final grade for a given course.

    CONSISTENCY GUARANTEE (two layers):
    1. Cache check: if this (student_id, course_name) pair has already been
       predicted in this session, return the cached result immediately —
       no LLM call at all. Planner, GPA, and Prediction agents all see
       the exact same grade.
    2. temperature=0 on predictive_ft_model: even on the first (uncached)
       call, the model is fully deterministic for identical input tokens.
    """
    import json, re

    cache_key = (student_id, course_name.strip().lower())

    if cache_key in _prediction_cache:
        # Return the EXACT same result produced on the first call — no LLM.
        return json.dumps(_prediction_cache[cache_key])

    # ── First call: run the LLM and populate the cache ──────────────────
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
        5. RETURN OUTPUT AS VALID JSON ONLY (no extra text, no markdown fences):

        {"course": "...", "predicted_final_exam": number, "total_marks": number, "percentage": number, "grade": "A/B/C"}
        """,
        tools=tools
    )

    result = await Runner.run(
        predictive_agent,
        input=f"Predict my final result for {course_name}",
        run_config=predictive_run_config,
    )

    raw_output = result.final_output

    # ── Robust JSON parsing: handle markdown fences and stray text ───────
    parsed = None
    try:
        parsed = json.loads(raw_output)
    except (json.JSONDecodeError, TypeError):
        cleaned = re.sub(r"```(?:json)?", "", str(raw_output)).strip().rstrip("`").strip()
        try:
            parsed = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            match = re.search(r"\{.*?\}", cleaned, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group())
                except (json.JSONDecodeError, ValueError):
                    pass

    if parsed and isinstance(parsed, dict) and "grade" in parsed:
        _prediction_cache[cache_key] = parsed   # store in cache
        return json.dumps(parsed)

    # ── Fallback: LLM output wasn't parseable — use Python formula ──────────
    # This guarantees a valid result even if the fine-tuned model returns prose.
    import json as _json

    # We need the actual marks to compute. Fetch them from DB.
    try:
        course_data = await _get_course_data_async(course_name, student_id, db)
        quizzes     = course_data.get("quizzes", [])
        assignments = course_data.get("assignments", [])
        mid_info    = course_data.get("midterm", {})

        q_total = sum(q["obtained"] for q in quizzes)
        q_max   = sum(q["max"]      for q in quizzes) or 1
        quiz_total = round((q_total / q_max) * 10, 2)

        a_total = sum(a["obtained"] for a in assignments)
        a_max   = sum(a["max"]      for a in assignments) or 1
        assignment_total = round((a_total / a_max) * 20, 2)

        midterm = float(mid_info.get("marks", 0)) if isinstance(mid_info, dict) else 0.0

        predicted_final = predict_final_exam(quiz_total, assignment_total, midterm)
        total_marks     = round(quiz_total + assignment_total + midterm + predicted_final, 2)
        percentage      = total_marks
        predicted_grade = get_grade_from_total(percentage)

        fallback_result = {
            "course":               course_name,
            "predicted_final_exam": predicted_final,
            "total_marks":          total_marks,
            "percentage":           percentage,
            "grade":                predicted_grade,
        }
        _prediction_cache[cache_key] = fallback_result
        return _json.dumps(fallback_result)

    except Exception:
        # Absolute last resort
        return _json.dumps({
            "course": course_name,
            "predicted_final_exam": 0,
            "total_marks": 0,
            "percentage": 0,
            "grade": "N/A",
        })

def build_tools(student_id: int, db: sqlite3.Connection):
    # Your existing tools should work with this db connection
    @function_tool
    async def get_course_data(course_name: str):
        return await _get_course_data_async(course_name, student_id, db)  # Uses passed db

    @function_tool
    async def get_performance_data(course_name: str):
        return await _get_performance_data_async(course_name, student_id, db)

    @function_tool
    async def get_course_analysis(course_name: str = ""):
        """
        Analyzes attendance risk per course.
        Pass a specific course name, or leave empty string for all courses.
        """
        return await _get_course_analysis_async(
            course_name if course_name.strip() else None,
            student_id, db
        )
    
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
        Fetches all courses with EXACT marks from the DB and computes
        the predicted final exam score using the Python formula directly.

        NO LLM is called here — prediction is pure deterministic math.
        This eliminates all hallucination of mark values and silent failures.

        Shared by Prediction Agent, Planner Agent, and GPA Agent.
        """
        cursor = db.cursor()

        # Fetch all courses — schema: course_id, course_name, credit_hours
        cursor.execute(
            "SELECT course_id, course_name, credit_hours FROM courses"
        )
        courses = cursor.fetchall()

        result = []

        for course_id, cname, ch in courses:

            # ── Exact quiz total from DB ─────────────────────────────────────
            cursor.execute("""
                SELECT COALESCE(SUM(marks_obtained), 0),
                       COALESCE(SUM(max_marks), 0)
                FROM quizzes
                WHERE student_id = ? AND course_id = ?
            """, (student_id, course_id))
            q_row = cursor.fetchone()
            q_obtained, q_max = q_row if q_row else (0, 0)
            quiz_total = round((q_obtained / q_max) * 10, 2) if q_max > 0 else 0.0

            # ── Exact assignment total from DB ───────────────────────────────
            cursor.execute("""
                SELECT COALESCE(SUM(marks_obtained), 0),
                       COALESCE(SUM(max_marks), 0)
                FROM assignments
                WHERE student_id = ? AND course_id = ?
            """, (student_id, course_id))
            a_row = cursor.fetchone()
            a_obtained, a_max = a_row if a_row else (0, 0)
            assignment_total = round((a_obtained / a_max) * 20, 2) if a_max > 0 else 0.0

            # ── Exact midterm from DB ────────────────────────────────────────
            cursor.execute("""
                SELECT midterm FROM marks
                WHERE student_id = ? AND course_id = ?
            """, (student_id, course_id))
            mid_row = cursor.fetchone()
            midterm = float(mid_row[0]) if mid_row and mid_row[0] is not None else 0.0

            # ── Attendance ───────────────────────────────────────────────────
            cursor.execute("""
                SELECT classes_attended, total_classes
                FROM attendance
                WHERE student_id = ? AND course_id = ?
            """, (student_id, course_id))
            att_row = cursor.fetchone()
            attendance_pct = (
                round((att_row[0] / att_row[1]) * 100, 1)
                if att_row and att_row[1] else 0.0
            )

            # ── Predict using Python formula (deterministic, no LLM) ─────────
            cache_key = (student_id, cname.strip().lower())
            if cache_key in _prediction_cache:
                cached          = _prediction_cache[cache_key]
                predicted_final = cached["predicted_final_exam"]
                predicted_grade = cached["grade"]
                total_marks     = cached["total_marks"]
                percentage      = cached["percentage"]
            else:
                predicted_final = predict_final_exam(quiz_total, assignment_total, midterm)
                total_marks     = round(quiz_total + assignment_total + midterm + predicted_final, 2)
                percentage      = total_marks          # out of 100
                predicted_grade = get_grade_from_total(percentage)

                # Store in cache so every agent sees the same values
                _prediction_cache[cache_key] = {
                    "predicted_final_exam": predicted_final,
                    "grade":                predicted_grade,
                    "total_marks":          total_marks,
                    "percentage":           percentage,
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
                "percentage":       percentage,
            })

        return {"courses": result}

    @function_tool
    async def compute_course_priority(courses_json: str) -> str:
        """
        Ranks courses by study priority (credit hours x grade urgency).
        Pass the courses list as a JSON string.
        Each item needs: name (str), credit_hours (int), predicted_grade (str).
        Returns a JSON string of ranked courses with priority_score.
        """
        import json as _j
        courses = _j.loads(courses_json)
        grade_map = {
            "A": 10, "A-": 9, "B+": 8, "B": 7,
            "B-": 6, "C+": 5, "C": 4,
            "C-": 3, "D+": 2, "D": 1, "F": 0
        }
        result = []
        for course in courses:
            grade_score   = grade_map.get(course.get("predicted_grade", "F"), 0)
            priority_score = course.get("credit_hours", 1) * (10 - grade_score)
            result.append({
                "course":         course.get("name", "Unknown"),
                "priority_score": priority_score
            })
        return _j.dumps(sorted(result, key=lambda x: x["priority_score"], reverse=True))

    # ── NEW TOOL: GPA Calculator ──────────────────────────────────────────────
    @function_tool
    async def compute_gpa(courses_json: str) -> str:
        """
        Calculates predicted semester GPA using Bahria University Karachi grading scheme.
        Pass the courses list as a JSON string.
        Each item needs: name (str), credit_hours (int), predicted_grade (str).
        Returns a JSON string with gpa, standing, breakdown, total_credit_hours.
        """
        import json as _j
        courses = _j.loads(courses_json)
        return _j.dumps(calculate_gpa_from_courses(courses))
    @function_tool
    async def generate_study_plan(courses_json: str) -> str:
        """
        Generates a personalized study plan for all courses.
        Pass the courses list from get_full_student_profile as a JSON string.
        Returns the complete formatted study plan as a markdown string.
        """
        import json as _j
        courses = _j.loads(courses_json)

        GRADE_POINTS_MAP = {
            "A":4.0,"A-":3.67,"B+":3.33,"B":3.0,"B-":2.67,
            "C+":2.33,"C":2.0,"C-":1.67,"D+":1.33,"D":1.0,"F":0.0
        }
        DAILY_HOURS = {
            "F":5.0,"D":4.5,"D+":4.0,"C-":3.5,"C":3.0,
            "C+":2.8,"B-":2.5,"B":2.2,"B+":2.0,"A-":1.5,"A":1.0
        }
        CH_MULT = {1: 0.7, 2: 1.0, 3: 1.3}

        sorted_courses = sorted(
            courses,
            key=lambda c: c["credit_hours"] * (4.0 - GRADE_POINTS_MAP.get(c["predicted_grade"], 0)),
            reverse=True
        )

        lines = []
        lines.append("# 📚 Your Personalized Study Plan\n")
        lines.append("## 🎯 Priority Order (Most Urgent → Least Urgent)\n")
        for i, c in enumerate(sorted_courses, 1):
            g   = c["predicted_grade"]
            gap = round(4.0 - GRADE_POINTS_MAP.get(g, 0), 2)
            lines.append(f"{i}. **{c['name']}** ({c['credit_hours']} CH) — Predicted: {g} | GPA Gap to A: {gap}")

        lines.append("\n---\n")
        lines.append("## 📅 Daily Study Hours Allocation\n")
        lines.append("| Course | Credit Hours | Predicted Grade | Daily Hours Needed |")
        lines.append("|--------|-------------|-----------------|-------------------|")
        for c in sorted_courses:
            g    = c["predicted_grade"]
            base = DAILY_HOURS.get(g, 2.5)
            hrs  = round(base * CH_MULT.get(c["credit_hours"], 1.0), 1)
            lines.append(f"| {c['name']} | {c['credit_hours']} CH | {g} | {hrs} hrs/day |")

        lines.append("\n---\n")
        lines.append("## 🧠 Course-Specific Strategy\n")
        for c in sorted_courses:
            g          = c["predicted_grade"]
            pct        = c.get("percentage", 0)
            mid        = c.get("midterm", 0)
            quiz       = c.get("quiz_total", 0)
            assgn      = c.get("assignment_total", 0)
            pred_final = c.get("predicted_final", 0)
            gp         = GRADE_POINTS_MAP.get(g, 0)
            components = {
                f"Quizzes ({quiz}/10)":       quiz / 10 if quiz else 0,
                f"Assignments ({assgn}/20)":  assgn / 20 if assgn else 0,
                f"Midterm ({mid}/20)":        mid / 20 if mid else 0,
            }
            weakest = min(components, key=components.get)
            lines.append(f"### 📌 {c['name']} — Grade: {g} → Target: A")
            lines.append(f"- **Sessional**: Quiz {quiz}/10 | Assignment {assgn}/20 | Midterm {mid}/20")
            lines.append(f"- **Predicted Final Exam**: {pred_final}/50")
            lines.append(f"- **Predicted Total**: {pct}%")
            lines.append(f"- **Weakest Area**: {weakest} ← prioritise this")
            if gp < 2.0:
                lines.append("- **⚠️ Action**: Critical — revisit fundamentals from week 1. Attempt every past paper.")
            elif gp < 3.0:
                lines.append("- **Action**: Consistent daily practice needed. Solve past papers under timed conditions.")
            elif gp < 3.67:
                lines.append("- **Action**: Small gap to A. Focus on your weakest area and do 2 full mock papers.")
            else:
                lines.append("- **Action**: Very close to A. One focused revision of weak topics will push you over.")
            if gp < 2.0:
                yt_query = f"{c['name']} basics for beginners"
            elif gp < 3.0:
                yt_query = f"{c['name']} problem solving tutorial"
            elif gp < 3.67:
                yt_query = f"{c['name']} advanced exam tips"
            else:
                yt_query = f"{c['name']} exam preparation tutorial"
            yt_url = "https://www.youtube.com/results?search_query=" + yt_query.replace(" ", "+")
            lines.append(f"- 📺 **YouTube**: [{yt_query}]({yt_url})")
            lines.append("")

        lines.append("---")
        lines.append("\n💬 **Tell me which specific topic you are struggling with** in any course above and I will give you a targeted YouTube link for that exact topic.")
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────

    return [
        get_course_data,
        get_performance_data,
        get_course_analysis,
        compute_final_result,
        get_full_student_profile,
        compute_course_priority,
        compute_gpa,
        generate_study_plan,     # ← deterministic plan tool
    ]


# =========================================================
# AGENT SETUP
# =========================================================

def build_agents(student_id: int, db):

    tools = build_tools(student_id, db)

    # ── Notes Agent tools (standalone — do not need DB or student_id) ─────────
    @function_tool
    async def ask_notes(question: str) -> str:
        """
        Answer any question about the currently uploaded lecture file.
        Works for PDF, PowerPoint, Word, or image files.
        Retrieves the most relevant pages and answers using GPT-4o vision.

        Examples:
          - "Explain slide 3 in simple words"
          - "What is the main topic of this document?"
          - "Summarize page 5"
          - "What formulas are mentioned?"
          - "What topics might appear in the final exam?"
        """
        return await _answer_notes_question_async(question)

    @function_tool
    async def summarize_notes() -> str:
        """
        Summarize the entire uploaded lecture file — all pages/slides.
        Returns main topics, key concepts, and important points.
        """
        return await _answer_notes_question_async(
            "Please summarize the entire document. Give me the main topics, "
            "key concepts, and anything important I should know for my exam."
        )

    @function_tool
    async def get_exam_topics() -> str:
        """
        Identify topics from the uploaded file that are most likely
        to appear in a university final exam.
        """
        return await _answer_notes_question_async(
            "Based on this material, what topics are most likely to appear "
            "in a university final exam? List them with brief explanations."
        )

    @function_tool
    async def check_notes_status() -> str:
        """Returns what file is currently uploaded, or asks the student to upload one."""
        if notes_file_loaded():
            return get_notes_summary()
        return "No file is currently uploaded."

    notes_tools = [ask_notes, summarize_notes, get_exam_topics, check_notes_status]

    # ── Notes Agent ────────────────────────────────────────────────────────────
    notes_agent = Agent(
        name="Notes Agent",
        model=notes_model,          # GPT-4o — required for vision support
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
        tools=notes_tools,
    )
    # ──────────────────────────────────────────────────────────────────────────

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
        You are the Academic Prediction Agent for Bahria University Karachi.

        ═══════════════════════════════════════════════
        STEP 1 — DECIDE: ALL COURSES or ONE COURSE?
        ═══════════════════════════════════════════════

        ALL COURSES (user says "all courses", "all subjects", "everything"):
          → Call get_full_student_profile ONCE
          → It returns exact marks + predicted grade for every course
          → Present every course using the output format below
          → DO NOT call get_course_data separately

        ONE COURSE (user names a specific course):
          → Call get_course_data for that course
          → Call compute_final_result with the exact values returned by the tool
          → Present using the output format below

        ═══════════════════════════════════════════════
        CRITICAL — USE EXACT MARKS FROM TOOL OUTPUT
        ═══════════════════════════════════════════════
        NEVER round, estimate, or paraphrase the marks.
        If the tool returns quiz_total=8.2, you write 8.2 — not 8 or "approximately 8".
        If the tool returns assignment_total=15.7, you write 15.7 — not 16 or 15.5.
        Copy numbers EXACTLY as returned by the tool.

        ═══════════════════════════════════════════════
        OUTPUT FORMAT (repeat for each course):
        ═══════════════════════════════════════════════

        📊 **[Course Name]**
        • Quiz Total       : [exact value from tool]/10
        • Assignment Total : [exact value from tool]/20
        • Midterm          : [exact value from tool]/20
        • Sessional Total  : [quiz+assignment+midterm]/50

        🔮 **Predicted Final Exam: [value]/50**

        🧮 **How this was calculated:**
        The predicted final exam score uses this weighted formula:
          Predicted Final = (Midterm/20 × 0.60  +  Quiz/10 × 0.20  +  Assignment/20 × 0.20) × 50
        Midterm carries 60% of the weight because it is the strongest predictor of final exam performance.
        Example with your marks: ([mid]/20 × 0.60 + [quiz]/10 × 0.20 + [assgn]/20 × 0.20) × 50 = [predicted_final]/50

        🏁 **Final Result:**
        • Total Marks : [sessional + predicted final]/100
        • Percentage  : [total]%
        • Grade       : [grade]

        ═══════════════════════════════════════════════
        STRICT RULES:
        ═══════════════════════════════════════════════
        - Copy ALL numbers EXACTLY from tool output — no rounding, no estimating
        - NEVER compute grades manually — always use compute_final_result tool
        - NEVER ask the student for their marks
        - NEVER skip tool calls
        """,
        handoff_description="Specialist agent for academic predictions and final exam forecasting",
        tools=tools
    )

    planner_agent = Agent(
        name="Planner Agent",
        model=planner_ft_model,
        instructions="""
        You are the Academic Planning Agent.

        ═══════════════════════════════════════════════
        WORKFLOW — FOLLOW EXACTLY, NO EXCEPTIONS
        ═══════════════════════════════════════════════

        STEP 1 → Call get_full_student_profile
                 Returns all courses with exact marks and predicted grades.
                 DO NOT ask the student for any information.

        STEP 2 → Call generate_study_plan with the courses list from Step 1
                 This tool generates the complete plan — priority order,
                 daily hours, strategies, timetable, YouTube tips.
                 DO NOT write your own plan. DO NOT modify the tool output.

        STEP 3 → Present the output of generate_study_plan EXACTLY as returned.
                 Add only a single short sentence at the end offering help
                 with specific weak topics.

        ═══════════════════════════════════════════════
        STRICT RULES:
        ═══════════════════════════════════════════════
        - NEVER write a study plan yourself — always use generate_study_plan tool
        - NEVER skip get_full_student_profile
        - NEVER ask the student for grades or marks
        - NEVER modify numbers from tool output
        - NEVER produce generic advice like "review lecture notes" or "group study"
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
        5. NEVER assume what the student wants. If unclear, present the four options clearly.
        
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
        handoffs=[lms_agent, predictive_agent, planner_agent, gpa_agent, notes_agent]
    )

    return triage_agent