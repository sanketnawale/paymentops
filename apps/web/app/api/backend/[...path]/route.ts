import { type NextRequest, NextResponse } from 'next/server';
import { requiredRole, roleSatisfies } from '@/lib/server/rbac';
import {
  CSRF_COOKIE,
  SESSION_COOKIE,
  internalApiUrl,
  isAuthorizedTenant,
  operatorHeaders,
  validateSessionToken,
} from '@/lib/server/session';

// Authenticated same-origin API proxy.
//
//   Browser (session cookie) -> /api/backend/*  (same origin)
//     -> session validated against the backend
//     -> operator credential + trusted actor identity injected server-side
//     -> PAYMENTOPS_INTERNAL_API_URL/*
//
// Anonymous callers receive 401 and never reach the backend. The browser never learns the
// internal service URL, the operator credential, or the session token value.

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const HOP_BY_HOP = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
  'host',
  'content-length',
  'accept-encoding',
  'x-client-id',
  'x-client-secret',
  'x-actor-identity',
  'x-session-token',
]);

const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function unauthorized(): NextResponse {
  return NextResponse.json({ detail: 'Authentication required.' }, { status: 401 });
}

function forbidden(detail: string): NextResponse {
  return NextResponse.json({ detail }, { status: 403 });
}

async function proxy(
  request: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
): Promise<Response> {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  const user = await validateSessionToken(token);
  if (!user) return unauthorized();
  if (!isAuthorizedTenant(user)) {
    return forbidden('Your account is not authorized for this workspace.');
  }

  const { path } = await ctx.params;
  const segments = path ?? [];

  // Role-based authorization (enforced server-side; UI visibility is not authorization).
  const required = requiredRole(request.method, segments);
  if (!roleSatisfies(user.role, required)) {
    return forbidden(`Your role (${user.role}) does not permit this action.`);
  }

  // CSRF: mutating requests must echo the double-submit token.
  if (MUTATING_METHODS.has(request.method)) {
    const cookieToken = request.cookies.get(CSRF_COOKIE)?.value;
    const headerToken = request.headers.get('x-csrf-token');
    if (!cookieToken || !headerToken || cookieToken !== headerToken) {
      return forbidden('Invalid or missing CSRF token.');
    }
  }

  const suffix = segments.map(encodeURIComponent).join('/');
  const target = `${internalApiUrl()}/${suffix}${request.nextUrl.search}`;

  const outbound = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) outbound.set(key, value);
  });
  outbound.set('accept', request.headers.get('accept') ?? 'application/json');

  // Inject the server-side operator credential and the trusted actor identity.
  for (const [key, value] of Object.entries(operatorHeaders())) outbound.set(key, value);
  outbound.set('X-Actor-Identity', user.email);

  const hasBody = !['GET', 'HEAD'].includes(request.method);
  const body = hasBody ? await request.arrayBuffer() : undefined;

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers: outbound,
      body: body && body.byteLength > 0 ? body : undefined,
      redirect: 'manual',
      cache: 'no-store',
    });
  } catch {
    return NextResponse.json({ detail: 'Upstream PaymentOps API is unavailable.' }, { status: 502 });
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) responseHeaders.set(key, value);
  });

  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export async function GET(request: NextRequest, ctx: { params: Promise<{ path?: string[] }> }) {
  return proxy(request, ctx);
}
export async function POST(request: NextRequest, ctx: { params: Promise<{ path?: string[] }> }) {
  return proxy(request, ctx);
}
export async function PUT(request: NextRequest, ctx: { params: Promise<{ path?: string[] }> }) {
  return proxy(request, ctx);
}
export async function PATCH(request: NextRequest, ctx: { params: Promise<{ path?: string[] }> }) {
  return proxy(request, ctx);
}
export async function DELETE(request: NextRequest, ctx: { params: Promise<{ path?: string[] }> }) {
  return proxy(request, ctx);
}
export async function HEAD(request: NextRequest, ctx: { params: Promise<{ path?: string[] }> }) {
  return proxy(request, ctx);
}
