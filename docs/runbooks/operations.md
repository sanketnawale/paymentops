# Operations Runbook

Operational procedures for the PaymentOps evaluation environment. Commands assume
`KUBECONFIG` points at the `loudnova` cluster and the `flux`/`kubectl` CLIs are installed.
Never paste real secrets into this document or into logs.

## Deploy and rollback

Deployments are GitOps-driven: CI builds images tagged with the commit SHA, and the infra repo
pins those SHAs. Flux applies the pinned revision.

```bash
# 1. Land and push the change on main (CI builds ghcr.io/cloodnova/paymentops-<api|web|worker>:<sha>)
# 2. Pin the new SHA in the infra repo
#    clusters/loudnova/apps/paymentops/{base,overlays/dev}/patch-*.yaml
# 3. Reconcile
flux reconcile source git flux-system
flux reconcile kustomization paymentops-dev --with-source
kubectl -n paymentops rollout status deploy/paymentops-api
kubectl -n paymentops rollout status deploy/paymentops-web
kubectl -n paymentops rollout status deploy/paymentops-worker
```

**Rollback:** revert the pin commit in the infra repo (git revert) and re-run the reconcile
commands. Flux will roll the deployments back to the previous image digests. No `latest` tags are
used; every deployment is pinned to a concrete commit SHA.

**Verify a release:** `GET /api/v1/info` must report `version`, `build_sha`, and `build_date`.

## Database backup and restore

The database is the system of record. Take a logical backup before any risky change.

```bash
# Backup (custom format) into the postgres pod, then copy out
kubectl -n paymentops exec deploy/paymentops-postgres -- \
  pg_dump -U paymentops -d paymentops -Fc -f /tmp/paymentops.dump
kubectl -n paymentops cp paymentops-postgres-0:/tmp/paymentops.dump ./paymentops-$(date +%F).dump

# Restore into an ISOLATED database first (never restore over the live DB to test)
kubectl -n paymentops exec deploy/paymentops-postgres -- sh -c \
  "dropdb -U paymentops --if-exists paymentops_restore_test && \
   createdb -U paymentops paymentops_restore_test && \
   pg_restore -U paymentops -d paymentops_restore_test /tmp/paymentops.dump"

# Validate: compare row counts and the alembic head between source and restored DBs
kubectl -n paymentops exec deploy/paymentops-postgres -- psql -U paymentops -d paymentops_restore_test \
  -c "SELECT version_num FROM alembic_version;"
```

A verified restore has the same `alembic_version` and matching row counts for
`organizations`, `app_users`, `payment_cases`, `iso_messages`, `payment_lifecycles`,
`account_entries`, and `integration_profiles`.

## Demo tenant reset

`scripts.reset_demo` deletes only the demo tenant's operational rows (foreign-key-safe order)
and never touches other tenants, platform configuration, or identities.

```bash
# Reset operational data, keep users
kubectl -n paymentops exec deploy/paymentops-api -- \
  python -m scripts.reset_demo --org cloudnova-demo-bank --yes

# Re-seed synthetic scenarios (idempotent)
kubectl -n paymentops exec deploy/paymentops-api -- \
  python -m scripts.seed_demo --org cloudnova-demo-bank

# Full reset including demo users
kubectl -n paymentops exec deploy/paymentops-api -- \
  python -m scripts.reset_demo --org cloudnova-demo-bank --yes --delete-users
```

## User administration

See `docs/authentication.md`. Passwords are supplied via `PAYMENTOPS_USER_PASSWORD` and are never
printed. Password reset and disable revoke all of the user's sessions.

## Incident response (baseline)

1. **Contain:** if a tenant may be compromised, disable its users
   (`scripts.user_admin disable-user`), which revokes sessions immediately.
2. **Preserve evidence:** take a database backup before remediation. Received payloads are
   immutable evidence (ADR-006) — never mutate them.
3. **Assess:** review `audit_events` (`auth.login`, `auth.logout`, operator actions) and
   application logs. Logs never contain payload data or secrets.
4. **Remediate:** rotate the affected credentials and the operator client secret
   (`paymentops-secrets`), then re-enable users.
5. **Report:** provide the affected tenant a generic summary with a correlation id; never include
   stack traces, configuration dumps, or payload contents.
