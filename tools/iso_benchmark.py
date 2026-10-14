"""ISO 20022 performance baseline (Task 39).

Measures adapter + validation + correlation latency on synthetic data. DEVELOPMENT BASELINE
only — not a production-scale claim.

Run: python tools/iso_benchmark.py
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path

from address_engine.providers import CloudNovaAddressProvider
from analysis.pipeline import AnalysisPipeline
from iso_engine import build_default_registry
from iso_engine.lifecycle.correlation import CorrelationProfile, correlate_profiles
from iso_engine.xml_security import secure_parse
from iso_engine.xsd_validator import validate_message
from rules_engine import build_address_ruleset

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "iso"
REG = build_default_registry()
PIPELINE = AnalysisPipeline(
    address_provider=CloudNovaAddressProvider(), rules_engine=build_address_ruleset()
)


def _stats(lat: list[float]) -> str:
    return f"p50={statistics.median(lat):.3f}ms p95={sorted(lat)[int(len(lat) * 0.95) - 1]:.3f}ms"


def _timed(fn, n: int) -> list[float]:
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000)
    return out


def main() -> None:
    names = {
        "pain001-00113-valid-single.xml": "pain.001 single",
        "pacs009-00113-valid.xml": "pacs.009",
        "pacs002-00116-accepted.xml": "pacs.002",
        "pacs008-00108-lifecycle.xml": "pacs.008",
    }
    for fname, label in names.items():
        data = (FIXTURES / fname).read_bytes()
        lat = _timed(lambda d=data: PIPELINE.analyze_iso(d, REG), 50)
        print(f"{label}: {_stats(lat)}")

    # correlation
    a = CorrelationProfile(end_to_end_id="E2E-0001", amount=1250000, currency="EUR")
    b = CorrelationProfile(end_to_end_id="E2E-0001", amount=1250000, currency="EUR")
    lat = _timed(lambda: correlate_profiles(a, b), 2000)
    print(f"correlate: {_stats(lat)}")

    # schema validation only
    data = (FIXTURES / "pain001-00113-valid-single.xml").read_bytes()
    doc = secure_parse(data)
    lat = _timed(lambda: validate_message(doc.root, "pain.001.001.13"), 100)
    print(f"pain.001 schema validation: {_stats(lat)}")


if __name__ == "__main__":
    main()
