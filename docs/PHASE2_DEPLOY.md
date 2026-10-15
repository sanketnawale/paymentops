# Phase 2A — Isolated PaymentOps hackathon deployment (Hetzner k3s)

Deployment of the **paymentops-amd** application (Evolus/AMD investigator) into the Hetzner
`hetzner-dr` k3s cluster under the isolated namespace **`paymentops-hackathon`**. Nothing is
shared with the business application or other namespaces.

> **Status: DEPLOYED and verified internally.** Images are published to GHCR (arm64), Flux has
> reconciled, migrations + seed are complete, and the validation tool returns real deterministic
> findings. The **public domain route is intentionally disabled** (added later).
>
> - App commit: `ef7f8d626717ae41a3273cee0776274da6cd9769`
> - Infra commits: `cd42c8c` (initial), `46d9fbc` (hardening) — Flux revision `main@46d9fbc…`
> - Images: `ghcr.io/sanketnawale/paymentops-hackathon-api:ef7f8d6…` and `…-web:ef7f8d6…`

## 1. Cluster facts (observed, `--kubeconfig $HOME\.kube\hetzner-dr.yaml`)

| Item | Value |
| --- | --- |
| Context / API | `hetzner-dr` / `https://65.21.241.211:6443` |
| Node | `hetzner-dr-01` (control-plane, k3s `v1.36.3+k3s1`, **arm64**, Ubuntu 24.04) |
| Capacity | 2 vCPU, ~3.8 GiB memory (~85% already used) |
| StorageClass | `local-path` (default) |
| Ingress | Envoy Gateway `public-gateway` (ns `gateway-infra`), HTTP listener only |
| External/TLS | **Cloudflare Tunnel** + Cloudflare-managed TLS/DNS |
| GitOps | Flux (`clusters/hetzner-dr`), source `ssh://git@github.com/sanketnawale/loudnova-infra` @ `main` |
| Registry | `ghcr.io` (pulled with the existing `ghcr-pull` secret) |

**Finding:** the business PaymentOps application is **not** on `hetzner-dr`; the only PaymentOps
workload there is the marketing site `paymentops-site/paymentops-website` (unchanged, 1/1). The
business API/web/DB manifests live under `clusters/loudnova/apps/paymentops` (another cluster).

## 2. What is deployed

Namespace `paymentops-hackathon`:

| Component | Resource | Status |
| --- | --- | --- |
| API | Deployment + Service `paymentops-hackathon-api` (:8000) | 1/1 |
| Web | Deployment + Service `paymentops-hackathon-web` (:80→3000) | 1/1 |
| PostgreSQL | Deployment + Service + PVC `…postgres-pvc` (2 Gi, `local-path`, Bound) | 1/1 |
| Migrations | Job `paymentops-hackathon-migrate` | Complete (through `0011_investigations`) |
| Demo seed | Job `paymentops-hackathon-seed` | Complete (org + operator client + admin) |
| Governance | ResourceQuota, LimitRange, NetworkPolicy | Applied |

Not deployed (not required for the investigation demo): worker, Redis, address-structuring.
`READY_CHECKS=database`; deterministic `CloudNovaAddressProvider`.

Resource usage after deploy: `requests.cpu 130m/600m`, `requests.memory 352Mi/900Mi`,
`pods 3/6`.

## 3. Images (published)

Published by GitHub Actions (`.github/workflows/ci.yml`) on `ubuntu-latest` using
`docker/setup-qemu-action` + `docker/setup-buildx-action`, `platforms: linux/arm64`, logged in
to GHCR with `GITHUB_TOKEN` (`contents: read`, `packages: write`), tagged with the full commit
SHA (immutable, no `latest`):

- `ghcr.io/sanketnawale/paymentops-hackathon-api:ef7f8d626717ae41a3273cee0776274da6cd9769`
- `ghcr.io/sanketnawale/paymentops-hackathon-web:ef7f8d626717ae41a3273cee0776274da6cd9769`

Run `38628478732` — all jobs green (Backend, Frontend, Security, Build & publish arm64).

## 4. Files

`paymentops-amd` (application): `apps/api/scripts/seed_hackathon.py`; `start_workflow`
prepare-only flag in `services/investigation_service.py` + `routers/investigations.py`;
`apps/web/lib/api.ts`, `apps/web/app/investigations/[id]/page.tsx`; tests; `.github/workflows/ci.yml`
(arm64 publish); docs.

`homeserver` (`clusters/hetzner-dr`): `apps/paymentops-hackathon/{base,overlays/dr}` +
`flux-system/paymentops-hackathon.yaml` (+ reference in `flux-system/kustomization.yaml`).

## 5. Secrets (out-of-band; never committed)

- `paymentops-hackathon-secrets` — `DATABASE_PASSWORD`, `EVOLUS_TOOL_API_KEY`, `EVOLUS_API_KEY`
- `paymentops-hackathon-web-operator` — `client-id`, `client-secret`
- `paymentops-hackathon-bootstrap` — `admin-email`, `admin-password`
- `ghcr-pull` — copied from `cloudnova-web`

Generated values were written only to the gitignored local `.env`. `EVOLUS_APPLICATION_ID` /
`EVOLUS_WORKFLOW_ID` / `EVOLUS_DEMO_ORG_PUBLIC_ID` are non-secret ConfigMap values.

## 6. Verification (observed)

| Check | Result |
| --- | --- |
| Flux `paymentops-hackathon` | `Ready=True` @ `main@46d9fbc…` |
| Pods | api/web/postgres 1/1 Running |
| Migration Job | Complete (0011) |
| Seed Job | Complete; org `cloudnova-hackathon-demo` + operator client + admin |
| `GET /health` (API) | 200 |
| `GET /ready` (API) | `{"status":"ready","checks":[{"name":"database","ok":true}]}` |
| `GET /api/health` (web, 127.0.0.1) | `{"status":"ok"}` |
| Tool, correct `X-Tool-Key` | 200 — `case_ref=inv-17ae8a6a2937`, `validation.status=valid`, findings `ADR-001`, `input_unchanged=true` |
| Tool, wrong/missing key | 401 |
| Business app `paymentops-site` | 1/1 (unchanged) |
| Domain route | HTTPRoute `Accepted=True`; frontend `/`→`/login` (307, relative Location), `/login` 200; tool 200/401 via Envoy `public-envoy` |
| NetworkPolicy | default-deny ingress; web ← gateway+ns, api ← ns+jobs+`envoy-gateway-system`, postgres ← api/migrate/seed. **Egress unrestricted** (DNS, in-namespace DB, outbound Evolus API); no business access. |

**Real test investigation (deployed database):** `inv-17ae8a6a2937`
(`demo_case_key=pacs008-missing-town`, `status=PREPARED`, 2× `ADR-001`, `input_hash=a78e9098…`).

## 7. Tool contract (Evolus WebAPI)

- Method/URL: `POST https://<hostname>/api/v1/evolus/tools/validate-case`
- Header: `X-Tool-Key: <EVOLUS_TOOL_API_KEY>` (raw value)
- Header: `Content-Type: application/json`
- Body: `{"case_ref":"<investigation_id>"}`
- Prepare-only creation (does not start the (unconnected) workflow):
  `POST /api/v1/investigations` `{"demo_case_key":"pacs008-missing-town","start_workflow":false}`

## 8. Domain / Cloudflare Tunnel (ENABLED)

The route `overlays/dr/httproute.yaml` is now listed in the overlay and reconciles green
(`Accepted=True`, `ResolvedRefs=True`). Exposure uses the **shared Cloudflare Tunnel → Envoy
`public-gateway`** path, exactly like the other published apps (host-based routing).

Tunnel connector: deployment `cloudflared` in namespace `cloudflare` (token-based,
dashboard-managed). The gateway's data-plane Service is `public-envoy`
(namespace `envoy-gateway-system`, ClusterIP, port 80) — confirmed as the `public-gateway`
status address (`10.43.116.175`).

**Exact Cloudflare Zero Trust → Networks → Tunnels → Public Hostname values:**

| Field | Value |
| --- | --- |
| Subdomain | `paymentops-hackathon` |
| Domain | `cloudnova.tech` |
| Path | *(empty)* |
| **Service type** | **HTTP** |
| **URL** | **`public-envoy.envoy-gateway-system.svc.cluster.local:80`** |
| HTTP Host Header | *(leave empty — defaults to the public hostname)* |

The single origin reaches both surfaces because Envoy dispatches by Host and the HTTPRoute
splits by path: `/api/v1/evolus/*` → `paymentops-hackathon-api:8000`; everything else →
`paymentops-hackathon-web:80`. Cloudflare terminates TLS (no cert-manager issuer).

TLS/DNS are managed in Cloudflare; no in-cluster certificate is used.

## 9. Rollback (hackathon only)

Suspend/remove Flux reconciliation first, then remove resources:

```powershell
kubectl --kubeconfig $HOME\.kube\hetzner-dr.yaml -n flux-system delete kustomization paymentops-hackathon
kubectl --kubeconfig $HOME\.kube\hetzner-dr.yaml delete -k <homeserver>\clusters\hetzner-dr\apps\paymentops-hackathon\overlays\dr
# Full teardown (destroys ONLY hackathon data):
kubectl --kubeconfig $HOME\.kube\hetzner-dr.yaml delete namespace paymentops-hackathon
```

Never affects `paymentops-site`, `clusters/loudnova`, or shared infrastructure.

## 10. Remaining blockers

1. **`EVOLUS_API_KEY` not present in local `.env`.** The deployed ConfigMap has
   `EVOLUS_ENABLED=true` but `evolus_configured` is false, so starting an agent workflow
   reports "not configured". Add the key privately to `.env` and update the
   `paymentops-hackathon-secrets` secret (`kubectl create secret … --dry-run=client -o yaml |
   kubectl apply -f -`) to enable live agent runs. Prepare-only investigations and the
   validation tool already work without it.
2. **Domain not configured** (intentional). Needs the hostname + Cloudflare Tunnel ingress +
   DNS.
3. **Live Evolus/AMD investigation not yet exercised** — the WebAPI tool must be attached in
   the Evolus workspace (see `docs/evolus/evolus-workspace-setup.md`) before a full run.
