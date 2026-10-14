# Phase 2A — Isolated PaymentOps hackathon deployment (Hetzner k3s)

This document covers deploying the **paymentops-amd** hackathon application into the Hetzner
`hetzner-dr` k3s cluster under the isolated namespace **`paymentops-hackathon`**, and its
rollback. It does not touch the business application or any shared infrastructure.

> **Status: prepared and validated, but NOT yet deployed.** Two external dependencies block
> the image supply (see [Blockers](#blockers)). Manifests render cleanly offline; both images
> build clean for `linux/arm64`.

## 1. Cluster facts (observed, `--kubeconfig $HOME\.kube\hetzner-dr.yaml`)

| Item | Value |
| --- | --- |
| Context | `hetzner-dr` |
| API server | `https://65.21.241.211:6443` |
| Node | `hetzner-dr-01` (control-plane, k3s `v1.36.3+k3s1`, **arm64**, Ubuntu 24.04) |
| Capacity | 2 vCPU, ~3.8 GiB memory; **~85% memory already in use** |
| StorageClass | `local-path` (default) |
| Ingress | Envoy Gateway `public-gateway` (ns `gateway-infra`), HTTP listener only |
| External/TLS | **Cloudflare Tunnel** (`cloudflare/cloudflared`) + Cloudflare-managed TLS/DNS |
| GitOps | Flux (`clusters/hetzner-dr`, source `ssh://git@github.com/sanketnawale/loudnova-infra` @ `main`) |
| Registry | `ghcr.io` (existing apps use `ghcr.io/sanketnawale/*` and `ghcr.io/cloodnova/*`) |

**Finding:** the business PaymentOps application is **not** deployed on `hetzner-dr`. The only
PaymentOps workload here is the marketing site `paymentops-site/paymentops-website`. The
business API/web/DB manifests live under `clusters/loudnova/apps/paymentops` (a different
cluster). We therefore mirror those conventions without touching them.

## 2. Architecture deployed

Namespace `paymentops-hackathon` (label `platform.cloudnova.tech/public-routes: "true"`):

| Component | Resource | Notes |
| --- | --- | --- |
| API | Deployment + Service `paymentops-hackathon-api` (:8000) | FastAPI; `/health`, `/ready` |
| Web | Deployment + Service `paymentops-hackathon-web` (:80 → 3000) | Next.js standalone; `/api/health` |
| PostgreSQL | Deployment + Service + PVC (2 Gi, `local-path`) | Isolated DB `paymentops_hackathon` |
| Migrations | Job `paymentops-hackathon-migrate` | `alembic upgrade head` → `0011_investigations` |
| Demo seed | Job `paymentops-hackathon-seed` | Org + operator client + admin user (idempotent) |
| Governance | ResourceQuota, LimitRange, NetworkPolicy | deny-all ingress + explicit allows |

**Intentionally not deployed:** worker, Redis, and the optional `address-structuring` service.
The investigation demo runs synchronously in the API; the deterministic address provider
(`CloudNovaAddressProvider`) is used, so those components are unnecessary. `READY_CHECKS=database`.

Resources are sized for the tight node (requests: API 50m/128Mi, Web 30m/96Mi, Postgres
50m/128Mi; single replicas; `Recreate` strategy to avoid surge pods).

## 3. Files

### `paymentops-amd` (application)
- `apps/api/scripts/seed_hackathon.py` — idempotent demo org + operator client + admin seed.
- `apps/api/paymentops_api/services/investigation_service.py` — added `start_workflow` flag
  (prepare-only investigations that never start the Evolus workflow).
- `apps/api/paymentops_api/routers/investigations.py` — `POST /api/v1/investigations` accepts
  `{"demo_case_key": "...", "start_workflow": false}`.
- `apps/web/lib/api.ts`, `apps/web/app/investigations/[id]/page.tsx` — `start_workflow` + the
  `PREPARED` state.
- Tests: `tests/security/test_validation_tool.py` (`test_prepare_only_does_not_start_workflow`).

### `homeserver` (GitOps) — `clusters/hetzner-dr`
- `apps/paymentops-hackathon/base/*` and `apps/paymentops-hackathon/overlays/dr/*`.
- `flux-system/paymentops-hackathon.yaml` (+ entry in `flux-system/kustomization.yaml`).

## 4. Images (immutable tags)

Names: `ghcr.io/sanketnawale/paymentops-hackathon-api` and `…-web`. The overlay pins tags via
`images: newTag` in `overlays/dr/kustomization.yaml` (placeholder `sha-pending0001`).

Build (arm64 required — the node is arm64):

```powershell
docker buildx build --platform linux/arm64 --push `
  -f apps/api/Dockerfile -t ghcr.io/sanketnawale/paymentops-hackathon-api:<TAG> .
docker buildx build --platform linux/arm64 --push `
  -f apps/web/Dockerfile -t ghcr.io/sanketnawale/paymentops-hackathon-web:<TAG> apps/web
```

Both images were verified to build clean for `linux/arm64` locally (build-cache only; not
pushed). Replace `<TAG>` in the overlay with the published tag/digest before applying.

## 5. Secrets (created out-of-band; NEVER committed)

Generated/entered privately. Names referenced by the manifests:

```powershell
# DB password + Evolus secrets
kubectl --kubeconfig $HOME\.kube\hetzner-dr.yaml -n paymentops-hackathon create secret generic paymentops-hackathon-secrets `
  --from-literal=DATABASE_PASSWORD='<enter privately>' `
  --from-literal=EVOLUS_API_KEY='<enter privately>' `
  --from-literal=EVOLUS_TOOL_API_KEY='<enter privately>'      # generated strong random

# Operator client (must match the seed job's PAYMENTOPS_OPERATOR_CLIENT_ID/SECRET)
kubectl --kubeconfig $HOME\.kube\hetzner-dr.yaml -n paymentops-hackathon create secret generic paymentops-hackathon-web-operator `
  --from-literal=client-id='cn_<generated>' `
  --from-literal=client-secret='<enter privately>'

# Admin bootstrap (seed job)
kubectl --kubeconfig $HOME\.kube\hetzner-dr.yaml -n paymentops-hackathon create secret generic paymentops-hackathon-bootstrap `
  --from-literal=admin-email='<enter privately>' `
  --from-literal=admin-password='<enter privately>'

# Image pull secret (copy the existing cluster credential; no values printed)
kubectl --kubeconfig $HOME\.kube\hetzner-dr.yaml get secret ghcr-pull -n cloudnova-web -o json `
  | %{ $s = $_ | ConvertFrom-Json; $s.metadata.namespace='paymentops-hackathon'; $s.metadata.name='ghcr-pull';
       $s.metadata.PSObject.Properties.Remove('resourceVersion'); $s.metadata.PSObject.Properties.Remove('uid');
       $s.metadata.PSObject.Properties.Remove('creationTimestamp');
       $s | ConvertTo-Json -Depth 20 | kubectl --kubeconfig $HOME\.kube\hetzner-dr.yaml apply -f - }
```

`EVOLUS_DEMO_ORG_PUBLIC_ID` is `cloudnova-hackathon-demo` (non-secret, in the ConfigMap).

## 6. Deploy

The established method is **Flux GitOps**; Flux reconciles from GitHub, so it requires a
commit + push of `homeserver` (not done here — pending instruction). Two options:

**A. GitOps (established method).** Commit + push the `homeserver` changes; Flux adds the
`paymentops-hackathon` Kustomization (already referenced) and applies the overlay. Then run the
seed job (it is part of the overlay). Verify:

```powershell
kubectl --kubeconfig $HOME\.kube\hetzner-dr.yaml -n flux-system get kustomization paymentops-hackathon
kubectl --kubeconfig $HOME\.kube\hetzner-dr.yaml -n paymentops-hackathon get pods,jobs
```

**B. Direct verify (interim, isolated).** Apply the rendered overlay to the namespace only:

```powershell
kubectl --kubeconfig $HOME\.kube\hetzner-dr.yaml apply -k C:\Users\sanke\Documents\homeserver\clusters\hetzner-dr\apps\paymentops-hackathon\overlays\dr
```

Do not mix methods once Flux owns the app (avoid conflicting ownership). Prefer **A**.

## 7. Internal verification (before any domain)

```powershell
kubectl --kubeconfig $HOME\.kube\hetzner-dr.yaml -n paymentops-hackathon port-forward svc/paymentops-hackathon-api 18000:8000
curl.exe http://localhost:18000/health
curl.exe http://localhost:18000/ready
```

## 8. Domain (Step 6, after internal checks pass)

The route file `overlays/dr/httproute.yaml` is prepared but **not** yet listed in the overlay.
Once the hostname is confirmed:
1. Add `- httproute.yaml` to `overlays/dr/kustomization.yaml`.
2. Set the hostname in `httproute.yaml` and in the ConfigMap (`CORS_ALLOWED_ORIGINS`,
   `ALLOWED_HOSTS`).
3. Add a matching **Cloudflare Tunnel** ingress rule + DNS record (managed remotely in
   Cloudflare Zero Trust) pointing the hostname at the Envoy `public-gateway`. TLS is
   terminated at Cloudflare; there is no cert-manager issuer to invent.

Expected DNS (Cloudflare-proxied) for the proposed hostname:
`paymentops-hackathon.cloudnova.tech` → Cloudflare Tunnel for this cluster.

## 9. Tool contract (Evolus WebAPI)

- URL: `https://<hostname>/api/v1/evolus/tools/validate-case`
- Headers: `X-Tool-Key: <EVOLUS_TOOL_API_KEY>` (raw), `Content-Type: application/json`
- Body: `{"case_ref":"<investigation_id>"}`

Create a real investigation (operator session via the app, or the operator API client), using
prepare-only mode during smoke tests so the (not-yet-connected) Evolus workflow is not started:
`POST /api/v1/investigations` with `{"demo_case_key":"pacs008-missing-town","start_workflow":false}`
→ returns `investigation_id`; use that as `case_ref`.

## 10. Rollback (hackathon only)

```powershell
# GitOps: remove the Kustomization + app dir in homeserver, commit/push; or:
kubectl --kubeconfig $HOME\.kube\hetzner-dr.yaml delete -k C:\Users\sanke\Documents\homeserver\clusters\hetzner-dr\apps\paymentops-hackathon\overlays\dr

# Full teardown (destroys ONLY hackathon data)
kubectl --kubeconfig $HOME\.kube\hetzner-dr.yaml delete namespace paymentops-hackathon
```

Never touches `paymentops-site`, `paymentops` (loudnova), or shared infrastructure.

## Blockers

1. **Registry push denied.** The available `gh` token scopes are `gist, read:org, repo,
   workflow` (no `write:packages`); `docker push ghcr.io/sanketnawale/...` returns
   `permission_denied: The token provided does not match expected scopes`. No Docker Hub login
   and no in-cluster registry exist.
   → Ask: grant packages write (`gh auth refresh -h github.com -s write:packages`) or provide a
   registry credential privately.
2. **arm64 build image supply.** Images must be arm64. Local builds were enabled via
   `tonistiigi/binfmt --install arm64` and both images build clean; the durable method is
   GitHub Actions (arm/amd runners) pushing to GHCR with `GITHUB_TOKEN` — which requires
   commit/push of the repo (not done).
3. **Hostname** for Step 6 not yet confirmed (proposed `paymentops-hackathon.cloudnova.tech`).
