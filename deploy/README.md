# Deployment

Purpose-built deployment helpers for CloudNova PaymentOps.

- `../docker-compose.yml` — local development orchestration (PostgreSQL, Redis, API, web,
  worker). Kubernetes is the production target; Docker Compose is for local iteration only.
- Kubernetes / GitOps manifests live in the **homeserver** repository under
  `clusters/loudnova/apps/paymentops/` (Flux-managed, Envoy Gateway routing). See
  `../docs/architecture/overview.md` and ADR-009.
- Images are produced by the `apps/*/Dockerfile` (multi-stage, non-root) and published via
  CI to a container registry (see `.github/workflows/ci.yml`).
