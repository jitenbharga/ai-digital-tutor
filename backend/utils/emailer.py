"""
Emailer — intentionally disabled.
All user-facing emails (verification, password reset, guardian invite,
weekly digest) are sent from the BROWSER via EmailJS
(frontend/src/lib/emailService.js). The backend only generates the links;
it never sends mail itself. Kept as a no-op so auth.py imports still work.
"""

import logging

logger = logging.getLogger(__name__)


def emailer_configured() -> bool:
    """Backend email is disabled by design — always False."""
    return False


# Alias for backward compatibility
smtp_configured = emailer_configured


async def send_email(to_addr: str, subject: str, body1: str = "", body2: str = "") -> bool:
    """Never called: backend mail is sent from the browser via EmailJS."""
    logger.info("Backend email disabled — %s: %s (sent from browser via EmailJS instead)", to_addr, subject)
    return False