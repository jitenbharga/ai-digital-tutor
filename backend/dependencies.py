from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt import PyJWTError as JWTError

from auth_config import SECRET_KEY, ALGORITHM
from database import users_collection

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")

        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        # SEC: reject refresh tokens (or any non-access token) presented as a
        # bearer credential. Older access tokens issued before this field was
        # added omit "type"; treat a missing type as "access" for backward
        # compatibility, but never accept an explicit "refresh".
        if payload.get("type", "access") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")

        # W4: persistence goes through the repository layer.
        from repositories.users import UserRepository
        user = await UserRepository.get_by_username(username)

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return user

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def assert_owns_student(current_user: dict, student_id: str) -> str:
    """SEC/IDOR: authoritative check that ``current_user`` may act on ``student_id``.

    Write endpoints historically trusted a ``student_id`` supplied in the request
    body, letting any authenticated user mutate another student's state. This
    helper is the single source of truth for that authorization decision:

    * A student may only act on their own record.
    * A guardian is read-only and may NOT use write endpoints, so guardians are
      rejected here (read access is handled separately by
      ``require_self_or_guardian``).

    Returns the validated student_id (always the caller's own username) so
    callers can use the returned value and never the client-supplied one.
    """
    username = current_user.get("username")
    # Students act only on themselves. We deliberately ignore the client value
    # and return the token-derived username to eliminate the IDOR entirely.
    if student_id and student_id != username:
        raise HTTPException(
            status_code=403,
            detail="You can only perform this action on your own account",
        )
    return username


def require_role(role: str):
    """FastAPI dependency that enforces a specific role on the current user."""
    async def _check(current_user: dict = Depends(get_current_user)):
        user_role = current_user.get("role", "student")
        if user_role != role:
            raise HTTPException(
                status_code=403,
                detail=f"This endpoint requires '{role}' role"
            )
        return current_user
    return _check


def require_self_or_guardian(param: str = "student_id"):
    """FastAPI dependency that closes the student-id IDOR (SEC-1).

    Reads ``param`` from the request path (falling back to query) and allows
    the request only if it matches the caller's own username, OR the caller is
    a guardian whose ``linked_children`` includes that student. Any other
    logged-in user gets 403 instead of another student's data.
    """
    async def _check(
        request: Request,
        current_user: dict = Depends(get_current_user),
    ):
        target = request.path_params.get(param) or request.query_params.get(param)
        if not target:
            raise HTTPException(status_code=400, detail=f"Missing {param}")

        username = current_user.get("username")
        if target == username:
            return current_user

        if (
            current_user.get("role") == "guardian"
            and target in current_user.get("linked_children", [])
        ):
            return current_user

        raise HTTPException(
            status_code=403,
            detail="You do not have access to this student's data",
        )

    return _check
