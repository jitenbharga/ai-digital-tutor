from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date


class UserIn(BaseModel):
    username: str
    email: EmailStr
    password: str
    account_type: str = "student"
    date_of_birth: Optional[date] = None


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