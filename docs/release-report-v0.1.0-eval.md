# v0.1.0-eval — Evaluation Release Report (50 items)

Product: **CloudNova PaymentOps** · Version: **`0.1.0-eval`** · Tag: **`v0.1.0-eval`**
Scope: controlled bank/fintech PoC readiness. Non-transactional by design.

Legend: ✅ done & verified · 🟡 done with a documented limitation · ⛔ out of scope by design.

## Security (1–12)

1. ✅ Non-transactional boundary documented in product, marketing, and release docs.
2. ✅ Local auth with PBKDF2-HMAC-SHA256, 600,000 iterations, per-user salt.
3. ✅ Server-side opaque sessions (SHA-256 token hash); 8h TTL; revocable.
4. ✅ Lockout after 5 failed logins / 15 minutes; no account enumeration.
5. ✅ CSRF double-submit cookie enforced on mutating proxy requests.
6. ✅ Server-side RBAC (VIEWER/OPERATOR/ADMIN) enforced in the web proxy.
7. ✅ Same-origin backend proxy strips inbound actor/credential headers.
8. ✅ Tenant isolation regression suites pass for cases, batches, profiles, matching, ISO, accounts.
9. ✅ No raw payloads/IBANs/names/addresses/BICs in logs (masking utilities available).
10. ✅ No secrets in images or repo; `.env` gitignored; runtime injection only.
11. ✅ Containers run non-root, drop ALL caps, `readOnlyRootFilesystem`, seccomp `RuntimeDefault`.
12. ✅ Namespace default-deny ingress + targeted NetworkPolicies for web/api/postgres/redis.

## Stability (13–22)

13. ✅ Deterministic validation is the sole source of truth; AI is non-authoritative.
14. ✅ Core functions with `AI_ENABLED=false` (default).
15. ✅ Structured errors for unsupported ISO versions (no stack traces to clients).
16. ✅ XML ingestion hardened (XXE / entity-expansion protections tested).
17. ✅ Idempotent re-analysis (payload-hash dedup); fixed UUID/VARCHAR comparison bug.
18. ✅ pacs.002 status reports now update lifecycle `current_status`.
19. ✅ Out-of-order status reports held as `UNRESOLVED`, then resolve.
20. ✅ Duplicate account entries detected across distinct messages.
21. ✅ Amount mismatches are never silently reconciled.
22. ✅ Frontend build/lint/typecheck/tests pass (35 tests).

## Recovery (23–28)

23. ✅ DB backup via `pg_dump` (custom format) verified.
24. ✅ Isolated restore verified with matching row counts and migration head.
25. ✅ Alembic head `0010_audit_case_nullable`; upgrade/downgrade roundtrip test passes.
26. ✅ Fixed a migration downgrade bug (0003 dropped an index after its column).
27. ✅ GitOps rollback by reverting image pins; no `latest` tags.
28. ✅ Received payloads treated as immutable evidence (ADR-006).

## Operations (29–35)

29. ✅ `/api/v1/info` reports `release`, `version`, `build_sha`, `build_date`.
30. ✅ Build metadata injected at image build time (SHA + timestamp).
31. ✅ User admin CLI: create / reset-password / disable / enable / set-role / revoke-sessions / list.
32. ✅ Auth audit events (`auth.login`, `auth.logout`) with no secrets.
33. ✅ Demo tooling: `seed_demo` (synthetic, idempotent) and `reset_demo` (tenant-scoped, FK-safe).
34. ✅ Operations runbook (deploy/rollback, backup/restore, demo reset, incident response).
35. ✅ Flux GitOps reconciled; api/web/worker pinned to the verified SHA.

## Performance (36–40)

36. ✅ In-process pipeline baseline captured (`docs/performance-baseline.md`).
37. ✅ Steady-state per-message p95 ~1.2–2.7 ms on synthetic fixtures.
38. ✅ Concurrent ×20 (4 workers): 0 failures.
39. 🟡 Large `camt.053` statements are bounded; async large-statement path not fully wired.
40. 🟡 Single-node dev environment only; re-measure before sizing commitments.

## Documentation (41–45)

41. ✅ `docs/RELEASE_NOTES.md` (v0.1.0-eval).
42. ✅ `docs/authentication.md` (auth, RBAC, CSRF, admin CLI, test DB).
43. ✅ `docs/runbooks/operations.md`.
44. ✅ `docs/demo-script.md`.
45. ✅ `docs/poc-package.md` (scope, security questionnaire, sales FAQ, one-pager).

## Demo & PoC readiness (46–50)

46. ✅ Demo tenant `cloudnova-demo-bank` with synthetic scenarios seeded.
47. ✅ Demo users `demo-admin@` / `demo-operator@` / `demo-viewer@cloudnova.tech`.
48. ✅ Live RBAC verified: operator→admin endpoint 403; viewer→mutating 403; reads 200.
49. ✅ Marketing claim review: non-transactional boundary and non-authoritative AI stated; no
   certification claims; no prohibited claims found.
50. ✅ CI gates green: backend (with real PostgreSQL + migrations), frontend, and security scans.

## Recommendation

**CONDITIONAL GO** for controlled bank/fintech PoC outreach under these conditions:

- Keep the scope to the six supported ISO versions and non-transactional workflows.
- Keep the AI layer disabled (or explicitly non-authoritative) for regulated audiences.
- Use per-customer integration profiles; no codebase forks.
- Provision demo credentials out-of-band and rotate them per engagement.
- Re-measure performance in the target environment and confirm data-residency/retention needs.
- Treat the documented limitations (proxy-level RBAC, subset XSDs, bounded camt ingest,
  camt-first non-retroactive linking, single operator tenant) as explicit PoC constraints.

No unrestricted public SaaS: the release is ready for **controlled** evaluation only.
