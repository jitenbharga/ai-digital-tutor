"""
PDF progress report generator using reportlab.
Produces a clean, single-page (or multi-page) report with:
  - Header with student info and date
  - Accuracy summary
  - Per-topic mastery table/bars
  - Weak links
  - Recommended next steps from study plan
"""
from datetime import datetime, timezone
from io import BytesIO

from core.capabilities import HAS_REPORTLAB

if HAS_REPORTLAB:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm, cm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.graphics.shapes import Drawing, Rect, String
    from reportlab.graphics.charts.barcharts import HorizontalBarChart


# Brand colors
BRAND_BLUE = HexColor("#2563eb") if HAS_REPORTLAB else None
BRAND_GREEN = HexColor("#22c55e") if HAS_REPORTLAB else None
BRAND_AMBER = HexColor("#f59e0b") if HAS_REPORTLAB else None
BRAND_RED = HexColor("#ef4444") if HAS_REPORTLAB else None
BRAND_GRAY = HexColor("#64748b") if HAS_REPORTLAB else None
LIGHT_GRAY = HexColor("#f1f5f9") if HAS_REPORTLAB else None


def build_report_pdf(
    student_id: str,
    total_questions: int,
    correct_answers: int,
    accuracy: float,
    topics: dict,
    kg_data: dict | None = None,
    plan_data: dict | None = None,
) -> bytes:
    """Build and return PDF bytes."""
    if not HAS_REPORTLAB:
        # Fallback: return a minimal text-based PDF
        return _build_text_fallback(student_id, total_questions, accuracy, topics)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"],
        fontSize=20, textColor=BRAND_BLUE, spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "ReportHeading", parent=styles["Heading2"],
        fontSize=14, textColor=BRAND_BLUE, spaceBefore=16, spaceAfter=8,
    )
    body_style = styles["Normal"]
    small_style = ParagraphStyle(
        "Small", parent=body_style, fontSize=9, textColor=BRAND_GRAY,
    )

    elements = []

    # ── Header ──
    elements.append(Paragraph("Student Progress Report", title_style))
    elements.append(Paragraph(
        f"Student: <b>{student_id}</b> &nbsp;|&nbsp; "
        f"Generated: {datetime.now(timezone.utc).strftime('%B %d, %Y %H:%M')}",
        small_style
    ))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1, color=BRAND_BLUE))
    elements.append(Spacer(1, 12))

    # ── Summary cards ──
    elements.append(Paragraph("Performance Summary", heading_style))
    summary_data = [
        ["Total Questions", "Correct Answers", "Accuracy", "Topics Studied"],
        [str(total_questions), str(correct_answers), f"{accuracy}%", str(len(topics))],
    ]
    summary_table = Table(summary_data, colWidths=[120, 120, 100, 120])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, 1), LIGHT_GRAY),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, BRAND_GRAY),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 16))

    # ── Topic Mastery ──
    if topics:
        elements.append(Paragraph("Topic Mastery", heading_style))
        topic_rows = [["Topic", "Mastery", "Level"]]
        for topic, val in sorted(topics.items(), key=lambda x: -x[1] if isinstance(x[1], (int, float)) else 0):
            mastery = val if isinstance(val, (int, float)) else 0
            pct = f"{mastery * 100:.0f}%" if isinstance(mastery, float) and mastery <= 1 else f"{mastery}%"
            level = "Strong" if (mastery if mastery <= 1 else mastery / 100) > 0.7 else \
                    "Medium" if (mastery if mastery <= 1 else mastery / 100) > 0.4 else "Weak"
            topic_rows.append([topic, pct, level])

        topic_table = Table(topic_rows, colWidths=[200, 100, 100])
        topic_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#ffffff"), LIGHT_GRAY]),
            ("GRID", (0, 0), (-1, -1), 0.5, BRAND_GRAY),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(topic_table)
        elements.append(Spacer(1, 16))

    # ── Weak Links ──
    if kg_data and kg_data.get("weak_links"):
        elements.append(Paragraph("Areas Needing Attention", heading_style))
        for wl in kg_data["weak_links"]:
            elements.append(Paragraph(f"• <b>{wl}</b> — needs more practice", body_style))
        if kg_data.get("suggested_focus"):
            elements.append(Spacer(1, 6))
            elements.append(Paragraph(
                f"<i>Recommended focus: {kg_data['suggested_focus']}</i>",
                ParagraphStyle("Focus", parent=body_style, textColor=BRAND_AMBER)
            ))
        elements.append(Spacer(1, 16))

    # ── Study Plan ──
    if plan_data and plan_data.get("plan"):
        elements.append(Paragraph("Recommended Next Steps", heading_style))
        plan_rows = [["Topic", "Duration", "Type", "Reason"]]
        plan_list = plan_data["plan"]
        if isinstance(plan_list, list):
            for item in plan_list:
                if isinstance(item, dict):
                    plan_rows.append([
                        item.get("topic", ""),
                        f"{item.get('duration_min', '')} min",
                        item.get("type", ""),
                        item.get("reason", ""),
                    ])

        if len(plan_rows) > 1:
            plan_table = Table(plan_rows, colWidths=[120, 70, 70, 200])
            plan_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#ffffff"), LIGHT_GRAY]),
                ("GRID", (0, 0), (-1, -1), 0.5, BRAND_GRAY),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            elements.append(plan_table)

        if plan_data.get("motivational_note"):
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(
                f"<i>{plan_data['motivational_note']}</i>",
                ParagraphStyle("Motive", parent=body_style, textColor=BRAND_GREEN)
            ))

    # ── Footer ──
    elements.append(Spacer(1, 24))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=BRAND_GRAY))
    elements.append(Paragraph(
        "Generated by AI Digital Tutor • This report is auto-generated from your learning data",
        ParagraphStyle("Footer", parent=small_style, alignment=TA_CENTER),
    ))

    doc.build(elements)
    return buf.getvalue()


def build_notebook_pdf(student_id: str, notes: list) -> bytes:
    """Build a PDF of the student's personal notebook, grouped by subject/topic."""
    if not HAS_REPORTLAB:
        lines = [f"Notebook for {student_id}", ""]
        for n in notes:
            lines.append(f"[{n.get('topic', '')}] {n.get('selected_text', '')}")
            if n.get("user_note"):
                lines.append(f"  Note: {n['user_note']}")
        return "\n".join(lines).encode("utf-8")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("NbTitle", parent=styles["Title"], fontSize=20, textColor=BRAND_BLUE, spaceAfter=4)
    heading_style = ParagraphStyle("NbHeading", parent=styles["Heading2"], fontSize=13, textColor=BRAND_BLUE, spaceBefore=14, spaceAfter=6)
    body_style = styles["Normal"]
    small_style = ParagraphStyle("NbSmall", parent=body_style, fontSize=9, textColor=BRAND_GRAY)
    quote_style = ParagraphStyle("NbQuote", parent=body_style, fontSize=10, leftIndent=10, textColor=HexColor("#0f172a"))
    note_style = ParagraphStyle("NbNote", parent=body_style, fontSize=10, leftIndent=10, textColor=BRAND_GRAY)

    elements = []
    elements.append(Paragraph("My Notebook", title_style))
    elements.append(Paragraph(
        f"{student_id} &nbsp;•&nbsp; Generated {datetime.now(timezone.utc).strftime('%B %d, %Y')} &nbsp;•&nbsp; {len(notes)} notes",
        small_style,
    ))
    elements.append(Spacer(1, 6))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=BRAND_GRAY))

    # Group by topic (fallback to subject / "General")
    grouped = {}
    for n in notes:
        key = n.get("topic") or n.get("subject") or "General"
        grouped.setdefault(key, []).append(n)

    def _esc(s):
        return (str(s or "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    for topic, items in grouped.items():
        elements.append(Paragraph(_esc(topic), heading_style))
        for n in items:
            elements.append(Paragraph(f"“{_esc(n.get('selected_text', ''))}”", quote_style))
            if n.get("user_note"):
                elements.append(Paragraph(f"<b>My note:</b> {_esc(n['user_note'])}", note_style))
            rel = n.get("related_topics") or []
            if rel:
                rel_txt = ", ".join(_esc(r) for r in rel)
                elements.append(Paragraph(f"<i>Related: {rel_txt}</i>", small_style))
            elements.append(Spacer(1, 8))

    elements.append(Spacer(1, 16))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=BRAND_GRAY))
    elements.append(Paragraph(
        "Generated by AI Digital Tutor • Your personal notebook",
        ParagraphStyle("NbFooter", parent=small_style, alignment=TA_CENTER),
    ))

    doc.build(elements)
    return buf.getvalue()


def build_progress_card_pdf(student_id: str, snapshot: dict) -> bytes:
    """C4: single-page shareable weekly progress card from the N7 snapshot."""
    topics = snapshot.get("topics_touched_this_week", 0)
    gain = round(snapshot.get("total_mastery_gain", 0.0) * 100)
    streak = snapshot.get("current_streak", 0)
    questions = snapshot.get("questions_this_week", 0)
    next_up = snapshot.get("next_up", "") or "Keep exploring"
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    if not HAS_REPORTLAB:
        return (
            f"My week on AI Tutor ({date_str})\n"
            f"Topics studied: {topics}\nMastery gained: +{gain}%\n"
            f"Questions: {questions}\nStreak: {streak} days\nNext up: {next_up}\n"
        ).encode("utf-8")

    # Compact landscape-ish card on A5
    from reportlab.lib.pagesizes import A5
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A5,
                            leftMargin=1.4 * cm, rightMargin=1.4 * cm,
                            topMargin=1.4 * cm, bottomMargin=1.4 * cm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("CardTitle", parent=styles["Title"], fontSize=20, textColor=BRAND_BLUE, spaceAfter=2)
    sub = ParagraphStyle("CardSub", parent=styles["Normal"], fontSize=9, textColor=BRAND_GRAY, spaceAfter=12)
    statnum = ParagraphStyle("StatNum", parent=styles["Title"], fontSize=22, alignment=TA_CENTER, textColor=BRAND_GREEN)
    statlbl = ParagraphStyle("StatLbl", parent=styles["Normal"], fontSize=8, alignment=TA_CENTER, textColor=BRAND_GRAY)
    foot = ParagraphStyle("Foot", parent=styles["Normal"], fontSize=9, textColor=BRAND_BLUE)

    def stat(num, lbl, color=BRAND_GREEN):
        s = ParagraphStyle("s", parent=statnum, textColor=color)
        return [Paragraph(str(num), s), Paragraph(lbl, statlbl)]

    elements = [
        Paragraph("My learning week", title),
        Paragraph(f"{student_id} &nbsp;•&nbsp; {date_str}", sub),
    ]
    grid = [[
        stat(topics, "Topics studied", BRAND_BLUE),
        stat(f"+{gain}%", "Mastery gained", BRAND_GREEN),
        stat(questions, "Questions", BRAND_AMBER),
        stat(f"{streak}🔥", "Day streak", BRAND_RED),
    ]]
    t = Table(grid, colWidths=[3.0 * cm] * 4)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
        ("BOX", (0, 0), (-1, -1), 0, LIGHT_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 4, HexColor("#ffffff")),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    elements += [t, Spacer(1, 16)]
    elements.append(Paragraph(f"<b>Next up:</b> {next_up}", styles["Normal"]))
    elements += [Spacer(1, 20), HRFlowable(width="100%", color=LIGHT_GRAY),
                 Spacer(1, 6), Paragraph("Made with AI Tutor", foot)]
    doc.build(elements)
    return buf.getvalue()


def build_cheatsheet_pdf(student_id: str, sheet: dict) -> bytes:
    """D2: one-page cheat sheet PDF — formulas, definitions, must-remember, your gotchas."""
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    if not HAS_REPORTLAB:
        lines = [sheet.get("title", "Cheat sheet"), ""]
        lines += ["FORMULAS:"] + [f"  • {x}" for x in sheet.get("key_formulas", [])]
        lines += ["", "MUST REMEMBER:"] + [f"  • {x}" for x in sheet.get("must_remember", [])]
        lines += ["", "YOUR GOTCHAS:"] + [f"  • {x}" for x in sheet.get("your_gotchas", [])]
        return "\n".join(lines).encode("utf-8")

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.6*cm, rightMargin=1.6*cm, topMargin=1.6*cm, bottomMargin=1.6*cm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("CsTitle", parent=styles["Title"], fontSize=18, textColor=BRAND_BLUE, spaceAfter=2)
    sub = ParagraphStyle("CsSub", parent=styles["Normal"], fontSize=8, textColor=BRAND_GRAY, spaceAfter=10)
    head = ParagraphStyle("CsHead", parent=styles["Heading2"], fontSize=12, textColor=BRAND_BLUE, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("CsBody", parent=styles["Normal"], fontSize=10, leading=14)
    gotcha = ParagraphStyle("CsGotcha", parent=body, textColor=HexColor("#b45309"))

    el = [Paragraph(sheet.get("title", "Cheat Sheet"), title),
          Paragraph(f"{student_id} &nbsp;•&nbsp; {date_str}", sub)]

    if sheet.get("key_formulas"):
        el.append(Paragraph("Key formulas", head))
        for f in sheet["key_formulas"]:
            el.append(Paragraph(f"• {f}", body))
    if sheet.get("key_definitions"):
        el.append(Paragraph("Definitions", head))
        for d in sheet["key_definitions"]:
            el.append(Paragraph(f"<b>{d.get('term','')}</b> — {d.get('definition','')}", body))
    if sheet.get("must_remember"):
        el.append(Paragraph("Must remember", head))
        for m in sheet["must_remember"]:
            el.append(Paragraph(f"• {m}", body))
    if sheet.get("your_gotchas"):
        el.append(Paragraph("Your personal gotchas", head))
        for g in sheet["your_gotchas"]:
            el.append(Paragraph(f"⚠ {g}", gotcha))
    if sheet.get("quick_examples"):
        el.append(Paragraph("Quick examples", head))
        for ex in sheet["quick_examples"]:
            el.append(Paragraph(ex, body))

    doc.build(el)
    return buf.getvalue()


def _build_text_fallback(student_id, total_questions, accuracy, topics):
    """Minimal fallback if reportlab is not installed."""
    lines = [
        f"Progress Report for {student_id}",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        "",
        f"Total Questions: {total_questions}",
        f"Accuracy: {accuracy}%",
        f"Topics: {len(topics)}",
        "",
    ]
    for t, v in topics.items():
        lines.append(f"  {t}: {v}")

    text = "\n".join(lines)
    # Return as a very basic PDF-like text (not a real PDF, but serves as placeholder)
    return text.encode("utf-8")
