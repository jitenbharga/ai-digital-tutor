import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_brevo_client = None


def get_brevo_client():
    global _brevo_client
    if _brevo_client is None:
        api_key = os.getenv("BREVO_API_KEY", "").strip()
        if not api_key:
            return None
        try:
            import sib_api_v3_sdk
            configuration = sib_api_v3_sdk.Configuration()
            configuration.api_key["api-key"] = api_key
            _brevo_client = sib_api_v3_sdk.TransactionalEmailsApi(
                sib_api_v3_sdk.ApiClient(configuration)
            )
        except Exception as e:
            logger.warning("Failed to init Brevo client: %s", e)
            return None
    return _brevo_client


def emailer_configured() -> bool:
    return get_brevo_client() is not None


# Alias for backward compatibility
smtp_configured = emailer_configured


async def send_email(to_email: str, subject: str, html: str, text: str) -> bool:
    client = get_brevo_client()
    if not client:
        logger.warning("Brevo not configured, skipping email to %s", to_email)
        return False
    try:
        import sib_api_v3_sdk
        sender_email = (os.getenv("BREVO_SENDER_EMAIL") or os.getenv("SMTP_FROM") or "noreply@digitaltutor.app").strip()
        sender_name = os.getenv("BREVO_SENDER_NAME", "Digital Tutor")

        if "<" in sender_email and ">" in sender_email:
            parts = sender_email.split("<")
            sender_name = parts[0].strip()
            sender_email = parts[1].replace(">", "").strip()

        email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": to_email}],
            sender={"email": sender_email, "name": sender_name},
            subject=subject,
            html_content=html,
            text_content=text,
        )
        await client.send_transac_email(email)
        return True
    except Exception as e:
        logger.error("Brevo send_email failed: %s", e)
        return False