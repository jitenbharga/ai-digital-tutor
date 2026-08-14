import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

if not SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY must be set in environment")

VERIFY_TOKEN_TTL_SECONDS = int(os.getenv("VERIFY_TOKEN_TTL_SECONDS", "86400"))
RESET_TOKEN_TTL_SECONDS = int(os.getenv("RESET_TOKEN_TTL_SECONDS", "3600"))
PURPOSE_VERIFY = "verify_email"
PURPOSE_RESET = "reset_password"