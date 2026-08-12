"""
Emailer — HTTPS REST API (Resend port 443) + SMTP fallback.
Render blocks outbound SMTP ports (25, 587, 465) on free instances.
HTTPS API calls to Resend (https://api.resend.com/emails) over Port 443 are NEVER blocked.
"""

import asyncio
import json
import logging
import os
import smtplib
import urllib.request
import urllib.error
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def emailer_configured() -> bool:
    """Check if either Resend HTTPS API or SMTP credentials are configured."""
    return bool(os.getenv("RESEND_API_KEY") or (os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD")))


# Backward compatibility alias for legacy call sites (routers/guardian.py, core/reminder_engine.py)
smtp_configured = emailer_configured


def _send_resend_https(to_addr: str, subject: str, html: str, text: str = "") -> bool:
    """Send email via Resend HTTPS REST API (Port 443 — works on Render without SMTP block)."""
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    if not api_key:
        return False

    # Default to Resend testing domain if no custom domain verified
    from_addr = os.getenv("SMTP_FROM", "").strip()
    if not from_addr or "resend.dev" in from_addr or not ("@" in from_addr):
        from_addr = "AI Tutor <onboarding@resend.dev>"

    payload = {
        "from": from_addr,
        "to": [to_addr],
        "subject": subject,
        "html": html if ("<" in html or "</" in html) else f"<p>{html}</p>",
        "text": text or (html if "<" not in html else "This email requires an HTML viewer."),
    }

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "AI-Tutor-Backend/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 201):
                logger.info("Email sent via Resend HTTPS (Port 443) to %s: %s", to_addr, subject)
                return True
    except urllib.error.HTTPError as err:
        try:
            err_body = err.read().decode("utf-8")
        except Exception:
            err_body = str(err)
        logger.error("Resend HTTPS API returned error %d for %s: %s", err.code, to_addr, err_body)
    except Exception as e:
        logger.warning("Resend HTTPS email request failed to %s: %s", to_addr, e)

    return False


def _send_sync(to_addr: str, subject: str, html_or_text: str = "", text_or_html: str = "") -> bool:
    """Send via Resend HTTPS first, falling back to SMTP if configured."""
    # Smart detection of html vs plain text parameters regardless of argument order
    if "<" in html_or_text or "</" in html_or_text:
        html, text = html_or_text, text_or_html
    elif "<" in text_or_html or "</" in text_or_html:
        html, text = text_or_html, html_or_text
    else:
        html, text = f"<p>{html_or_text or text_or_html}</p>", html_or_text or text_or_html

    # 1. Try HTTPS API (Port 443 - never blocked on Render)
    if os.getenv("RESEND_API_KEY"):
        if _send_resend_https(to_addr, subject, html, text):
            return True

    # 2. Try SMTP fallback
    if os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"):
        host = os.getenv("SMTP_HOST")
        port = int(os.getenv("SMTP_PORT", "587"))
        user = os.getenv("SMTP_USER")
        password = (os.getenv("SMTP_PASSWORD") or "").strip().replace(" ", "")
        from_addr = os.getenv("SMTP_FROM", user)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.attach(MIMEText(text or "This email requires an HTML viewer.", "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
        logger.info("Email sent via SMTP to %s: %s", to_addr, subject)
        return True

    logger.warning("No working email provider configured — skipped email to %s", to_addr)
    return False


async def send_email(to_addr: str, subject: str, body1: str = "", body2: str = "") -> bool:
    """Send an email off the event loop."""
    if not emailer_configured():
        logger.warning("Email service not configured — email to %s skipped", to_addr)
        return False
    try:
        return await asyncio.to_thread(_send_sync, to_addr, subject, body1, body2)
    except Exception as e:
        logger.error("Email send failed to %s: %s", to_addr, e)
        return False
