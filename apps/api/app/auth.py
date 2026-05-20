"""Verify Bearer tokens against auth-service /internal/verify."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    org_id: str | None
    role: str | None


def _auth_disabled() -> bool:
    return os.getenv("AUTH_DISABLED", "").lower() in ("1", "true", "yes")


def _verify_token(token: str) -> AuthUser:
    base = os.getenv("AUTH_SERVICE_URL", "http://127.0.0.1:4000").rstrip("/")
    api_key = os.getenv("AUTH_SERVICE_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AUTH_SERVICE_API_KEY is not configured on the API",
        )

    try:
        with httpx.Client(timeout=5.0) as client:
            res = client.post(
                f"{base}/internal/verify",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"token": token},
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot reach auth service at {base}: {exc}",
        ) from exc

    if res.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service verification failed",
        )

    body = res.json()
    if not body.get("valid"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    user_id = body.get("userId")
    if not user_id or not isinstance(user_id, str):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service returned an invalid user id",
        )

    org_id = body.get("orgId")
    role = body.get("role")
    return AuthUser(
        user_id=user_id,
        org_id=org_id if isinstance(org_id, str) else None,
        role=role if isinstance(role, str) else None,
    )


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ] = None,
) -> AuthUser:
    if _auth_disabled():
        return AuthUser(
            user_id=os.getenv("AUTH_DEV_USER_ID", "dev-user"),
            org_id=None,
            role=None,
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization: Bearer <token>",
        )

    return _verify_token(credentials.credentials)
