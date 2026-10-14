"""Application metrics.

Low-cardinality labels only. Never label with IBANs, names, message IDs, account numbers, or
case IDs. Labels are limited to status, message_type, rule_category, and provider.
"""

from __future__ import annotations

import time

from prometheus_client import Counter, Histogram

from address_engine.base import AddressAnalysis, AddressProvider
from payment_domain.models import PostalAddress

analysis_total = Counter(
    "paymentops_analysis_total",
    "Total payment analyses",
    ("status", "message_type"),
)
analysis_duration = Histogram(
    "paymentops_analysis_duration_seconds",
    "Payment analysis duration",
    ("message_type",),
)
validation_failures_total = Counter(
    "paymentops_validation_failures_total",
    "Total XSD/validation failures",
    ("message_type",),
)
rule_findings_total = Counter(
    "paymentops_rule_findings_total",
    "Total rule findings",
    ("rule_category", "severity"),
)
address_resolution_total = Counter(
    "paymentops_address_resolution_total",
    "Address resolution outcomes",
    ("readiness",),
)
repair_candidates_total = Counter(
    "paymentops_repair_candidates_total",
    "Repair candidates generated",
    ("status",),
)

# Address-provider metrics. Labels limited to provider + status; never addresses/towns/IBANs.
address_provider_requests_total = Counter(
    "paymentops_address_provider_requests_total",
    "Address provider requests",
    ("provider", "status"),
)
address_provider_failures_total = Counter(
    "paymentops_address_provider_failures_total",
    "Address provider failures",
    ("provider",),
)
address_provider_fallback_total = Counter(
    "paymentops_address_provider_fallback_total",
    "Address provider fallbacks",
    ("provider",),
)
address_provider_duration = Histogram(
    "paymentops_address_provider_duration_seconds",
    "Address provider request duration",
    ("provider",),
)

# Week 3 metrics (low-cardinality labels: status/format/category only).
profile_analysis_total = Counter(
    "paymentops_profile_analysis_total",
    "Profile-resolved analyses",
    ("status", "format"),
)
mapping_failures_total = Counter(
    "paymentops_mapping_failures_total",
    "Mapping failures",
    ("category",),
)
batch_jobs_total = Counter(
    "paymentops_batch_jobs_total",
    "Batch jobs",
    ("status",),
)
batch_records_total = Counter(
    "paymentops_batch_records_total",
    "Batch records processed",
    ("status",),
)
cases_total = Counter(
    "paymentops_cases_total",
    "PaymentOps cases",
    ("status",),
)
case_actions_total = Counter(
    "paymentops_case_actions_total",
    "Case actions",
    ("action",),
)

# Week 4 matching metrics (low-cardinality labels: classification/status/record_type only).
# NEVER label with IBANs, record ids, names, or references.
match_evaluations_total = Counter(
    "paymentops_match_evaluations_total",
    "Match pair evaluations",
    ("classification",),
)
match_duration = Histogram(
    "paymentops_match_duration_seconds",
    "Match evaluation duration",
    ("classification",),
)
match_classifications_total = Counter(
    "paymentops_match_classifications_total",
    "Match classifications produced",
    ("classification", "record_type"),
)
match_candidate_count = Histogram(
    "paymentops_match_candidate_count",
    "Candidates returned per search",
    ("record_type",),
)
reconciliation_jobs_total = Counter(
    "paymentops_reconciliation_jobs_total",
    "Reconciliation jobs",
    ("status",),
)

# Week 5 ISO lifecycle metrics (low-cardinality labels: family/definition/version/status only).
# NEVER label with message ids, IBANs, names, or references.
iso_messages_total = Counter(
    "paymentops_iso_messages_total",
    "ISO messages analyzed",
    ("family", "version", "status"),
)
iso_validation_failures_total = Counter(
    "paymentops_iso_validation_failures_total",
    "ISO schema validation failures",
    ("family", "version"),
)
iso_adapter_duration = Histogram(
    "paymentops_iso_adapter_duration_seconds",
    "ISO adapter duration",
    ("family", "version"),
)
lifecycle_correlations_total = Counter(
    "paymentops_lifecycle_correlations_total",
    "Lifecycle correlations",
    ("status", "family"),
)
lifecycle_events_total = Counter(
    "paymentops_lifecycle_events_total",
    "Lifecycle events",
    ("event_type",),
)
iso_unsupported_versions_total = Counter(
    "paymentops_iso_unsupported_versions_total",
    "Unsupported ISO versions rejected",
    ("family",),
)

# Week 6 account-reporting metrics (low-cardinality labels only).
account_reports_total = Counter(
    "paymentops_account_reports_total",
    "Account reports ingested",
    ("report_type", "version"),
)
account_entries_total = Counter(
    "paymentops_account_entries_total",
    "Account entries ingested",
    ("credit_debit",),
)
account_reconciliations_total = Counter(
    "paymentops_account_reconciliations_total",
    "Account reconciliations",
    ("classification",),
)
missing_account_events_total = Counter(
    "paymentops_missing_account_events_total",
    "Missing account events detected",
    (),
)

# Phase 1 investigation metrics (low-cardinality labels only: status/result).
# NEVER label with case refs, execution ids, rule ids, or payload data.
investigations_total = Counter(
    "paymentops_investigations_total",
    "Investigation operations",
    ("status",),
)
evolus_workflow_runs_total = Counter(
    "paymentops_evolus_workflow_runs_total",
    "Evolus workflow runs started",
    ("status",),
)
tool_validations_total = Counter(
    "paymentops_tool_validations_total",
    "Validation tool invocations",
    ("result",),
)


class MetricAddressProvider(AddressProvider):
    """Wraps an :class:`AddressProvider`, recording low-cardinality metrics per request.

    Labels: provider + status only. Never address/town/country/case data.
    """

    def __init__(self, provider: AddressProvider, *, label: str) -> None:
        self._provider = provider
        self._label = label
        self.name = provider.name
        self.version = provider.version

    def analyze(self, address: PostalAddress) -> AddressAnalysis:
        start = time.perf_counter()
        try:
            result = self._provider.analyze(address)
            status = "fallback" if result.fallback else "ok"
            address_provider_requests_total.labels(provider=self._label, status=status).inc()
            if result.fallback:
                address_provider_fallback_total.labels(provider=self._label).inc()
            return result
        except Exception:
            address_provider_requests_total.labels(provider=self._label, status="error").inc()
            address_provider_failures_total.labels(provider=self._label).inc()
            raise
        finally:
            address_provider_duration.labels(provider=self._label).observe(
                time.perf_counter() - start
            )
