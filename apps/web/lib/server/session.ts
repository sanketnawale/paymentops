// Server-only session helpers. The session token is an opaque, DB-backed value stored in an
// HttpOnly cookie. The browser never sees the backend operator credential or the token value.
// (This module must only be imported from server code: route handlers and middleware.)

export const SESSION_COOKIE = 'paymentops_session';
export const CSRF_COOKIE = 'paymentops_csrf';

export interface SessionUser {
  id: string;
  email: string;
  display_name: string;
  role: 'ADMIN' | 'OPERATOR' | 'VIEWER' | string;
  organization_id: string;
}

export function internalApiUrl(): string {
  return (process.env.PAYMENTOPS_INTERNAL_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '');
}

export function operatorHeaders(): Record<string, string> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const id = process.env.PAYMENTOPS_CLIENT_ID;
  const secret = process.env.PAYMENTOPS_CLIENT_SECRET;
  if (id && secret) {
    headers['X-Client-Id'] = id;
    headers['X-Client-Secret'] = secret;
  }
  return headers;
}

/** Validate a session token against the backend. Returns the user or null. */
export async function validateSessionToken(token: string | undefined): Promise<SessionUser | null> {
  if (!token) return null;
  try {
    const res = await fetch(`${internalApiUrl()}/api/v1/auth/session`, {
      headers: { ...operatorHeaders(), 'X-Session-Token': token },
      cache: 'no-store',
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { user?: SessionUser };
    return body.user ?? null;
  } catch {
    return null;
  }
}

/** True when the session user's organization matches the operator tenant (isolation guard). */
export function isAuthorizedTenant(user: SessionUser): boolean {
  const expected = process.env.PAYMENTOPS_OPERATOR_ORG_ID;
  if (!expected) return true; // not configured -> no extra guard (backend still scopes by client)
  return user.organization_id === expected;
}

export function isProduction(): boolean {
  return (process.env.NODE_ENV ?? 'development') === 'production';
}

export function sessionCookieOptions(maxAgeSeconds: number) {
  return {
    httpOnly: true,
    secure: isProduction(),
    sameSite: 'lax' as const,
    path: '/',
    maxAge: maxAgeSeconds,
  };
}

export function csrfCookieOptions(maxAgeSeconds: number) {
  return {
    httpOnly: false, // readable by same-origin JS to echo in X-CSRF-Token
    secure: isProduction(),
    sameSite: 'lax' as const,
    path: '/',
    maxAge: maxAgeSeconds,
  };
}
