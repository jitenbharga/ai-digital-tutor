"""
B6: Minimal SMTP emailer — stdlib only (smtplib in a thread), no new deps.

Env vars (all required for sending; if unset, send_email() no-ops with a log):
  SMTP_HOST       e.g. smtp.gmail.com
  SMTP_PORT       default 587 (STARTTLS)
  SMTP_USER       login username
  SMTP_PASSWORD   login password / app password
  SMTP_FROM       From address (defaults to SMTP_USER)
"""
import asyncio
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))


def _send_sync(to_addr: str, subject: str, html: str, text: str = ""):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    # Gmail App Passwords display with spaces but must be sent without them.
    password = (os.getenv("SMTP_PASSWORD") or "").strip().replace(" ", "")
    from_addr = os.getenv("SMTP_FROM", user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(text or "This email requires an HTML viewer.", "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(host, port, timeout=20) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(from_addr, [to_addr], msg.as_string())


async def send_email(to_addr: str, subject: str, html: str, text: str = "") -> bool:
    """Send an email off the event loop. Returns False (and logs) on any failure."""
    if not smtp_configured():
        logger.warning("SMTP not configured — email to %s skipped", to_addr)
        return False
    try:
        await asyncio.to_thread(_send_sync, to_addr, subject, html, text)
        logger.info("email sent to %s: %s", to_addr, subject)
        return True
    except Exception as e:
        logger.error("email send failed to %s: %s", to_addr, e)
        return False
