import hashlib
import hmac
import os
import re

import jwt
from fastapi import Depends, Header, HTTPException, status
from werkzeug.security import check_password_hash, generate_password_hash

import database

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, hashed: str) -> bool:
    if hashed.startswith(("scrypt:", "pbkdf2:")):
        return check_password_hash(hashed, password)
    if re.fullmatch(r"[a-fA-F0-9]{64}", hashed):
        legacy_hash = hashlib.sha256(password.encode()).hexdigest()
        return hmac.compare_digest(legacy_hash, hashed)
    return False


def is_legacy_password_hash(hashed: str) -> bool:
    return re.fullmatch(r"[a-fA-F0-9]{64}", hashed) is not None


def decode_bearer(authorization: str | None) -> dict:
    if not authorization:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"error": "No token provided"})
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"error": "No token provided"})
    try:
        payload = jwt.decode(parts[1], SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"error": "Token has expired"})
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"error": "Invalid token"})
    if not isinstance(payload, dict) or not isinstance(payload.get("username"), str):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"error": "Invalid token"})
    return payload


def current_user(authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    payload = decode_bearer(authorization)
    user = database.get_user_by_username(payload["username"])
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"error": "User not found"})
    return user


def citizen_user(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "citizen":
        raise HTTPException(status.HTTP_403_FORBIDDEN, {"error": "Unauthorized"})
    return user


def authority_user(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "authority":
        raise HTTPException(status.HTTP_403_FORBIDDEN, {"error": "Unauthorized"})
    return user


def decode_query_token(token: str | None) -> dict:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"error": "No token provided"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"error": "Token has expired"})
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"error": "Invalid token"})
    if not isinstance(payload, dict) or not isinstance(payload.get("username"), str):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"error": "Invalid token"})
    return payload


def query_user(token: str | None, required_role: str | None = None) -> dict:
    payload = decode_query_token(token)
    user = database.get_user_by_username(payload["username"])
    if not user:
        raise HTTPException(status.HTTP_403_FORBIDDEN, {"error": "Unauthorized"})
    if required_role and user["role"] != required_role:
        raise HTTPException(status.HTTP_403_FORBIDDEN, {"error": "Unauthorized"})
    return user
