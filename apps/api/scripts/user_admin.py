"""User administration CLI (safe, non-public).

Never prints passwords. Uses the same PBKDF2 hashing as login. Password changes revoke all
existing sessions and clear any login lockout.

Examples:

    # create a user (also see scripts/bootstrap_admin.py)
    PAYMENTOPS_USER_PASSWORD='...' python -m scripts.user_admin create-user \
        --email user@example.com --name "User" --org cloudnova-demo-bank --role OPERATOR

    PAYMENTOPS_USER_PASSWORD='...' python -m scripts.user_admin reset-password \
        --email user@example.com
    python -m scripts.user_admin enable-user  --email user@example.com
    python -m scripts.user_admin set-role     --email user@example.com --role ADMIN
    python -m scripts.user_admin revoke-sessions --email user@example.com
    python -m scripts.user_admin list-users
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from paymentops_api.db.base import Database
from paymentops_api.db.models import Organization
from paymentops_api.services import user_service
from paymentops_api.settings import get_settings
from sqlalchemy import select


def _password_from_env() -> str | None:
    value = os.environ.get("PAYMENTOPS_USER_PASSWORD")
    if not value:
        return None
    if len(value) < 12:
        print("PAYMENTOPS_USER_PASSWORD must be at least 12 characters.")
        return None
    return value


async def _run(args: argparse.Namespace) -> int:
    db = Database(get_settings())
    try:
        async for session in db.session():
            if args.command == "list-users":
                users = await user_service.list_users(session)
                for u in users:
                    print(f"{u.email}\t{u.role}\t{u.status}\t{u.organization_id}")
                return 0

            if args.command == "create-user":
                password = _password_from_env()
                if not password:
                    print("Set PAYMENTOPS_USER_PASSWORD (>=12 chars).")
                    return 2
                existing = await user_service.get_user_by_email(session, args.email)
                if existing is not None:
                    print("A user with that email already exists.")
                    return 1
                result = await session.execute(
                    select(Organization).where(Organization.public_id == args.org)
                )
                org = result.scalar_one_or_none()
                if org is None:
                    print(f"Organization '{args.org}' not found.")
                    return 1
                await user_service.create_user(
                    session,
                    organization_id=str(org.id),
                    email=args.email,
                    display_name=args.name or args.email,
                    password=password,
                    role=user_service.UserRole(args.role),
                )
                print(f"Created {args.role} user {args.email} in '{args.org}'.")
                return 0

            user = await user_service.get_user_by_email(session, args.email)
            if user is None:
                print("User not found.")
                return 1

            if args.command == "reset-password":
                password = _password_from_env()
                if not password:
                    print("Set PAYMENTOPS_USER_PASSWORD (>=12 chars).")
                    return 2
                await user_service.set_password(session, user, password)
                print(f"Password reset for {user.email}; all sessions revoked.")
                return 0

            if args.command == "disable-user":
                await user_service.set_status(session, user, user_service.UserStatus.DISABLED)
                print(f"Disabled {user.email}; sessions revoked.")
                return 0

            if args.command == "enable-user":
                await user_service.set_status(session, user, user_service.UserStatus.ACTIVE)
                print(f"Enabled {user.email}.")
                return 0

            if args.command == "set-role":
                await user_service.set_role(session, user, user_service.UserRole(args.role))
                print(f"Set role {args.role} for {user.email}.")
                return 0

            if args.command == "revoke-sessions":
                count = await user_service.revoke_all_sessions(session, str(user.id))
                print(f"Revoked {count} session(s) for {user.email}.")
                return 0
    finally:
        await db.dispose()
    return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="user_admin")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list-users")
    p.add_argument("--org", default=None)

    p = sub.add_parser("create-user")
    p.add_argument("--email", required=True)
    p.add_argument("--name", default=None)
    p.add_argument("--org", required=True)
    p.add_argument("--role", choices=["ADMIN", "OPERATOR", "VIEWER"], default="VIEWER")

    for name in ("reset-password", "disable-user", "enable-user", "revoke-sessions"):
        p = sub.add_parser(name)
        p.add_argument("--email", required=True)

    p = sub.add_parser("set-role")
    p.add_argument("--email", required=True)
    p.add_argument("--role", choices=["ADMIN", "OPERATOR", "VIEWER"], required=True)

    return parser


if __name__ == "__main__":
    sys.exit(asyncio.run(_run(_parser().parse_args())))
