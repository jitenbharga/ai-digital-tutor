"""
Certificate generator for mastery milestones.
Produces a celebratory PDF certificate when a student masters a topic.
"""
import uuid
from datetime import datetime, timezone
from io import BytesIO
from core.capabilities import HAS_REPORTLAB

if HAS_REPORTLAB:
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.units import cm, mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.graphics.shapes import Drawing, Rect, String, Line

MASTERY_THRESHOLD = 0.8  # topic mastery >= this triggers a certificate

# Milestone tiers
MILESTONES = [
    {"threshold": 0.8, "title": "Proficiency", "color": "#2563eb"},
    {"threshold": 0.9, "title": "Excellence", "color": "#7c3aed"},
    {"threshold": 0.95, "title": "Mastery", "color": "#d97706"},
]


def get_milestone_tier(mastery: float) -> dict | None:
    """Return the highest milestone tier achieved."""
    achieved = None
    for m in MILESTONES:
        if mastery >= m["threshold"]:
            achieved = m
    return achieved


def create_certificate_record(
    student_id: str,
    topic: str,
    mastery: float,
    display_name: str = "",
) -> dict:
    """Create a certificate document for MongoDB."""
    tier = get_milestone_tier(mastery)
    return {
        "cert_id": str(uuid.uuid4())[:12],
        "student_id": student_id,
        "topic": topic,
        "mastery": round(mastery, 3),
        "tier": tier["title"] if tier else "Proficiency",
        "display_name": display_name or student_id,
        "awarded_at": datetime.now(timezone.utc).isoformat(),
        "timestamp": datetime.now(timezone.utc).timestamp(),
    }


async def check_and_award_certificates(
    student_id: str,
    topic: str,
    mastery: float,
    display_name: str = "",
) -> dict | None:
    """Check if mastery crossed threshold and award certificate if not already earned."""
    from database import certificates_collection

    if mastery < MASTERY_THRESHOLD:
        return None

    tier = get_milestone_tier(mastery)
    if not tier:
        return None

    # Check if this tier was already awarded for this topic
    existing = await certificates_collection.find_one({
        "student_id": student_id,
        "topic": topic,
        "tier": tier["title"],
    })
    if existing:
        return None  # Already earned

    cert = create_certificate_record(student_id, topic, mastery, display_name)
    await certificates_collection.insert_one(cert)

    return cert


def build_certificate_pdf(
    student_name: str,
    topic: str,
    tier: str,
    mastery: float,
    awarded_at: str,
) -> bytes:
    """Generate a celebratory PDF certificate."""
    if not HAS_REPORTLAB:
        return _text_fallback(student_name, topic, tier, mastery, awarded_at)

    buf = BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(
        buf, pagesize=page,
        leftMargin=3 * cm, rightMargin=3 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )

    # Colors
    tier_colors = {
        "Proficiency": HexColor("#2563eb"),
        "Excellence": HexColor("#7c3aed"),
        "Mastery": HexColor("#d97706"),
    }
    accent = tier_colors.get(tier, HexColor("#2563eb"))
    gold = HexColor("#d97706")

    # Styles
    title_style = ParagraphStyle(
        "CertTitle", fontSize=36, alignment=TA_CENTER,
        textColor=accent, fontName="Helvetica-Bold",
        spaceAfter=8,
    )
    subtitle_style = ParagraphStyle(
        "CertSub", fontSize=14, alignment=TA_CENTER,
        textColor=HexColor("#64748b"), fontName="Helvetica",
        spaceAfter=20,
    )
    name_style = ParagraphStyle(
        "CertName", fontSize=28, alignment=TA_CENTER,
        textColor=HexColor("#1e293b"), fontName="Helvetica-Bold",
        spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "CertBody", fontSize=16, alignment=TA_CENTER,
        textColor=HexColor("#475569"), fontName="Helvetica",
        spaceAfter=8,
    )
    topic_style = ParagraphStyle(
        "CertTopic", fontSize=22, alignment=TA_CENTER,
        textColor=accent, fontName="Helvetica-Bold",
        spaceAfter=16,
    )
    footer_style = ParagraphStyle(
        "CertFooter", fontSize=10, alignment=TA_CENTER,
        textColor=HexColor("#94a3b8"), fontName="Helvetica",
    )

    elements = []

    # Decorative border
    w, h = page
    d = Drawing(w - 6 * cm, 4)
    d.add(Rect(0, 0, w - 6 * cm, 3, fillColor=accent, strokeColor=None))
    elements.append(d)
    elements.append(Spacer(1, 20))

    # Star decoration
    elements.append(Paragraph("&#9733; &#9733; &#9733;", ParagraphStyle(
        "Stars", fontSize=24, alignment=TA_CENTER, textColor=gold,
    )))
    elements.append(Spacer(1, 8))

    # Title
    elements.append(Paragraph("Certificate of Achievement", title_style))
    elements.append(Paragraph(f"{tier} Level", subtitle_style))

    # Divider
    d2 = Drawing(200, 2)
    d2.add(Rect(0, 0, 200, 1, fillColor=HexColor("#e2e8f0"), strokeColor=None))
    elements.append(d2)
    elements.append(Spacer(1, 16))

    # Recipient
    elements.append(Paragraph("This certifies that", body_style))
    elements.append(Paragraph(student_name, name_style))

    # Achievement
    elements.append(Paragraph("has demonstrated proficiency in", body_style))
    elements.append(Paragraph(topic, topic_style))

    # Score
    pct = round(mastery * 100)
    elements.append(Paragraph(
        f"Achieving <b>{pct}%</b> mastery",
        ParagraphStyle("Score", fontSize=14, alignment=TA_CENTER,
                       textColor=HexColor("#22c55e"), fontName="Helvetica"),
    ))
    elements.append(Spacer(1, 24))

    # Bottom border
    d3 = Drawing(w - 6 * cm, 4)
    d3.add(Rect(0, 0, w - 6 * cm, 3, fillColor=accent, strokeColor=None))
    elements.append(d3)
    elements.append(Spacer(1, 12))

    # Date + footer
    date_str = awarded_at[:10] if awarded_at else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    elements.append(Paragraph(f"Awarded on {date_str}", footer_style))
    elements.append(Paragraph("AI Digital Tutor", footer_style))

    doc.build(elements)
    return buf.getvalue()


def _text_fallback(student_name, topic, tier, mastery, awarded_at):
    """Plain text fallback when reportlab is unavailable."""
    text = f"""
===================================
  CERTIFICATE OF ACHIEVEMENT
  {tier} Level
===================================

  This certifies that

  {student_name}

  has demonstrated proficiency in

  {topic}

  Achieving {round(mastery * 100)}% mastery

  Awarded: {awarded_at[:10] if awarded_at else 'N/A'}
  AI Digital Tutor
===================================
"""
    return text.strip().encode("utf-8")
