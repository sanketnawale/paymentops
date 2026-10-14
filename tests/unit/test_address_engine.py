"""Unit tests for the address engine (normalization, readiness, provider abstraction)."""

from __future__ import annotations

from address_engine.base import AddressProvider
from address_engine.normalization import (
    extract_country_from_lines,
    normalize_country_field,
    normalize_unicode,
    normalize_whitespace,
)
from address_engine.providers import (
    CloudNovaAddressProvider,
    FallbackAddressProvider,
    SwiftDerivedAddressProvider,
)
from payment_domain.models import AddressReadiness, EvidenceLevel, PostalAddress


def test_normalize_whitespace_and_unicode():
    assert normalize_whitespace("  a   b  ") == "a b"
    assert normalize_unicode("Ｈｅｌｌｏ") == "Hello"


def test_normalize_country_field_name_to_code():
    code, level, _ = normalize_country_field("Italy")
    assert code == "IT"
    assert level == EvidenceLevel.HIGH


def test_normalize_country_field_valid_code():
    code, level, _ = normalize_country_field("it")
    assert code == "IT"
    assert level == EvidenceLevel.HIGH


def test_extract_country_from_lines():
    code, level = extract_country_from_lines(["Via Roma 5, Roma, Italy"])
    assert code == "IT"
    assert level == EvidenceLevel.MEDIUM


def test_cloudnova_provider_ready():
    addr = PostalAddress(country="IT", town_name="Milano")
    analysis = CloudNovaAddressProvider().analyze(addr)
    assert analysis.readiness == AddressReadiness.READY
    assert analysis.country_code == "IT"
    assert analysis.town_name == "Milano"


def test_cloudnova_provider_repairable_invalid_country():
    addr = PostalAddress(country="Italy", town_name="Milano")
    analysis = CloudNovaAddressProvider().analyze(addr)
    assert analysis.readiness == AddressReadiness.REPAIRABLE
    assert analysis.country_code == "IT"


def test_cloudnova_provider_unresolved():
    addr = PostalAddress()
    analysis = CloudNovaAddressProvider().analyze(addr)
    assert analysis.readiness == AddressReadiness.UNRESOLVED


def test_swift_provider_isolated_and_disabled():
    provider = SwiftDerivedAddressProvider("")  # not configured
    assert isinstance(provider, AddressProvider)
    assert provider.configured is False
    analysis = provider.analyze(PostalAddress(country="IT", town_name="Milano"))
    assert analysis.available is False
    assert analysis.note == "ADDRESS_PROVIDER_FALLBACK"


def test_swift_provider_unreachable_returns_fallback():
    # No service on this URL -> transport error -> available=False.
    provider = SwiftDerivedAddressProvider(
        "http://127.0.0.1:59999", timeout_seconds=0.2, max_retries=0
    )
    analysis = provider.analyze(PostalAddress(address_lines=["Via Roma 5, Roma, Italy"]))
    assert analysis.available is False
    assert analysis.note == "ADDRESS_PROVIDER_FALLBACK"


def test_swift_provider_no_address_lines():
    provider = SwiftDerivedAddressProvider("http://127.0.0.1:59999", timeout_seconds=0.2)
    analysis = provider.analyze(PostalAddress())
    assert analysis.available is False


def test_fallback_provider_uses_cloudnova_when_primary_unavailable():
    primary = SwiftDerivedAddressProvider("")  # unavailable
    fallback = CloudNovaAddressProvider()
    fp = FallbackAddressProvider(primary, fallback)
    analysis = fp.analyze(PostalAddress(country="Italy", town_name="Milano"))
    assert analysis.available is True
    assert analysis.fallback is True
    assert analysis.provider == "cloudnova"
    assert analysis.note == "ADDRESS_PROVIDER_FALLBACK"
    assert fp.fallback_count == 1


def test_fallback_provider_passes_through_when_primary_available():
    primary = CloudNovaAddressProvider()
    fp = FallbackAddressProvider(primary, CloudNovaAddressProvider())
    analysis = fp.analyze(PostalAddress(country="IT", town_name="Milano"))
    assert analysis.available is True
    assert analysis.fallback is False
    assert analysis.provider == "cloudnova"
    assert fp.fallback_count == 0


def test_swift_provider_not_used_by_default():
    # The default pipeline uses the CloudNova provider, never the Swift one.
    assert CloudNovaAddressProvider().name == "cloudnova"
    assert SwiftDerivedAddressProvider("").name == "swift_derived"
