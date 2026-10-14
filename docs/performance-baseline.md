# Performance Baseline (evaluation)

These numbers are a **baseline for the evaluation release**, not a performance guarantee. They
were captured on a single-node K3s development cluster / local runner using synthetic fixtures.
Re-measure in the target environment before making any sizing commitments.

## Pipeline throughput (in-process, `tests/perf_baseline.py`)

Command:

```bash
python tests/perf_baseline.py
```

| Scenario | n | p50 | p95 | max |
| --- | --- | --- | --- | --- |
| Single valid pacs.008 (cold) | 1 | 25.61 ms | 25.61 ms | 25.61 ms |
| Single invalid pacs.008 | 1 | 2.14 ms | 2.14 ms | 2.14 ms |
| Single address-provider case | 1 | 2.17 ms | 2.17 ms | 2.17 ms |
| 10 sequential valid | 10 | 1.30 ms | 2.53 ms | 3.80 ms |
| 100 sequential valid | 100 | 1.19 ms | 2.65 ms | 3.70 ms |
| Concurrent ×20 (4 workers) | 20 | — | — | 28.77 ms total, 0 failures |

Notes:

- The first "single valid" call includes one-time warm-up (schema/registry loading); steady-state
  per-message latency is ~1.2–2.7 ms p95 for the analyzed fixtures.
- Measurements cover the deterministic analysis pipeline (validation, address structuring, repair
  candidate generation) in-process, excluding network and database I/O.

## Caveats

- Bounded by the single-node development environment.
- Fixtures are small single-transaction messages; large `camt.053` statements are ingested with a
  bounded transaction limit and are not represented here.
- Not a capacity claim. Use the target environment and representative payloads for sizing.
