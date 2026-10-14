# Authentication & Session Architecture

PaymentOps uses **real server-side authentication** for the private application. There is no
client-side "logged in" flag, and no API secrets are exposed to the browser.

## Components

```
Browser
  -> /login                       (Next.js page)
  -> POST /api/auth/login         (Next.js route handler)
       -> POST /api/v1/auth/login (FastAPI, server-to-server, operator credential)
       -> verifies password, creates a DB-backed session, returns an opaque token
  -> HttpOnly session cookie      (set by Next.js on the app origin)
  -> /api/backend/*               (authenticated proxy)
       -> validates the session against FastAPI
       -> injects the operator credential + trusted actor identity
       -> forwards to the private API
```

## User model

`app_users`: id, organization_id, email (unique, lowercased), display_name, password_hash,
role, status, failed_login_count, locked_until, last_login_at, created_at, updated_at.

Roles: `ADMIN`, `OPERATOR`, `VIEWER`. Status: `ACTIVE`, `DISABLED`.

Passwords are stored only as salted **PBKDF2-HMAC-SHA256** hashes (600k iterations), via
`paymentops_api/passwords.py`. Plaintext passwords are never persisted or logged.

## Sessions

`user_sessions`: id, user_id, organization_id, token_hash (SHA-256 of the opaque token),
created_at, expires_at, last_seen_at, revoked_at.

- The raw session token is returned to the Next.js server once and stored only in an HttpOnly
  cookie. Only its SHA-256 hash is stored in the database.
- Sessions expire after 8 hours and can be revoked (logout / `revoke_all_sessions`).
- Cookies: `HttpOnly`, `SameSite=Lax`, `Secure` in production, `Path=/`.

## Failed-login protections

- Generic failure message ("Invalid email or password.") — no user enumeration.
- After 5 consecutive failures the account is locked for 15 minutes.
- A disabled account is only revealed after correct credentials are supplied.

## CSRF

State-changing requests carry a double-submit token: a non-HttpOnly `paymentops_csrf` cookie
is echoed by the browser in the `X-CSRF-Token` header, and the proxy rejects mutating requests
when the two do not match. Combined with `SameSite=Lax`, this blocks cross-site request forgery.

## Route protection

- `middleware.ts` redirects anonymous users from all application routes to `/login`.
- `/api/backend/*` validates the session server-side and returns `401` for anonymous callers.
- The proxy strips any inbound `X-Actor-Identity` / credential headers and sets them itself.

## Audit actor

The proxy injects a trusted `X-Actor-Identity` header (the authenticated user's email) for
operator actions. The backend prefers this trusted header over any body-supplied operator value,
so audit records attribute actions to the authenticated user rather than a spoofable value.

## Bootstrap the first administrator

```bash
PAYMENTOPS_BOOTSTRAP_ADMIN_EMAIL=admin@example.com \
PAYMENTOPS_BOOTSTRAP_ADMIN_PASSWORD='<strong-temporary-password>' \
PAYMENTOPS_BOOTSTRAP_ORG_PUBLIC_ID=cloudnova \
python -m scripts.bootstrap_admin
```

- The password is read from the environment and never printed.
- Re-running with an existing email is a no-op.
- Change the temporary password after first sign-in. There is no public self-service signup;
  users are provisioned by CloudNova (see the marketing repo's demo-request flow).

## User administration

Day-to-day account operations use `scripts.user_admin` (run inside the API container). Passwords
are supplied via `PAYMENTOPS_USER_PASSWORD` (minimum 12 characters) and are never printed.

```bash
# create a user in an existing tenant
PAYMENTOPS_USER_PASSWORD='<strong-password>' python -m scripts.user_admin create-user \
    --email user@example.com --name "User" --org cloudnova-demo-bank --role OPERATOR

# rotate a password (clears lockout and revokes all of the user's sessions)
PAYMENTOPS_USER_PASSWORD='<strong-password>' python -m scripts.user_admin reset-password \
    --email user@example.com

python -m scripts.user_admin disable-user --email user@example.com   # also revokes sessions
python -m scripts.user_admin enable-user  --email user@example.com
python -m scripts.user_admin set-role     --email user@example.com --role ADMIN
python -m scripts.user_admin revoke-sessions --email user@example.com
python -m scripts.user_admin list-users
```

## Audit events

Authentication events are recorded in `audit_events` with `case_id = NULL` and
`event_type` `auth.login` / `auth.logout`, attributed to the user's email. No passwords or
session tokens are ever written to the audit log.

## Tests and the test database

The integration/security suites require PostgreSQL and are skipped unless `TEST_DATABASE_URL`
is set. An autouse fixture truncates all application tables before each test, so the suite is
safe to run repeatedly against a dedicated (throwaway) database:

```bash
alembic upgrade head          # with DATABASE_* pointing at the throwaway DB
TEST_DATABASE_URL='postgresql+asyncpg://.../paymentops_test' pytest
```

## OIDC migration path

The user/session model is intentionally small. Local login can be augmented or replaced by an
OIDC provider later: the session table and `resolve_session` remain the authoritative check,
so an OIDC callback can mint the same server-side session.
