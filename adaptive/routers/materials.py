"""
S1: My Materials — upload textbook chapters, ask & quiz from them.
Extracted from api/extras.py.
"""

import time
import logging

from fastapi import (
    APIRouter, Depends, HTTPException, Query, Body, Request, UploadFile, File,
)

from adaptive.dependencies import require_role
from adaptive.rate_limit import limiter, check_llm_budget, user_key
from adaptive.utils.upload import read_capped, safe_basename

logger = logging.getLogger(__name__)

router = APIRouter(tags=["materials"])

MAX_MATERIALS = 10
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


async def get_material_or_404(student_id: str, material_id: str) -> dict:
    """Fetch a student's material document or raise 404 (Improvement #2 —
    shared by the ask/quiz paths so the fetch logic can't drift)."""
    from database import user_materials_collection
    doc = await user_materials_collection.find_one({
        "student_id": student_id, "material_id": material_id,
    })
    if not doc:
        raise HTTPException(404, "Material not found")
    return doc


@router.post("/me/materials")
@limiter.limit("5/minute", key_func=user_key)
async def upload_material(
    request: Request,
    title: str = Query(""),
    current_user: dict = Depends(require_role("student")),
    file: UploadFile = File(None),
):
    """Upload a PDF/TXT/MD chapter. Extracts text, chunks, stores."""
    import uuid
    from core.user_materials import extract_text, chunk_text, build_idf
    from database import user_materials_collection

    student_id = current_user["username"]

    # Check material count limit
    count = await user_materials_collection.count_documents({"student_id": student_id})
    if count >= MAX_MATERIALS:
        raise HTTPException(400, f"Maximum {MAX_MATERIALS} materials allowed. Delete one first.")

    if file is None:
        raise HTTPException(400, "file is required (multipart upload)")

    file_bytes = await read_capped(file, MAX_FILE_SIZE)
    if len(file_bytes) == 0:
        raise HTTPException(400, "Empty file uploaded")

    filename = safe_basename(file.filename)
    material_title = title.strip() or filename.rsplit(".", 1)[0]

    try:
        text = extract_text(file_bytes, filename)
    except ValueError as e:
        raise HTTPException(422, str(e))

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(422, "No usable text could be extracted from this file.")

    idf = build_idf(chunks)
    material_id = str(uuid.uuid4())[:12]

    doc = {
        "material_id": material_id,
        "student_id": student_id,
        "title": material_title[:200],
        "filename": filename[:200],
        "chunk_count": len(chunks),
        "char_count": sum(len(c["text"]) for c in chunks),
        "chunks": chunks,
        "idf": idf,
        "created_at": time.time(),
    }
    await user_materials_collection.insert_one(doc)

    return {
        "material_id": material_id,
        "title": material_title,
        "chunk_count": len(chunks),
        "char_count": doc["char_count"],
    }


@router.post("/me/materials/upload")
@limiter.limit("5/minute", key_func=user_key)
async def upload_material_multipart(
    request: Request,
    file: UploadFile = File(...),
    title: str = Query(""),
    current_user: dict = Depends(require_role("student")),
):
    """Multipart upload endpoint (alias with proper signature)."""
    import uuid
    from core.user_materials import extract_text, chunk_text, build_idf
    from database import user_materials_collection

    student_id = current_user["username"]
    count = await user_materials_collection.count_documents({"student_id": student_id})
    if count >= MAX_MATERIALS:
        raise HTTPException(400, f"Maximum {MAX_MATERIALS} materials allowed.")

    file_bytes = await read_capped(file, MAX_FILE_SIZE)
    if not file_bytes:
        raise HTTPException(400, "Empty file")

    filename = safe_basename(file.filename)
    material_title = title.strip() or filename.rsplit(".", 1)[0]

    try:
        text = extract_text(file_bytes, filename)
    except ValueError as e:
        raise HTTPException(422, str(e))

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(422, "No usable text extracted.")

    idf = build_idf(chunks)
    material_id = str(uuid.uuid4())[:12]

    doc = {
        "material_id": material_id,
        "student_id": student_id,
        "title": material_title[:200],
        "filename": filename[:200],
        "chunk_count": len(chunks),
        "char_count": sum(len(c["text"]) for c in chunks),
        "chunks": chunks,
        "idf": idf,
        "created_at": time.time(),
    }
    await user_materials_collection.insert_one(doc)
    return {
        "material_id": material_id,
        "title": material_title,
        "chunk_count": len(chunks),
        "char_count": doc["char_count"],
    }


@router.get("/me/materials")
@limiter.limit("60/minute", key_func=user_key)
async def list_materials(
    request: Request,
    current_user: dict = Depends(require_role("student")),
):
    """List uploaded materials (without chunk data)."""
    from database import user_materials_collection

    items = []
    async for doc in user_materials_collection.find(
        {"student_id": current_user["username"]},
        {"_id": 0, "chunks": 0, "idf": 0},
    ).sort("created_at", -1):
        items.append(doc)
    return {"materials": items}


@router.delete("/me/materials/{material_id}")
async def delete_material(
    material_id: str,
    current_user: dict = Depends(require_role("student")),
):
    from database import user_materials_collection

    res = await user_materials_collection.delete_one({
        "student_id": current_user["username"],
        "material_id": material_id,
    })
    if res.deleted_count == 0:
        raise HTTPException(404, "Material not found")
    return {"ok": True}


@router.post("/me/materials/{material_id}/ask")
@limiter.limit("10/minute", key_func=user_key)
async def ask_material(
    request: Request,
    material_id: str,
    body: dict = Body(...),
    current_user: dict = Depends(require_role("student")),
    _budget: dict = Depends(check_llm_budget),
):
    """Socratic Q&A grounded in a specific uploaded chapter."""
    from core.llm_utils import call_llm
    from core.llm_registry import build_models
    from core.user_materials import retrieve_chunks, format_material_grounding
    from utils.prompt_safety import wrap_student_text, looks_like_injection

    student_id = current_user["username"]
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "question is required")
    if len(question) > 2000:
        raise HTTPException(400, "question too long (max 2000 chars)")

    if looks_like_injection(question):
        logger.warning("possible injection in material-ask from %s", student_id)

    doc = await get_material_or_404(student_id, material_id)

    chunks = doc.get("chunks", [])
    idf = doc.get("idf", {})
    relevant = retrieve_chunks(question, chunks, idf, top_k=8)
    grounding = format_material_grounding(relevant, doc.get("title", "your chapter"))

    safe_q = wrap_student_text(question, "student_question")

    prompt = f"""{grounding}

The student asks:
{safe_q}

You are a Socratic tutor. Answer using ONLY the reference material above.
- Use the material's terminology and notation.
- If the answer is not in the material, say "This isn't covered in your chapter."
- Guide understanding — don't just state facts. Ask a follow-up question.
- Use LaTeX for math (wrap in $ or $$).

Return JSON: {{"answer": "...", "covered": true/false, "follow_up": "..."}}"""

    result = await call_llm(
        build_models(), prompt, required_key="answer",
        engine_name="material_ask", prompt_version="v1",
    )
    if not result:
        result = {"answer": "I couldn't process this question — try rephrasing.", "covered": True, "follow_up": ""}
    return result


@router.post("/me/materials/{material_id}/quiz")
@limiter.limit("10/minute", key_func=user_key)
async def quiz_from_material(
    request: Request,
    material_id: str,
    body: dict = Body(default={}),
    current_user: dict = Depends(require_role("student")),
    _budget: dict = Depends(check_llm_budget),
):
    """Generate a quiz from uploaded chapter content. Uses the normal quiz pipeline."""
    import uuid as _uuid_mat
    import random
    from core.llm_utils import call_llm
    from core.llm_registry import build_models
    from core.user_materials import format_material_grounding

    student_id = current_user["username"]
    num_questions = min(max(int(body.get("num_questions") or 10), 3), 15)

    doc = await get_material_or_404(student_id, material_id)

    chunks = doc.get("chunks", [])
    if not chunks:
        raise HTTPException(422, "Material has no content")

    # Sample random chunks to get diverse questions
    sample_size = min(len(chunks), 12)
    sampled = random.sample(chunks, sample_size)
    grounding = format_material_grounding(sampled, doc.get("title", "chapter"))

    prompt = f"""{grounding}

Generate exactly {num_questions} multiple-choice questions STRICTLY from the reference material above.

Rules:
- Every question and every answer option must come from the material. Do NOT use outside knowledge.
- Each question has exactly 4 options (A, B, C, D) with one correct answer.
- Mix difficulty: some recall, some understanding, some application.
- Cover different sections of the material.

Return JSON: {{"questions": [
  {{"id": "q1", "question": "...", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct": "B", "explanation": "...", "concept": "...", "difficulty": "easy|medium|hard"}}
]}}"""

    result = await call_llm(
        build_models(), prompt, required_key="questions",
        engine_name="material_quiz", prompt_version="v1",
    )
    if not result or not result.get("questions"):
        raise HTTPException(502, "Failed to generate quiz from this material")

    questions = result["questions"]
    for q in questions:
        q["type"] = "mcq"
        q["hints_used"] = 0
        if "id" not in q:
            q["id"] = str(_uuid_mat.uuid4())[:8]

    # Register as active quiz (reuses existing pipeline)
    quiz_id = str(_uuid_mat.uuid4())[:8]
    from serve import _save_active_quiz
    await _save_active_quiz(quiz_id, {
        "questions": questions,
        "student_id": student_id,
        "topic": doc.get("title", "Uploaded Material"),
        "source": "material",
        "material_id": material_id,
    })

    public = [{
        "id": q["id"], "type": "mcq", "question": q["question"],
        "options": q.get("options", {}), "multiple": q.get("multiple", False),
        "concept": q.get("concept", ""), "difficulty": q.get("difficulty", "medium"),
    } for q in questions]

    return {
        "quiz_id": quiz_id,
        "quiz_title": f"Quiz: {doc.get('title', 'Your Chapter')}",
        "questions": public,
        "total": len(public),
    }
