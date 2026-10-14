"""Matching performance baseline (Task 30).

Measures deterministic match evaluation latency and throughput on synthetic data. This is a
DEVELOPMENT BASELINE on local hardware — not a production-scale claim.

Run: python tools/match_benchmark.py
"""

from __future__ import annotations

import statistics
import time
from decimal import Decimal

from matching_engine import MatchRecord, RecordType, default_policy, evaluate_pair

POLICY = default_policy("org-bench")


def _rec(rid: str, ref: str, amount: str, cname: str, i: int) -> MatchRecord:
    return MatchRecord(
        record_id=rid,
        record_type=RecordType.PAYMENT,
        organization_id="org-bench",
        amount=Decimal(amount),
        currency="EUR",
        remittance_reference=ref,
        creditor_name=cname,
        debtor_account=f"IT60X0542811{i:08d}",
    )


def _timed(fn, n: int) -> tuple[list[float], float]:
    latencies: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        latencies.append((time.perf_counter() - t0) * 1000)  # ms
    return latencies, sum(latencies)


def _stats(latencies: list[float]) -> str:
    return (
        f"p50={statistics.median(latencies):.3f}ms "
        f"p95={sorted(latencies)[int(len(latencies) * 0.95) - 1]:.3f}ms "
        f"mean={statistics.mean(latencies):.3f}ms"
    )


def main() -> None:
    a = _rec("a", "INV-92881", "12500", "ACME INDUSTRIA SPA", 1)
    b = _rec("b", "INV92881", "12500", "ACME INDUSTRIA S.P.A.", 1)

    lat, total = _timed(lambda: evaluate_pair(a, b, POLICY), 200)
    print(f"single pair (200 runs): {_stats(lat)}  throughput={200 / (total / 1000):.0f}/s")

    candidates = [_rec(f"c{i}", "INV92881", "12500", "ACME INDUSTRIA SPA", i) for i in range(100)]
    lat, total = _timed(lambda: [evaluate_pair(a, c, POLICY) for c in candidates], 10)
    print(f"100 candidate comparisons (10 runs): {_stats(lat)}")

    candidates1k = [_rec(f"c{i}", f"INV{i}", "12500", "ACME INDUSTRIA SPA", i) for i in range(1000)]
    lat, total = _timed(lambda: [evaluate_pair(a, c, POLICY) for c in candidates1k], 3)
    print(f"1000 candidate comparisons (3 runs): {_stats(lat)}")

    sources = [_rec(f"s{i}", f"INV-{i}", "12500", "ACME INDUSTRIA SPA", i) for i in range(100)]
    lat, total = _timed(
        lambda: [evaluate_pair(s, candidates1k[i % 1000], POLICY) for i, s in enumerate(sources)],
        3,
    )
    print(f"100-source reconciliation (3 runs): {_stats(lat)}")


if __name__ == "__main__":
    main()
