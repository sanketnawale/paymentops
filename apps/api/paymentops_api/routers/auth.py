"""Authentication API (server-to-server).

These endpoints are called by the trusted Next.js web server, not the public browser, and
require the internal operator API client. They return/accept opaque session tokens; the raw
token is never logged. Sessions are revocable server-side.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from paymentops_api.auth import AuthenticatedClient, get_api_client, get_db
from paymentops_api.db.models import AppUser, AuditEvent
from paymentops_api.services import user_service

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


def _user_dict(user: AppUser) -> dict[str, object]:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "organization_id": str(user.organization_id),
    }


@router.post("/api/v1/auth/login")
async def login(
    body: LoginRequest,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        user = await user_service.authenticate(session, body.email, body.password)
    except user_service.AccountDisabledError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled. Contact your administrator.",
        ) from None
    except user_service.AuthenticationError:
        # Generic message: never reveal whether the email exists.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        ) from None
    token, expires_at = await user_service.create_session(session, user)
    session.add(
        AuditEvent(
            organization_id=user.organization_id,
            case_id=None,
            event_type="auth.login",
            user_identity=user.email,
            action_metadata={"role": user.role},
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()
    return {
        "session_token": token,
        "expires_at": expires_at.isoformat(),
        "user": _user_dict(user),
    }


@router.get("/api/v1/auth/session")
async def session_info(
    x_session_token: str = Header(..., alias="X-Session-Token"),
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user = await user_service.resolve_session(session, x_session_token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid")
    return {"user": _user_dict(user)}


@router.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    x_session_token: str = Header(..., alias="X-Session-Token"),
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> None:
    user = await user_service.resolve_session(session, x_session_token)
    await user_service.revoke_session(session, x_session_token)
    if user is not None:
        session.add(
            AuditEvent(
                organization_id=user.organization_id,
                case_id=None,
                event_type="auth.logout",
                user_identity=user.email,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
