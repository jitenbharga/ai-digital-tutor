"""
Brevo (formerly Sendinblue) HTTPS REST API Email Dispatcher.
Uses HTTPS Port 443 — NEVER blocked on Render or any cloud provider.
"""

import asyncio
import json
import logging
import os
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


def emailer_configured() -> bool:
    """Check if Brevo API Key is configured in environment."""
    return bool(os.getenv("BREVO_API_KEY") or os.getenv("SENDINBLUE_API_KEY"))


# Alias for backward compatibility
smtp_configured = emailer_configured


def _send_brevo_sync(to_addr: str, subject: str, html: str, text: str = "") -> bool:
    """Send transactional email via Brevo REST API v3 (Port 443)."""
    api_key = (os.getenv("BREVO_API_KEY") or os.getenv("SENDINBLUE_API_KEY") or "").strip()
    if not api_key:
        logger.warning("Brevo API Key (BREVO_API_KEY) not set in environment.")
        return False

    sender_email = (os.getenv("BREVO_SENDER_EMAIL") or os.getenv("SMTP_FROM") or "jitenbharga40@gmail.com").strip()
    sender_name = (os.getenv("BREVO_SENDER_NAME") or "AI TUTOR").strip()

    if "<" in sender_email and ">" in sender_email:
        parts = sender_email.split("<")
        sender_name = parts[0].strip()
        sender_email = parts[1].replace(">", "").strip()

    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_addr}],
        "subject": subject,
        "htmlContent": html if ("<" in html or "</" in html) else f"<p>{html}</p>",
        "textContent": text or (html if "<" not in html else "This email requires an HTML viewer."),
    }

    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AI-Digital-Tutor/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            if resp.status in (200, 201, 202):
                logger.info("Email sent via Brevo HTTPS REST API (Port 443) to %s: %s", to_addr, subject)
                return True
    except urllib.error.HTTPError as err:
        try:
            err_body = err.read().decode("utf-8")
        except Exception:
            err_body = str(err)
        logger.error("Brevo REST API error %d for %s: %s", err.code, to_addr, err_body)
    except Exception as e:
        logger.error("Brevo REST API request exception for %s: %s", to_addr, e)

    return False


async def send_email(to_addr: str, subject: str, body1: str = "", body2: str = "") -> bool:
    """Send transactional email off the event loop via Brevo REST API."""
    if not emailer_configured():
        logger.warning("Brevo email service not configured — email to %s skipped", to_addr)
        return False

    if "<" in body1 or "</" in body1:
        html, text = body1, body2
    elif "<" in body2 or "</" in body2:
        html, text = body2, body1
    else:
        html, text = f"<p>{body1 or body2}</p>", body1 or body2

    try:
        return await asyncio.to_thread(_send_brevo_sync, to_addr, subject, html, text)
    except Exception as e:
        logger.error("Failed to dispatch email to %s: %s", to_addr, e)
        return False