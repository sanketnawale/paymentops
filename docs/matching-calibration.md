# Matching Threshold Calibration

**Status: DEVELOPMENT BASELINE — NOT production-ready.**

These thresholds were established against a small synthetic dataset in Week 4. They are a
starting point only. They MUST be re-validated against customer historical data before any
production use, and the `MatchingPolicy` version should be bumped and republished whenever
they change.

## Weighted score

`match_score = 100 * sum(weight_i * similarity_i) / sum(weight_i)` over compared fields.

`match_score` is a bounded, deterministic score (0..100). It is **NOT a probability** and must
never be labelled as one (a calibrated model would be required to claim probability).

## Thresholds (default policy)

| Threshold | Value | Meaning |
|-----------|-------|---------|
| `matched` | 85 | score >= 85 and no critical conflict -> MATCHED |
| `possible_match` | 60 | score >= 60 and no critical conflict -> POSSIBLE_MATCH |
| `review` | 40 | score >= 40 and no critical conflict -> REVIEW_REQUIRED |
| below `review` | < 40 | UNMATCHED |

Critical conflicts (currency, amount, transaction_id, account, hard party-name mismatch)
override the score: they force `REVIEW_REQUIRED` (score >= 40) or `UNMATCHED` (score < 40),
never a blind `MATCHED`.

## Why these thresholds

- The synthetic exact-match cases score ~97 (high-weight identifiers + amount + currency all
  exact), comfortably above `matched` = 85.
- Punctuation/legal-form name variants score ~97-100 on the name field, so they do not block.
- A genuinely different company (`ACME INDUSTRIA SPA` vs `ACME LOGISTICS SRL`) has a name
  similarity of ~61, which is below the name-mismatch signal of 70 and therefore routed to
  review rather than auto-matched.

## False-positive examples observed

- `ACME INDUSTRIA SPA` vs `ACME LOGISTICS SRL` with identical reference+amount+currency scored
  92 but was correctly forced to `REVIEW_REQUIRED` by the name-mismatch signal (this is the
  intended false-positive guard).
- Two records sharing only amount+currency (but differing everywhere else) scored ~45-55, i.e.
  in the `REVIEW_REQUIRED` band — acceptable ambiguity, but means amount+currency alone are
  insufficient to auto-match.

## False-negative examples observed

- A record with a materially different `value_date` (> 3 days) but otherwise matching reference
  + amount + currency still auto-matches (score ~90) because date weight is only 5. This is
  intentional: date is a weak signal. If customers need stricter date behaviour, increase the
  `value_date`/`booking_date` weight or reduce the `date_tolerances` window in the policy.

## Name-mismatch signal

A party-name similarity below **70** (when both names are present) is treated as a critical
conflict and routed to `REVIEW_REQUIRED`. Tuned so legal-form variants pass and genuine company
changes are reviewed.

## Next steps before production

1. Collect customer historical matched/unmatched pairs.
2. Re-calibrate thresholds; bump and republish the `MatchingPolicy` version.
3. Record the dataset and methodology in a follow-up ADR.
