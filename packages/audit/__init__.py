"""Audit package boundary.

Responsibility (planned): immutable, tenant-scoped audit trail of validation decisions,
corrections, and human approvals. No real audit persistence in Week 1.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class IAuditSink(ABC):
    @abstractmethod
    async def record(
        self, event: str, organization_id: str | None, occurred_at: datetime | None = None
    ) -> None:
        """Persist an audit event. Must always be tenant-scoped."""
        raise NotImplementedError
