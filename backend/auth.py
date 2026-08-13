import os
import logging
import asyncio
from typing import Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, Request, Response, Body, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from jwt import PyJWTError as JWTError

from api.schemas import UserIn, Token
from database import users_collection, refresh_tokens_collection
from security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from dependencies import require_role, get_current_user
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()
logger = logging.getLogger(__name__)

# Strong refs to fire-and-forget background tasks (prevents premature GC).
_background_tasks: set = set()

# SEC-5: the refresh token lives in an httpOnly, Secure, SameSite=Strict cookie
# so client-side JS (and therefore any XSS) can never read it.
REFRESH_COOKIE = "refresh_token"
_COOKIE_SECURE = os.getenv("ENVIRONMENT") == "production"

# TEST/E2E ONLY: auto-verify new signups so end-to-end tests can log in without a
# real mailbox. Hard-gated OFF in production (ENVIRONMENT check) and opt-in via an
# explicit E2E_AUTO_VERIFY=1 flag, so normal unit/integration tests that assert the
# real "verification required" behaviour are unaffected.
_AUTO_VERIFY_SIGNUP = (
    os.getenv("ENVIRONMENT", "").lower() != "production"
    and os.getenv("E2E_AUTO_VERIFY") == "1"
)


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


# Base URL used to build absolute links in emails (verify / reset). Falls back to
# a relative path if unset — set APP_BASE_URL in prod (e.g. https://app.example.com).
_APP_BASE_URL = os.getenv("APP_BASE_URL", "").rstrip("/")


async def _send_verification_email(username: str, email: str) -> str:
    """Create a single-use verify token, send email if backend emailer configured, return link."""
    from core.account_recovery import (
        create_token, VERIFY_TOKEN_TTL_SECONDS, PURPOSE_VERIFY,
    )
    from core.emailer import send_email, emailer_configured
    from core.email_templates import verification_email

    token = await create_token(username, PURPOSE_VERIFY, VERIFY_TOKEN_TTL_SECONDS)
    link = f"{_APP_BASE_URL}/verify-email?token={token}"
    if emailer_configured() and email:
        subject, html, text = verification_email(link)
        try:
            await send_email(email, subject, html, text)
        except Exception as e:
            logger.warning("Backend send_email failed for %s: %s", username, e)
    return link


@router.post("/signup", status_code=201)
@limiter.limit("5/minute")
async def signup(request: Request, user: UserIn):
    """Public signup — always creates a student account.

    Returns a generic success message whether or not the username is
    already taken, so an attacker cannot enumerate valid usernames.
    """
    role = user.account_type  # "student" or "guardian"

    # ── Age gate (13+ policy). Students must provide DOB. ──
    is_minor = False
    if role == "student":
        if not user.date_of_birth:
            raise HTTPException(400, "date_of_birth is required (YYYY-MM-DD)")
        from datetime import date
        try:
            dob = date.fromisoformat(user.date_of_birth)
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

    from repositories.users import UserRepository
    # Generic response (no account enumeration) whether username OR email is taken.
    _generic_ok = {
        "message": "If the username and email are available, your account was created. "
                   "Check your email for a verification link before logging in.",
        "verify_required": True,
    }
    if await UserRepository.exists(user.username):
        return _generic_ok
    if await UserRepository.email_exists(user.email):
        return _generic_ok

    # PRIVACY / data-minimization (GDPR-K): we only need to know the age *band*
    # (to gate minor-only features), not the exact birthdate. Derive the band and
    # the is_minor flag, then discard the raw DOB — it is never persisted.
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
    # Email is required now (login identifier + verification). Stored lowercased.
    email = (user.email or "").strip().lower()
    doc["email"] = email
    doc["email_verified"] = _AUTO_VERIFY_SIGNUP
    if role == "guardian":
        doc["linked_children"] = []  # student usernames this guardian can read
    await UserRepository.create(doc)

    # Build the verification link. Sending is done by the frontend (email
    # service), so the link is returned in the response. Skipped when
    # auto-verify is on (test/E2E) since there's no real mailbox.
    if not _AUTO_VERIFY_SIGNUP:
        try:
            verify_link = await _send_verification_email(user.username, email)
        except Exception as e:
            logger.warning("verification link failed for %s: %s", user.username, e)
            verify_link = ""
    else:
        verify_link = ""

    # P0.3: Track signup event (fire-and-forget, but keep a reference so the
    # task isn't garbage-collected mid-flight and log any failure).
    try:
        from core.analytics import track_signup
        import asyncio
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
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
):

    # Login is by EMAIL. OAuth2PasswordRequestForm's `username` field carries the
    # email (the frontend sends it there).
    identifier = (form_data.username or "").strip().lower()

    # L-11: reject early if this identifier is locked out after repeated failures.
    from core.login_guard import (
        assert_login_allowed, record_login_failure, clear_login_failures,
    )
    await assert_login_allowed(identifier)

    from repositories.users import UserRepository
    from services.token_service import TokenService
    user = await UserRepository.get_by_email(identifier)

    # Reject if: no such email, OR account is Google-only (no password set), OR
    # wrong password. Same 401 for all → no account enumeration / no signal about
    # which emails exist or how they authenticate.
    if (
        not user
        or not user.get("hashed_password")
        or not verify_password(form_data.password, user["hashed_password"])
    ):
        await record_login_failure(identifier)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # SEC: block login until the email is verified (detail is a stable code the
    # frontend keys on to offer a "resend verification" action).
    if not user.get("email_verified", False):
        raise HTTPException(status_code=403, detail="email_not_verified")

    # Successful auth clears the failure counter.
    await clear_login_failures(identifier)

    role = user.get("role", "student")

    # W4: token issuance + refresh persistence live in the service/repository layer.
    access_token, refresh_token = await TokenService.issue_token_pair(
        user["username"], role
    )

    # SEC-5: refresh token → httpOnly cookie; only the short-lived access token
    # goes to JS (kept in memory client-side, never localStorage).
    _set_refresh_cookie(response, refresh_token)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": role,
        "username": user["username"],
    }


@router.post("/refresh")
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str = Cookie(None),
    body_token: str = Body(None, embed=True, alias="refresh_token"),
):
    """Exchange a valid refresh token (from the httpOnly cookie) for a new
    access token. Falls back to a body token for backward compatibility."""
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

    # W4: revocation + rotation via the repository/service layer.
    from repositories.refresh_tokens import RefreshTokenRepository
    from repositories.users import UserRepository
    from services.token_service import TokenService

    stored = await RefreshTokenRepository.get(jti)
    if not stored:
        raise HTTPException(401, "Refresh token has been revoked")
    if stored.get("revoked"):
        # Reuse of an already-rotated token: likely theft/replay. Revoke the
        # whole token family for this user as a precaution.
        await RefreshTokenRepository.revoke_family(stored.get("username"))
        _clear_refresh_cookie(response)
        raise HTTPException(401, "Refresh token has been revoked")

    username = payload.get("sub")
    user = await UserRepository.get_by_username(username)
    if not user:
        raise HTTPException(401, "User not found")

    role = user.get("role", "student")
    # SEC: rotate — issue a new access+refresh pair and revoke the old jti. A
    # stolen old token becomes useless after the legitimate client refreshes.
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
    """Revoke the refresh token (from cookie) and clear it."""
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

    # Only let a user revoke their own tokens
    if payload.get("sub") != current_user.get("username"):
        raise HTTPException(403, "Cannot revoke another user's token")

    from repositories.refresh_tokens import RefreshTokenRepository
    await RefreshTokenRepository.revoke(jti)

    return {"message": "Logged out successfully"}


# ── W3: Account recovery — password reset + email verification ──────────────
from pydantic import BaseModel


class ForgotPasswordRequest(BaseModel):
    username: str = ""
    email: str = ""


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class VerifyEmailRequest(BaseModel):
    token: str


@router.post("/forgot-password")
@limiter.limit("5/minute")
async def forgot_password(request: Request, body: ForgotPasswordRequest):
    """Start a password reset. Always returns a generic message (no account
    enumeration). If the account exists AND has an email, a reset link is
    returned — the FRONTEND emails it (EmailJS from the browser)."""
    from core.account_recovery import (
        create_token, RESET_TOKEN_TTL_SECONDS, PURPOSE_RESET,
    )

    ident = (body.username or body.email or "").strip().lower()
    generic = {
        "message": "If a matching account with an email exists, a reset link has been sent."
    }
    if not ident:
        return generic
    from repositories.users import UserRepository
    user = await UserRepository.get_by_username_or_email(ident)
    if not user:
        print(f"[AUTH] forgot_password: No user account found for '{ident}'", flush=True)
        logger.warning("forgot_password: No user account found for '%s'", ident)
        return generic

    email = user.get("email")
    if not email:
        print(f"[AUTH] forgot_password: User '{user.get('username')}' has NO email on file!", flush=True)
        logger.warning("forgot_password: User '%s' has no email on file", user.get("username"))
        return generic

    token = await create_token(user["username"], PURPOSE_RESET, RESET_TOKEN_TTL_SECONDS)
    link = f"{_APP_BASE_URL}/reset-password?token={token}"
    generic["link"] = link

    from core.emailer import send_email, emailer_configured
    from core.email_templates import password_reset_email
    if not emailer_configured():
        print("[AUTH] forgot_password: BREVO_API_KEY is NOT set in environment variables!", flush=True)
        logger.warning("forgot_password: Email service NOT configured (BREVO_API_KEY missing)")
    else:
        subject, html, text = password_reset_email(link)
        try:
            print(f"[AUTH] forgot_password: Attempting send_email to {email}...", flush=True)
            sent = await send_email(email, subject, html, text)
            if sent:
                print(f"[AUTH] forgot_password: Reset email SUCCESS for {email}", flush=True)
                logger.info("forgot_password: Reset email successfully sent to %s", email)
            else:
                print(f"[AUTH] forgot_password: send_email returned FALSE for {email}", flush=True)
                logger.warning("forgot_password: send_email returned False for %s", email)
        except Exception as e:
            print(f"[AUTH] forgot_password: EXCEPTION for {email}: {e}", flush=True)
            logger.error("forgot_password: send_email exception for %s: %s", email, e)
    return generic


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(request: Request, body: ResetPasswordRequest):
    """Complete a password reset with a valid single-use token."""
    from core.account_recovery import consume_token, PURPOSE_RESET

    if len((body.new_password or "")) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    username = await consume_token(body.token, PURPOSE_RESET)
    if not username:
        raise HTTPException(400, "Invalid or expired reset token")
    from repositories.users import UserRepository
    from repositories.refresh_tokens import RefreshTokenRepository
    await UserRepository.set_password(username, hash_password(body.new_password))
    # SEC: revoke every refresh token so any session opened with the old password
    # (e.g. by an attacker) is invalidated the moment the owner resets.
    await RefreshTokenRepository.revoke_family(username)
    return {"message": "Password has been reset. Please log in."}


@router.post("/verify-email/request")
@limiter.limit("5/minute")
async def request_email_verification(
    request: Request, current_user: dict = Depends(get_current_user)
):
    """Return a verification link for the logged-in user's email — the
    FRONTEND emails it (see frontend/src/lib/emailService.js)."""
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
@limiter.limit("10/minute")
async def verify_email(request: Request, body: VerifyEmailRequest):
    """Confirm an email address with a valid single-use token."""
    from core.account_recovery import consume_token, PURPOSE_VERIFY

    username = await consume_token(body.token, PURPOSE_VERIFY)
    if not username:
        raise HTTPException(400, "Invalid or expired verification token")
    from repositories.users import UserRepository
    await UserRepository.set_email_verified(username, True)
    return {"message": "Email verified."}


class ResendVerificationRequest(BaseModel):
    email: str = ""


@router.post("/verify-email/resend")
@limiter.limit("5/minute")
async def resend_verification(request: Request, body: ResendVerificationRequest):
    """Public: return a fresh verification link for the email address. Generic
    response (no enumeration). No-op if the account is missing or already
    verified — needed because unverified users can't log in to hit the authed
    request endpoint. The FRONTEND emails the link when present."""
    email = (body.email or "").strip().lower()
    generic = {"message": "If that email needs verification, a new link has been sent."}
    if not email:
        return generic
    from repositories.users import UserRepository
    user = await UserRepository.get_by_email(email)
    if user and user.get("email") and not user.get("email_verified"):
        try:
            generic["link"] = await _send_verification_email(user["username"], user.get("email", ""))
        except Exception as e:
            logger.warning("resend verification failed for %s: %s", user["username"], e)
    return generic


# ── Continue with Google (Google Identity Services) ─────────────────────────
class GoogleAuthRequest(BaseModel):
    credential: str  # Google ID token (JWT) from the GIS button
    account_type: Optional[str] = "student"  # "student" or "guardian"


async def _unique_username_from_email(email: str) -> str:
    """Derive a valid, unique username from an email local-part."""
    import re as _re
    import secrets as _secrets
    from repositories.users import UserRepository

    base = _re.sub(r"[^a-zA-Z0-9_\-.]", "", email.split("@")[0])[:24]
    if len(base) < 3:
        base = (base + "user")[:6]
    candidate = base
    for _ in range(5):
        if not await UserRepository.exists(candidate):
            return candidate
        candidate = f"{base}{_secrets.token_hex(2)}"[:32]
    return f"{base}{_secrets.token_hex(4)}"[:32]


@router.post("/auth/google", response_model=Token)
@limiter.limit("10/minute")
async def google_auth(request: Request, response: Response, body: GoogleAuthRequest):
    """Verify a Google ID token, then log in (existing email) or create a new
    verified student/guardian account. No password is set for Google-only accounts."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(503, "Google sign-in is not configured")
    if not body.credential:
        raise HTTPException(400, "Missing Google credential")

    # Verify signature + audience (client_id) + issuer with Google's public keys.
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

    from repositories.users import UserRepository
    from services.token_service import TokenService

    user = await UserRepository.get_by_email(email)
    if not user:
        role = body.account_type if body.account_type in ("student", "guardian") else "student"
        username = await _unique_username_from_email(email)
        doc = {
            "username": username,
            "role": role,
            "email": email,
            "email_verified": True,   # Google already verified it
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
            from core.analytics import track_signup
            _t = asyncio.create_task(track_signup(username, role))
            _background_tasks.add(_t)
            _t.add_done_callback(_background_tasks.discard)
        except Exception:
            pass
    elif google_sub and not user.get("google_sub"):
        # Link Google to an existing password account on first Google login.
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
