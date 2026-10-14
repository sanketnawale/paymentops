"""Address provider abstraction.

The rest of PaymentOps depends only on :class:`AddressProvider`; it never depends on any
provider's implementation details (e.g. Swift-specific internals). Providers return
evidence-based results; there is no fabricated numeric confidence.

Providers:
- ``CloudNovaAddressProvider``  : deterministic normalization + readiness (default)
- ``SwiftDerivedAddressProvider`` : isolated adapter over a separately-containerized Swift
  town/country inference component (optional; not enabled in Week 2)
- future: ``CustomerProvidedAddressProvider``
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from payment_domain.models import AddressReadiness, EvidenceLevel, PostalAddress


@dataclass(frozen=True)
class AddressAnalysis:
    """Deterministic, evidence-based result of analyzing a postal address."""

    provider: str
    provider_version: str
    # Resolved candidate values (normalized).
    country_code: str | None = None
    country_name: str | None = None
    town_name: str | None = None
    postcode: str | None = None
    street_name: str | None = None
    building_number: str | None = None
    normalized_fields: dict[str, str] = field(default_factory=dict)
    # Readiness classification.
    readiness: AddressReadiness = AddressReadiness.UNRESOLVED
    evidence_level: EvidenceLevel = EvidenceLevel.LOW
    # Provider availability / confidence.
    available: bool = True
    note: str | None = None
    # Set when the primary provider was unavailable and a fallback was used.
    fallback: bool = False
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "provider_version": self.provider_version,
            "country_code": self.country_code,
            "country_name": self.country_name,
            "town_name": self.town_name,
            "postcode": self.postcode,
            "street_name": self.street_name,
            "building_number": self.building_number,
            "normalized_fields": self.normalized_fields,
            "readiness": self.readiness.value,
            "evidence_level": self.evidence_level.value,
            "available": self.available,
            "note": self.note,
            "fallback": self.fallback,
            "evidence": self.evidence,
        }


class AddressProvider(ABC):
    """Interface every address provider implements."""

    name: str = ""
    version: str = ""

    @abstractmethod
    def analyze(self, address: PostalAddress) -> AddressAnalysis:
        raise NotImplementedError

    @property
    def description(self) -> str:
        return f"{self.name} (v{self.version})"
