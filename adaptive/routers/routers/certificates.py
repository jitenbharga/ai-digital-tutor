"""
Certificates — mastery certificate listing, PDF download, and award check.
Extracted from serve.py.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from dependencies import get_current_user
from runtime import tutor, _concept_mastery, _require_feature
from config.features import CERTIFICATES_ENABLED
from api.schemas import CertificateInfo, CertificatesListResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["certificates"])


# ── Extracted certificate routes (verbatim from serve.py) ──
@router.get("/me/certificates", response_model=CertificatesListResponse)
async def list_certificates(current_user: dict = Depends(get_current_user)):
    """List all earned certificates for the current student."""
    _require_feature(CERTIFICATES_ENABLED, "certificates")
    from database import certificates_collection
    username = current_user["username"]
    cursor = certificates_collection.find(
        {"student_id": username}, {"_id": 0}
    ).sort("timestamp", -1)
    certs = await cursor.to_list(length=100)
    return CertificatesListResponse(
        certificates=[CertificateInfo(**c) for c in certs],
        total=len(certs),
    )


@router.get("/me/certificates/{cert_id}/pdf")
async def download_certificate_pdf(
    cert_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Download a certificate as PDF."""
    _require_feature(CERTIFICATES_ENABLED, "certificates")
    import io
    from database import certificates_collection
    from core.certificate_builder import build_certificate_pdf

    username = current_user["username"]
    cert = await certificates_collection.find_one({
        "student_id": username, "cert_id": cert_id,
    })
    if not cert:
        raise HTTPException(404, "Certificate not found")

    pdf_bytes = build_certificate_pdf(
        student_name=cert.get("display_name", username),
        topic=cert["topic"],
        tier=cert["tier"],
        mastery=cert["mastery"],
        awarded_at=cert.get("awarded_at", ""),
    )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="certificate_{cert["topic"]}_{cert["tier"]}.pdf"'
        },
    )


@router.post("/me/check-certificates")
async def check_certificates_now(current_user: dict = Depends(get_current_user)):
    """Manually check and award any pending certificates based on current mastery."""
    _require_feature(CERTIFICATES_ENABLED, "certificates")
    from core.certificate_builder import check_and_award_certificates
    username = current_user["username"]

    student = await tutor.sessions.get_student(username)
    if not student or not student.concepts:
        return {"new_certificates": []}

    display_name = username
    # Try to get display name from user profile
    from database import users_collection
    user_doc = await users_collection.find_one({"username": username})
    if user_doc and user_doc.get("profile", {}).get("display_name"):
        display_name = user_doc["profile"]["display_name"]

    new_certs = []
    for topic, concept in student.concepts.items():
        mastery = _concept_mastery(concept)
        cert = await check_and_award_certificates(
            student_id=username, topic=topic,
            mastery=mastery, display_name=display_name,
        )
        if cert:
            new_certs.append(CertificateInfo(
                cert_id=cert["cert_id"], topic=cert["topic"],
                tier=cert["tier"], mastery=cert["mastery"],
                awarded_at=cert["awarded_at"],
                display_name=cert.get("display_name", ""),
            ))

    return {"new_certificates": [c.model_dump() for c in new_certs]}
