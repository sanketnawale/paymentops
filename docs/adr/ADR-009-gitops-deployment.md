# ADR-009: Kubernetes + GitOps deployment model

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

The existing CloudNova platform is deployed via Flux GitOps into a Kubernetes cluster. The
application should follow the same model rather than inventing a new deployment system.

## Decision

- **Deploy via Kubernetes + Flux GitOps**, reusing the existing cluster (Envoy Gateway,
  `base/` + `overlays/<env>` conventions).
- GitOps manifests live in the **homeserver** repository, not the application repository
  (application repo keeps Dockerfiles + CI that produces images).
- Environments: `paymentops-dev`, `paymentops-test`, `paymentops-demo`. No `prod` yet.
- Kubernetes is the deployment target; Docker Compose is local iteration only.

## Consequences

- Aligns with existing platform conventions; no separate infrastructure repo created.
- Image flow: CI builds→publishes image→GitOps references a pinned image (no `latest`).
- Cluster constraints (single node) are documented; HA is structured where feasible.
