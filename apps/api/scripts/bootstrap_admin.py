"""Bootstrap the first CloudNova administrator (one-time, safe, idempotent).

Usage (inside the API container or a host with DB access):

    PAYMENTOPS_BOOTSTRAP_ADMIN_EMAIL=admin@example.com \
    PAYMENTOPS_BOOTSTRAP_ADMIN_PASSWORD='<strong-temporary-password>' \
    PAYMENTOPS_BOOTSTRAP_ORG_PUBLIC_ID=cloudnova \
    PAYMENTOPS_BOOTSTRAP_ORG_NAME='CloudNova' \
    python -m scripts.bootstrap_admin

- The password is read from the environment and never printed or logged.
- Re-running with an existing email is a no-op (safe).
- Documented procedure: create the admin, then change the temporary password out-of-band.
"""

from __future__ import annotations

import asyncio
import os
import sys

from paymentops_api.db.base import Database
from paymentops_api.db.models import Organization
from paymentops_api.services import user_service
from paymentops_api.settings import get_settings
from sqlalchemy import select


async def _bootstrap() -> int:
    email = os.environ.get("PAYMENTOPS_BOOTSTRAP_ADMIN_EMAIL", "").strip()
    password = os.environ.get("PAYMENTOPS_BOOTSTRAP_ADMIN_PASSWORD", "")
    display_name = os.environ.get(
        "PAYMENTOPS_BOOTSTRAP_ADMIN_NAME", "CloudNova Administrator"
    ).strip()
    org_public_id = os.environ.get("PAYMENTOPS_BOOTSTRAP_ORG_PUBLIC_ID", "cloudnova").strip()
    org_name = os.environ.get("PAYMENTOPS_BOOTSTRAP_ORG_NAME", "CloudNova").strip()

    if not email or not password:
        print(
            "PAYMENTOPS_BOOTSTRAP_ADMIN_EMAIL and PAYMENTOPS_BOOTSTRAP_ADMIN_PASSWORD are required."
        )
        return 2
    if len(password) < 12:
        print("Password must be at least 12 characters.")
        return 2

    db = Database(get_settings())
    try:
        async for session in db.session():
            existing = await user_service.get_user_by_email(session, email)
            if existing is not None:
                print(f"Admin user already exists: {existing.email} (no change).")
                return 0
            result = await session.execute(
                select(Organization).where(Organization.public_id == org_public_id)
            )
            org = result.scalar_one_or_none()
            if org is None:
                org = Organization(name=org_name, public_id=org_public_id)
                session.add(org)
                await session.commit()
                await session.refresh(org)
            await user_service.create_user(
                session,
                organization_id=str(org.id),
                email=email,
                display_name=display_name,
                password=password,
                role=user_service.UserRole.ADMIN,
            )
            print(f"Created ADMIN user {email} in organization '{org_public_id}'.")
            print("Change this temporary password after first sign-in.")
            return 0
    finally:
        await db.dispose()
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_bootstrap()))
