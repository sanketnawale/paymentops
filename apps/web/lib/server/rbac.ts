// Role-based access control (server-side). The Next.js proxy enforces roles because the
// backend authenticates a single operator client and cannot distinguish users.
//
// VIEWER   -> read-only (safe methods)
// OPERATOR -> all operator actions (case/match/reconciliation decisions)
// ADMIN    -> operator actions + administrative configuration
//
// This is enforced server-side; hiding UI is not authorization.

export type Role = 'VIEWER' | 'OPERATOR' | 'ADMIN';

const RANK: Record<Role, number> = { VIEWER: 0, OPERATOR: 1, ADMIN: 2 };

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

// Administrative (mutating) endpoints require ADMIN.
const ADMIN_PATTERNS: RegExp[] = [
  /^\/api\/v1\/clients$/,
  /^\/api\/v1\/integration-profiles$/,
  /^\/api\/v1\/integration-profiles\/[^/]+\/publish$/,
  /^\/api\/v1\/matching\/policies$/,
  /^\/api\/v1\/matching\/policies\/[^/]+\/publish$/,
];

export function normalizeRole(role: string | null | undefined): Role {
  const upper = (role ?? '').toUpperCase();
  return upper === 'ADMIN' || upper === 'OPERATOR' ? upper : 'VIEWER';
}

/** The minimum role required for a request to the given backend path. */
export function requiredRole(method: string, pathSegments: string[]): Role {
  if (SAFE_METHODS.has(method.toUpperCase())) return 'VIEWER';
  const path = `/${pathSegments.join('/')}`;
  if (ADMIN_PATTERNS.some((re) => re.test(path))) return 'ADMIN';
  return 'OPERATOR';
}

export function roleSatisfies(role: string | null | undefined, required: Role): boolean {
  return RANK[normalizeRole(role)] >= RANK[required];
}
