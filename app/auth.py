"""
JWT-аутентификация.

Пароли хранятся в виде PBKDF2-HMAC-SHA256 хэша с солью (без внешних
бинарных зависимостей вроде bcrypt — только стандартная библиотека).
Токены — JWT (HS256) через PyJWT.
"""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.models import UserPublic
from app.storage import users_table

SECRET_KEY = os.environ.get("SECRET_KEY", "sirius-arenda-dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 часа

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, digest_hex = stored_hash.split("$", 1)
    except ValueError:
        return False
    new_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return hmac.compare_digest(new_hash.hex(), digest_hex)


def create_user(username: str, password: str) -> dict:
    if users_table.get("username", username):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Пользователь с таким именем уже существует")
    user = {
        "id": users_table.next_id(),
        "username": username,
        "password_hash": _hash_password(password),
    }
    return users_table.insert(user)


def authenticate_user(username: str, password: str) -> dict | None:
    user = users_table.get("username", username)
    if not user or not _verify_password(password, user["password_hash"]):
        return None
    return user


def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "username": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str | None = Depends(oauth2_scheme)) -> UserPublic:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить учётные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        username = payload.get("username")
    except (jwt.PyJWTError, TypeError, ValueError):
        raise credentials_exception

    user = users_table.get("id", user_id)
    if user is None:
        raise credentials_exception
    return UserPublic(id=user["id"], username=username)
