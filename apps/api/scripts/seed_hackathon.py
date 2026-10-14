"""Idempotently seed the PaymentOps hackathon demo tenant and operator client.

Creates (only if absent):
- an Organization with the configured public id (``EVOLUS_DEMO_ORG_PUBLIC_ID``);
- an optional ADMIN application user;
- an optional operator API client (``PAYMENTOPS_OPERATOR_CLIENT_ID`` /
  ``PAYMENTOPS_OPERATOR_CLIENT_SECRET``), storing only a salted hash of the secret.

No secret value is ever printed. Intended to run as a one-shot Kubernetes Job, or inside the
API container:

    EVOLUS_DEMO_ORG_PUBLIC_ID=cloudnova-hackathon-demo \
    PAYMENTOPS_OPERATOR_CLIENT_ID=... PAYMENTOPS_OPERATOR_CLIENT_SECRET=... \
    PAYMENTOPS_BOOTSTRAP_ADMIN_EMAIL=... PAYMENTOPS_BOOTSTRAP_ADMIN_PASSWORD=... \
    python -m scripts.seed_hackathon
"""

from __future__ import annotations

import asyncio
import os
import sys

from paymentops_api.auth import hash_secret
from paymentops_api.db.base import Database
from paymentops_api.db.models import ApiClient, Organization
from paymentops_api.services import user_service
from paymentops_api.settings import get_settings
from sqlalchemy import select


async def _seed() -> int:
    org_public_id = os.environ.get("EVOLUS_DEMO_ORG_PUBLIC_ID", "").strip()
    org_name = os.environ.get("PAYMENTOPS_HACKATHON_ORG_NAME", "CloudNova Hackathon Demo").strip()
    client_id = os.environ.get("PAYMENTOPS_OPERATOR_CLIENT_ID", "").strip()
    client_secret = os.environ.get("PAYMENTOPS_OPERATOR_CLIENT_SECRET", "")
    admin_email = os.environ.get("PAYMENTOPS_BOOTSTRAP_ADMIN_EMAIL", "").strip()
    admin_password = os.environ.get("PAYMENTOPS_BOOTSTRAP_ADMIN_PASSWORD", "")
    admin_name = os.environ.get("PAYMENTOPS_BOOTSTRAP_ADMIN_NAME", "Hackathon Operator").strip()

    if not org_public_id:
        print("EVOLUS_DEMO_ORG_PUBLIC_ID is required.")
        return 2

    db = Database(get_settings())
    try:
        async for session in db.session():
            result = await session.execute(
                select(Organization).where(Organization.public_id == org_public_id)
            )
            org = result.scalar_one_or_none()
            if org is None:
                org = Organization(name=org_name, public_id=org_public_id)
                session.add(org)
                await session.commit()
                await session.refresh(org)
                print(f"created organization public_id={org_public_id}")
            else:
                print(f"organization exists public_id={org_public_id}")

            if client_id and client_secret:
                existing = await session.execute(
                    select(ApiClient).where(ApiClient.client_id == client_id)
                )
                if existing.scalar_one_or_none() is None:
                    session.add(
                        ApiClient(
                            client_id=client_id,
                            secret_hash=hash_secret(client_secret),
                            organization_id=org.id,
                            allowed_profiles=[],
                            status="ACTIVE",
                        )
                    )
                    await session.commit()
                    print("operator api client created")
                else:
                    print("operator api client exists (no change)")

            if admin_email and admin_password:
                existing_admin = await user_service.get_user_by_email(session, admin_email)
                if existing_admin is None:
                    if len(admin_password) < 12:
                        print("admin password must be at least 12 characters.")
                        return 2
                    await user_service.create_user(
                        session,
                        organization_id=str(org.id),
                        email=admin_email,
                        display_name=admin_name,
                        password=admin_password,
                        role=user_service.UserRole.ADMIN,
                    )
                    print("admin user created")
                else:
                    print("admin user exists (no change)")
            return 0
    finally:
        await db.dispose()
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_seed()))
