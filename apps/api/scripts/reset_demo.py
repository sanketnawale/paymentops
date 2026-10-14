"""Reset ONLY the CloudNova Demo Bank tenant's operational data.

Deletes demo-tenant rows from every organization-scoped table in foreign-key-safe order.
It never touches other tenants, platform configuration, or (by default) identities/users.

    python -m scripts.reset_demo --yes
    python -m scripts.reset_demo --org cloudnova-demo-bank --yes --delete-users
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from paymentops_api.db.base import Database
from paymentops_api.settings import get_settings
from sqlalchemy import text

# Identity/platform tables are preserved unless --delete-users is passed.
PROTECTED = {"organizations", "api_clients", "app_users", "user_sessions"}


async def _load_graph(conn) -> tuple[list[str], list[tuple[str, str]]]:
    tables = [
        r[0]
        for r in (
            await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.columns "
                    "WHERE column_name='organization_id' AND table_schema='public'"
                )
            )
        ).all()
    ]
    edges = [
        (r[0], r[1])
        for r in (
            await conn.execute(
                text(
                    "SELECT tc.table_name AS child, ccu.table_name AS parent "
                    "FROM information_schema.table_constraints tc "
                    "JOIN information_schema.constraint_column_usage ccu "
                    "  ON tc.constraint_name = ccu.constraint_name "
                    "WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_schema='public'"
                )
            )
        ).all()
    ]
    return tables, edges


def _deletion_order(tables: list[str], edges: list[tuple[str, str]]) -> list[str]:
    """Topologically sort so children are deleted before parents (edge child -> parent)."""
    nodes = set(tables)
    children_of = {t: set() for t in tables}
    for child, parent in edges:
        if child in nodes and parent in nodes and child != parent:
            children_of[parent].add(child)
    order: list[str] = []
    remaining = set(tables)
    while remaining:
        ready = sorted(t for t in remaining if not (children_of[t] & remaining))
        if not ready:  # cycle: fall back to alphabetical for the rest
            ready = sorted(remaining)
        for t in ready:
            order.append(t)
            remaining.discard(t)
    return order


async def _reset(org_public_id: str, delete_users: bool) -> int:
    db = Database(get_settings())
    try:
        async for session in db.session():
            org_id = (
                await session.execute(
                    text("SELECT id FROM organizations WHERE public_id=:p"),
                    {"p": org_public_id},
                )
            ).scalar_one_or_none()
            if org_id is None:
                print(f"Organization '{org_public_id}' not found.")
                return 1

            tables, edges = await _load_graph(await session.connection())
            targets = [t for t in tables if delete_users or t not in PROTECTED]
            order = _deletion_order(targets, edges)

            for table in order:
                result = await session.execute(
                    text(f'DELETE FROM "{table}" WHERE organization_id = :org'),  # noqa: S608
                    {"org": org_id},
                )
                if result.rowcount:
                    print(f"  {table}: {result.rowcount}")
            await session.commit()
            print(f"Demo tenant '{org_public_id}' reset complete.")
            return 0
    finally:
        await db.dispose()
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="reset_demo")
    parser.add_argument("--org", default="cloudnova-demo-bank")
    parser.add_argument("--delete-users", action="store_true")
    parser.add_argument("--yes", action="store_true", help="required confirmation")
    args = parser.parse_args()
    if not args.yes:
        print("Refusing to delete without --yes.")
        sys.exit(2)
    sys.exit(asyncio.run(_reset(args.org, args.delete_users)))
