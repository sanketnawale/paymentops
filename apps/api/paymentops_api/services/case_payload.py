"""Load the immutable payload and evidence for an investigation (demo fixture or upload).

Kept in a small neutral module so both the investigation service and the repair service can use
it without a circular import.
"""

from __future__ import annotations

import base64

from paymentops_api.db.models import Investigation
from paymentops_api.evolus.demo_cases import SupportingRecord, get_demo_case, record_from_stored


def load_payload(inv: Investigation) -> bytes:
    """Return the immutable payload bytes for an investigation (demo fixture or upload)."""
    if inv.source == "upload":
        if not inv.payload_xml:
            raise LookupError(inv.investigation_id)
        return base64.b64decode(inv.payload_xml)
    return get_demo_case(inv.demo_case_key).load()


def load_record(inv: Investigation) -> SupportingRecord | None:
    """Return the supporting evidence record for an investigation, if any."""
    if inv.source == "upload":
        return record_from_stored(inv.payload_evidence)
    return get_demo_case(inv.demo_case_key).supporting_record


def case_origin(inv: Investigation) -> str:
    if inv.source == "upload":
        return "user-uploaded synthetic payload"
    return get_demo_case(inv.demo_case_key).origin


def synthetic_input_preview(inv: Investigation) -> str | None:
    """A display preview of the synthetic payload (never raises)."""
    try:
        return load_payload(inv).decode("utf-8", errors="replace")
    except LookupError:
        return None
