from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt import PyJWTError as JWTError

from user.auth_config import SECRET_KEY, ALGORITHM
from user.database import users_collection

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")

        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        if payload.get("type", "access") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")

        from user.repositories.users import UserRepository
        user = await UserRepository.get_by_username(username)

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return user

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def assert_owns_student(current_user: dict, student_id: str) -> str:
    username = current_user.get("username")
    if student_id and student_id != username:
        raise HTTPException(
            status_code=403,
            detail="You can only perform this action on your own account",
        )
    return username


def require_role(role: str):
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