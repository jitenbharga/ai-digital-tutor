import logging

logger = logging.getLogger(__name__)


async def track_signup(username: str, role: str):
    logger.info("Analytics: signup username=%s role=%s", username, role)