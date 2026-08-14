from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import date


class UserIn(BaseModel):
    username: str
    email: EmailStr
    password: str
    account_type: str = "student"
    date_of_birth: Optional[date] = None

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def _empty_dob_to_none(cls, v):
        return v if v not in ("", None) else None


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str


class GoogleAuthRequest(BaseModel):
    credential: str
    account_type: Optional[str] = "student"


class ForgotPasswordRequest(BaseModel):
    username: str = ""
    email: str = ""


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: str = ""