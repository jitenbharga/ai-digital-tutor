"""
N12: Personal Notebook — CRUD for student highlights + notes.
Extracted from serve.py.
"""

import time
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import StreamingResponse

from adaptive.dependencies import require_role
from adaptive.database import db, student_states_collection
from adaptive.utils.mongo_safe import safe_topic_filter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notebook"])

_notes_col = db["notes"]


@router.get("/me/notebook")
async def get_notebook(
    topic: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_role("student")),
):
    """Get personal notebook notes, optionally filtered by topic."""
    student_id = current_user["username"]
    query = {"student_id": student_id}
    if topic:
        query["topic"] = safe_topic_filter(topic)

    cursor = _notes_col.find(
        query, {"_id": 0, "student_id": 0}
    ).sort("created_at", -1).limit(limit)

    notes = []
    topics_seen = set()
    async for doc in cursor:
        notes.append({
            "note_id": doc.get("note_id", ""),
            "node_id": doc.get("node_id", ""),
            "topic": doc.get("topic", ""),
            "selected_text": doc.get("selected_text", ""),
            "user_note": doc.get("user_note", ""),
            "source_context": doc.get("source_context", ""),
            "related_topics": doc.get("related_topics", []),
            "created_at": doc.get("created_at", 0),
            "updated_at": doc.get("updated_at", 0),
        })
        if doc.get("topic"):
            topics_seen.add(doc["topic"])

    total = await _notes_col.count_documents({"student_id": student_id})

    return {
        "notes": notes,
        "total": total,
        "topics": sorted(topics_seen),
    }


@router.get("/me/notebook/export.pdf")
async def export_notebook_pdf(
    current_user: dict = Depends(require_role("student")),
):
    """Export the student's notebook as a PDF, grouped by topic."""
    import io as _io_nb
    from core.report_builder import build_notebook_pdf

    student_id = current_user["username"]
    cursor = _notes_col.find({"student_id": student_id}, {"_id": 0}).sort("created_at", -1)
    notes = []
    async for doc in cursor:
        notes.append({
            "topic": doc.get("topic", ""),
            "subject": doc.get("subject", ""),
            "selected_text": doc.get("selected_text", ""),
            "user_note": doc.get("user_note", ""),
            "related_topics": doc.get("related_topics", []),
            "created_at": doc.get("created_at", 0),
        })

    pdf_bytes = build_notebook_pdf(student_id, notes)
    return StreamingResponse(
        _io_nb.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="my_notebook.pdf"'},
    )


@router.post("/me/notebook")
async def save_note(
    body: dict = Body(...),
    current_user: dict = Depends(require_role("student")),
):
    """Save a highlight to personal notebook."""
    student_id = current_user["username"]

    selected_text = body.get("selected_text", "").strip()
    if not selected_text or len(selected_text) > 5000:
        raise HTTPException(400, "selected_text must be 1-5000 characters")

    topic = body.get("topic", "")
    user_note = body.get("user_note", "")[:2000]
    source_context = body.get("source_context", "")[:2000]

    # Get related topics from knowledge graph if available
    related_topics = []
    if topic:
        try:
            state = await student_states_collection.find_one(
                {"student_id": student_id}, {"_id": 0, "concepts": 1}
            )
            if state and state.get("concepts"):
                concepts = state["concepts"]
                topic_lower = topic.lower()
                for key, data in concepts.items():
                    if key.lower() != topic_lower and isinstance(data, dict):
                        mastery = data.get("concept_mastery", data.get("knowledge", 0))
                        if mastery > 0.1:
                            related_topics.append(key)
                        if len(related_topics) >= 5:
                            break
        except Exception:
            pass

    note_id = "note_{}".format(uuid.uuid4().hex[:12])
    now = time.time()

    doc = {
        "note_id": note_id,
        "student_id": student_id,
        "node_id": body.get("node_id", ""),
        "topic": topic,
        "selected_text": selected_text,
        "user_note": user_note,
        "source_context": source_context,
        "related_topics": related_topics,
        "created_at": now,
        "updated_at": now,
    }
    await _notes_col.insert_one(doc)

    return {
        "note_id": note_id,
        "related_topics": related_topics,
    }


@router.put("/me/notebook/{note_id}")
async def update_note(
    note_id: str,
    body: dict = Body(...),
    current_user: dict = Depends(require_role("student")),
):
    """Update a note's user_note text."""
    student_id = current_user["username"]
    user_note = body.get("user_note", "")[:2000]

    result = await _notes_col.update_one(
        {"student_id": student_id, "note_id": note_id},
        {"$set": {"user_note": user_note, "updated_at": time.time()}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Note not found")

    return {"ok": True, "note_id": note_id}


@router.delete("/me/notebook/{note_id}")
async def delete_note(
    note_id: str,
    current_user: dict = Depends(require_role("student")),
):
    """Delete a notebook entry."""
    student_id = current_user["username"]

    result = await _notes_col.delete_one(
        {"student_id": student_id, "note_id": note_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(404, "Note not found")
    return {"ok": True, "note_id": note_id}
