import os
import logging
import asyncio
from typing import Optional
from datetime import datetime, date
from fastapi import APIRouter, HTTPException, Depends, Request, Response, Body, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from jwt import PyJWTError as JWTError

from user.api.schemas import UserIn, Token, GoogleAuthRequest, ForgotPasswordRequest, ResetPasswordRequest, VerifyEmailRequest, ResendVerificationRequest
from user.database import users_collection, refresh_tokens_collection
from user.security import hash_password, verify_password
from user.dependencies import require_role, get_current_user
from slowapi import Limiter
from slowapi.util import get_remote_address
from user.core.account_recovery import (
    create_token, consume_token, PURPOSE_VERIFY, PURPOSE_RESET,
    VERIFY_TOKEN_TTL_SECONDS, RESET_TOKEN_TTL_SECONDS,
)
from user.core.emailer import send_email, emailer_configured
from user.core.email_templates import verification_email, password_reset_email
from user.core.login_guard import assert_login_allowed, record_login_failure, clear_login_failures
from user.services.token_service import TokenService, decode_token
from user.auth_config import REFRESH_TOKEN_EXPIRE_DAYS
from user.rate_limit import limiter as shared_limiter

router = APIRouter()
logger = logging.getLogger(__name__)

_background_tasks: set = set()

REFRESH_COOKIE = "refresh_token"
_COOKIE_SECURE = os.getenv("ENVIRONMENT") == "production"

_AUTO_VERIFY_SIGNUP = (
    os.getenv("ENVIRONMENT", "").lower() != "production"
    and os.getenv("E2E_AUTO_VERIFY") == "1"
)

_APP_BASE_URL = os.getenv("APP_BASE_URL", "").rstrip("/")


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="strict",
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path="/", samesite="strict")


async def _send_verification_email(username: str, email: str) -> str:
    token = await create_token(username, PURPOSE_VERIFY, VERIFY_TOKEN_TTL_SECONDS)
    link = f"{_APP_BASE_URL}/verify-email?token={token}"
    if not emailer_configured():
        logger.warning("BREVO_API_KEY is NOT set!")
    elif email:
        subject, html, text = verification_email(link)
        try:
            sent = await send_email(email, subject, html, text)
            if sent:
                logger.info("Verification email sent to %s", email)
            else:
                logger.warning("send_email returned FALSE for %s", email)
        except Exception as e:
            logger.warning("Backend send_email failed for %s: %s", username, e)
    return link


@router.post("/signup", status_code=201)
@shared_limiter.limit("5/minute")
async def signup(request: Request, user: UserIn):
    role = user.account_type

    is_minor = False
    if role == "student":
        if not user.date_of_birth:
            raise HTTPException(400, "date_of_birth is required (YYYY-MM-DD)")
        try:
            dob = user.date_of_birth
        except (ValueError, TypeError):
            raise HTTPException(400, "date_of_birth must be a valid date in YYYY-MM-DD format")
        today = date.today()
        if dob > today:
            raise HTTPException(400, "date_of_birth cannot be in the future")
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 13:
            raise HTTPException(
                403,
                "You must be at least 13 to sign up. Ask a parent or guardian to "
                "create a guardian account and set up access for you.",
            )
        is_minor = age < 18

    from user.repositories.users import UserRepository

    _generic_ok = {
        "message": "If the username and email are available, your account was created. "
                   "Check your email for a verification link before logging in.",
        "verify_required": True,
    }
    if await UserRepository.exists(user.username):
        return _generic_ok
    if await UserRepository.email_exists(user.email):
        return _generic_ok

    age_band = ""
    if role == "student":
        age_band = "13-17" if is_minor else "18+"

    doc = {
        "username": user.username,
        "hashed_password": hash_password(user.password),
        "role": role,
        "is_minor": is_minor,
        "age_band": age_band,
    }
    email = (user.email or "").strip().lower()
    doc["email"] = email
    doc["email_verified"] = _AUTO_VERIFY_SIGNUP
    if role == "guardian":
        doc["linked_children"] = []
    await UserRepository.create(doc)

    if not _AUTO_VERIFY_SIGNUP:
        try:
            verify_link = await _send_verification_email(user.username, email)
        except Exception as e:
            logger.warning("verification link failed for %s: %s", user.username, e)
            verify_link = ""
    else:
        verify_link = ""

    try:
        from user.core.analytics import track_signup
        _t = asyncio.create_task(track_signup(user.username, role))
        _background_tasks.add(_t)
        _t.add_done_callback(_background_tasks.discard)
    except Exception:
        pass

    return {
        "message": "Account created. Check your email for a verification link before logging in.",
        "verify_required": True,
        "verify_link": verify_link or None,
    }


@router.post("/login", response_model=Token)
@shared_limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
):

    identifier = (form_data.username or "").strip().lower()

    await assert_login_allowed(identifier)

    from user.repositories.users import UserRepository
    user = await UserRepository.get_by_email(identifier)

    if (
        not user
        or not user.get("hashed_password")
        or not verify_password(form_data.password, user["hashed_password"])
    ):
        await record_login_failure(identifier)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.get("email_verified", False):
        raise HTTPException(status_code=403, detail="email_not_verified")

    await clear_login_failures(identifier)

    role = user.get("role", "student")

    access_token, refresh_token = await TokenService.issue_token_pair(
        user["username"], role
    )

    _set_refresh_cookie(response, refresh_token)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": role,
        "username": user["username"],
    }


@router.post("/refresh")
@shared_limiter.limit("10/minute")
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str = Cookie(None),
    body_token: str = Body(None, embed=True, alias="refresh_token"),
):
    token = refresh_token or body_token
    if not token:
        raise HTTPException(401, "Missing refresh token")
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(401, "Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(401, "Token is not a refresh token")

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(401, "Malformed refresh token")

    from user.repositories.refresh_tokens import RefreshTokenRepository
    from user.repositories.users import UserRepository

    stored = await RefreshTokenRepository.get(jti)
    if not stored:
        raise HTTPException(401, "Refresh token has been revoked")
    if stored.get("revoked"):
        await RefreshTokenRepository.revoke_family(stored.get("username"))
        _clear_refresh_cookie(response)
        raise HTTPException(401, "Refresh token has been revoked")

    username = payload.get("sub")
    user = await UserRepository.get_by_username(username)
    if not user:
        raise HTTPException(401, "User not found")

    role = user.get("role", "student")
    new_access, new_refresh = await TokenService.rotate_refresh(jti, username, role)
    _set_refresh_cookie(response, new_refresh)

    return {"access_token": new_access, "token_type": "bearer", "role": role}


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: str = Cookie(None),
    body_token: str = Body(None, embed=True, alias="refresh_token"),
    current_user: dict = Depends(get_current_user),
):
    token = refresh_token or body_token
    _clear_refresh_cookie(response)
    if not token:
        return {"message": "Logged out successfully"}
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(400, "Invalid refresh token")

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(400, "Malformed refresh token")

    if payload.get("sub") != current_user.get("username"):
        raise HTTPException(403, "Cannot revoke another user's token")

    from user.repositories.refresh_tokens import RefreshTokenRepository
    await RefreshTokenRepository.revoke(jti)

    return {"message": "Logged out successfully"}


@router.post("/forgot-password")
@shared_limiter.limit("5/minute")
async def forgot_password(request: Request, body: ForgotPasswordRequest):
    from user.core.account_recovery import create_token, PURPOSE_RESET, RESET_TOKEN_TTL_SECONDS

    ident = (body.username or body.email or "").strip().lower()
    generic = {
        "message": "If a matching account with an email exists, a reset link has been sent."
    }
    if not ident:
        return generic

    from user.repositories.users import UserRepository
    user = await UserRepository.get_by_username_or_email(ident)
    if not user:
        return generic

    email = user.get("email")
    if not email:
        return generic

    token = await create_token(user["username"], PURPOSE_RESET, RESET_TOKEN_TTL_SECONDS)
    link = f"{_APP_BASE_URL}/reset-password?token={token}"
    generic["link"] = link

    if not emailer_configured():
        logger.warning("Email service NOT configured (BREVO_API_KEY missing)")
    else:
        subject, html, text = password_reset_email(link)
        try:
            sent = await send_email(email, subject, html, text)
            if sent:
                logger.info("forgot_password: Reset email successfully sent to %s", email)
            else:
                logger.warning("forgot_password: send_email returned False for %s", email)
        except Exception as e:
            logger.error("forgot_password: send_email exception for %s: %s", email, e)
    return generic


@router.post("/reset-password")
@shared_limiter.limit("5/minute")
async def reset_password(request: Request, body: ResetPasswordRequest):
    from user.core.account_recovery import consume_token, PURPOSE_RESET

    if len((body.new_password or "")) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    username = await consume_token(body.token, PURPOSE_RESET)
    if not username:
        raise HTTPException(400, "Invalid or expired reset token")
    from user.repositories.users import UserRepository
    from user.repositories.refresh_tokens import RefreshTokenRepository
    await UserRepository.set_password(username, hash_password(body.new_password))
    await RefreshTokenRepository.revoke_family(username)
    return {"message": "Password has been reset. Please log in."}


@router.post("/verify-email/request")
@shared_limiter.limit("5/minute")
async def request_email_verification(
    request: Request, current_user: dict = Depends(get_current_user)
):
    email = current_user.get("email")
    if not email:
        raise HTTPException(400, "No email on file. Add one to your profile first.")
    if current_user.get("email_verified"):
        return {"message": "Email already verified."}
    token = await create_token(
        current_user["username"], PURPOSE_VERIFY, VERIFY_TOKEN_TTL_SECONDS
    )
    link = f"{_APP_BASE_URL}/verify-email?token={token}"
    return {"message": "Verification email sent.", "link": link}


@router.post("/verify-email")
@shared_limiter.limit("10/minute")
async def verify_email(request: Request, body: VerifyEmailRequest):
    from user.core.account_recovery import consume_token, PURPOSE_VERIFY

    username = await consume_token(body.token, PURPOSE_VERIFY)
    if not username:
        raise HTTPException(400, "Invalid or expired verification token")
    from user.repositories.users import UserRepository
    await UserRepository.set_email_verified(username, True)
    return {"message": "Email verified."}


@router.post("/verify-email/resend")
@shared_limiter.limit("5/minute")
async def resend_verification(request: Request, body: ResendVerificationRequest):
    email = (body.email or "").strip().lower()
    generic = {"message": "If that email needs verification, a new link has been sent."}
    if not email:
        return generic
    from user.repositories.users import UserRepository
    user = await UserRepository.get_by_email(email)
    if user and user.get("email") and not user.get("email_verified"):
        try:
            generic["link"] = await _send_verification_email(user["username"], user.get("email", ""))
        except Exception as e:
            logger.warning("resend verification failed for %s: %s", user["username"], e)
    return generic


@router.post("/auth/google", response_model=Token)
@shared_limiter.limit("10/minute")
async def google_auth(request: Request, response: Response, body: GoogleAuthRequest):
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(503, "Google sign-in is not configured")
    if not body.credential:
        raise HTTPException(400, "Missing Google credential")

    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        info = await asyncio.to_thread(
            google_id_token.verify_oauth2_token,
            body.credential, google_requests.Request(), client_id,
        )
    except Exception as e:
        logger.warning("google id_token verify failed: %s", e)
        raise HTTPException(401, "Invalid Google credential")

    if info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(401, "Invalid token issuer")
    email = (info.get("email") or "").strip().lower()
    if not email or not info.get("email_verified", False):
        raise HTTPException(401, "Google account email unavailable or unverified")

    google_sub = info.get("sub", "")
    display_name = info.get("name") or email.split("@")[0]

    from user.repositories.users import UserRepository

    user = await UserRepository.get_by_email(email)
    if not user:
        role = body.account_type if body.account_type in ("student", "guardian") else "student"
        username = await _unique_username_from_email(email)
        doc = {
            "username": username,
            "role": role,
            "email": email,
            "email_verified": True,
            "google_sub": google_sub,
            "display_name": display_name,
            "is_minor": False,
            "age_band": "",
            "onboarded": False,
        }
        if role == "guardian":
            doc["linked_children"] = []
        await UserRepository.create(doc)
        user = doc
        try:
            from user.core.analytics import track_signup
            _t = asyncio.create_task(track_signup(username, role))
            _background_tasks.add(_t)
            _t.add_done_callback(_background_tasks.discard)
        except Exception:
            pass
    elif google_sub and not user.get("google_sub"):
        await UserRepository.set_google_sub(user["username"], google_sub)

    role = user.get("role", "student")
    access_token, refresh_token = await TokenService.issue_token_pair(user["username"], role)
    _set_refresh_cookie(response, refresh_token)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": role,
        "username": user["username"],
    }


async def _unique_username_from_email(email: str) -> str:
    import re as _re
    import secrets as _secrets
    from user.repositories.users import UserRepository

    base = _re.sub(r"[^a-zA-Z0-9_\-.]", "", email.split("@")[0])[:24]
    if len(base) < 3:
        base = (base + "user")[:6]
    candidate = base
    for _ in range(5):
        if not await UserRepository.exists(candidate):
            return candidate
        candidate = f"{base}{_secrets.token_hex(2)}"[:32]
    return f"{base}{_secrets.token_hex(4)}"[:32]