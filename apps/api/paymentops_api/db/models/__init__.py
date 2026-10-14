"""Declarative base shared by all ORM models, plus model module imports and re-exports.

``Base`` must be defined before the model modules are imported (they import ``Base`` from
this package). Importing the model modules registers all tables on ``Base.metadata``.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all PaymentOps ORM models."""


# Import model modules so their tables register on Base.metadata (used by Alembic).
from paymentops_api.db.models import account as _account  # noqa: E402,F401
from paymentops_api.db.models import analysis as _analysis  # noqa: E402,F401
from paymentops_api.db.models import auth as _auth  # noqa: E402,F401
from paymentops_api.db.models import integration as _integration  # noqa: E402,F401
from paymentops_api.db.models import investigation as _investigation  # noqa: E402,F401
from paymentops_api.db.models import lifecycle as _lifecycle  # noqa: E402,F401
from paymentops_api.db.models import matching as _matching  # noqa: E402,F401
from paymentops_api.db.models import platform as _platform  # noqa: E402,F401
from paymentops_api.db.models.account import (  # noqa: E402
    AccountBalanceRow,
    AccountEntryRow,
    AccountReconciliationRow,
    AccountReportRow,
)
from paymentops_api.db.models.analysis import (  # noqa: E402
    AnalysisRun,
    AuditEvent,
    PaymentCase,
    RepairCandidate,
    RuleFinding,
)
from paymentops_api.db.models.auth import AppUser, UserSession  # noqa: E402
from paymentops_api.db.models.integration import (  # noqa: E402
    ApiClient,
    BatchJob,
    CaseAction,
    IntegrationProfile,
    IntegrationProfileVersion,
)
from paymentops_api.db.models.investigation import Investigation  # noqa: E402
from paymentops_api.db.models.lifecycle import (  # noqa: E402
    IsoMessage,
    MessageCorrelation,
    PaymentLifecycleEventRow,
    PaymentLifecycleRow,
)
from paymentops_api.db.models.matching import (  # noqa: E402
    MatchCandidate,
    MatchingPolicyRow,
    MatchingPolicyVersion,
    MatchRecordRow,
    MatchRun,
)
from paymentops_api.db.models.platform import AppMetadata, Organization  # noqa: E402

__all__ = [
    "AccountBalanceRow",
    "AccountEntryRow",
    "AccountReconciliationRow",
    "AccountReportRow",
    "AnalysisRun",
    "ApiClient",
    "AppMetadata",
    "AppUser",
    "AuditEvent",
    "Base",
    "BatchJob",
    "CaseAction",
    "IntegrationProfile",
    "IntegrationProfileVersion",
    "Investigation",
    "IsoMessage",
    "MatchCandidate",
    "MatchingPolicyRow",
    "MatchingPolicyVersion",
    "MatchRecordRow",
    "MatchRun",
    "MessageCorrelation",
    "Organization",
    "PaymentCase",
    "PaymentLifecycleEventRow",
    "PaymentLifecycleRow",
    "RepairCandidate",
    "RuleFinding",
    "UserSession",
]
