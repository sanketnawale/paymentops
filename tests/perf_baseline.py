"""Rough performance baseline (not a claim; baseline data only).

Measures pipeline throughput for a single valid/invalid message, an address-provider-heavy
case, and 10/100 sequential analyses, plus modest concurrency.
"""

from __future__ import annotations

import concurrent.futures
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import load_fixture

from address_engine.providers import CloudNovaAddressProvider
from analysis import AnalysisPipeline
from rules_engine import build_address_ruleset


def make_pipeline() -> AnalysisPipeline:
    return AnalysisPipeline(
        address_provider=CloudNovaAddressProvider(),
        rules_engine=build_address_ruleset(),
    )


def run(pipeline: AnalysisPipeline, fixture: bytes, n: int = 1) -> list[float]:
    times: list[float] = []
    for _ in range(n):
        start = time.perf_counter()
        pipeline.analyze(fixture, repair=True)
        times.append((time.perf_counter() - start) * 1000)
    return times


def report(name: str, times: list[float]) -> None:
    p50 = statistics.median(times)
    p95 = sorted(times)[int(len(times) * 0.95) - 1] if len(times) > 1 else times[0]
    print(f"{name}: n={len(times)} p50={p50:.2f}ms p95={p95:.2f}ms max={max(times):.2f}ms")


def main() -> None:
    pipeline = make_pipeline()
    valid = load_fixture("valid_structured")
    invalid = load_fixture("country_full_name")
    address_heavy = load_fixture("address_adrline_only")

    report("single valid", run(pipeline, valid, 1))
    report("single invalid", run(pipeline, invalid, 1))
    report("single address-provider case", run(pipeline, address_heavy, 1))

    report("10 sequential valid", run(pipeline, valid, 10))
    report("100 sequential valid", run(pipeline, valid, 100))

    failures = 0
    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(pipeline.analyze, valid, repair=True) for _ in range(20)]
        for f in concurrent.futures.as_completed(futures):
            try:
                f.result()
            except Exception:  # noqa: BLE001
                failures += 1
    elapsed = (time.perf_counter() - start) * 1000
    print(f"concurrent x20 (4 workers): total={elapsed:.2f}ms failures={failures}")


if __name__ == "__main__":
    main()
