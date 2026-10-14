import { NextRequest } from 'next/server';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const validateSessionToken = vi.fn();
const isAuthorizedTenant = vi.fn();

vi.mock('@/lib/server/session', () => ({
  SESSION_COOKIE: 'paymentops_session',
  CSRF_COOKIE: 'paymentops_csrf',
  internalApiUrl: () => 'http://paymentops-api:8000',
  operatorHeaders: () => ({ 'X-Client-Id': 'operator-client', 'X-Client-Secret': 'operator-secret' }),
  validateSessionToken: (...args: unknown[]) => validateSessionToken(...args),
  isAuthorizedTenant: (...args: unknown[]) => isAuthorizedTenant(...args),
}));

import { GET, POST } from './route';

const USER = {
  id: 'u1',
  email: 'operator@example.com',
  display_name: 'Op',
  role: 'OPERATOR',
  organization_id: 'org-1',
};

interface FetchCall {
  url: string;
  init: RequestInit;
}

function stubFetch(status = 200, body: unknown = { ok: true }): FetchCall[] {
  const calls: FetchCall[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string | URL, init: RequestInit) => {
      calls.push({ url: String(url), init });
      return new Response(JSON.stringify(body), {
        status,
        headers: { 'content-type': 'application/json' },
      });
    }),
  );
  return calls;
}

beforeEach(() => {
  validateSessionToken.mockResolvedValue(USER);
  isAuthorizedTenant.mockReturnValue(true);
});

afterEach(() => {
  vi.restoreAllMocks();
  validateSessionToken.mockReset();
  isAuthorizedTenant.mockReset();
});

describe('authenticated same-origin API proxy', () => {
  it('rejects anonymous requests with 401 and never calls the backend', async () => {
    validateSessionToken.mockResolvedValue(null);
    const calls = stubFetch();
    const req = new NextRequest('https://app.test/api/backend/api/v1/dashboard');
    const res = await GET(req, { params: Promise.resolve({ path: ['api', 'v1', 'dashboard'] }) });

    expect(res.status).toBe(401);
    expect(calls).toHaveLength(0);
  });

  it('rejects a session from an unauthorized tenant', async () => {
    isAuthorizedTenant.mockReturnValue(false);
    const calls = stubFetch();
    const req = new NextRequest('https://app.test/api/backend/api/v1/dashboard', {
      headers: { cookie: 'paymentops_session=abc' },
    });
    const res = await GET(req, { params: Promise.resolve({ path: ['api', 'v1', 'dashboard'] }) });

    expect(res.status).toBe(403);
    expect(calls).toHaveLength(0);
  });

  it('forwards an authenticated GET and injects credentials + actor', async () => {
    const calls = stubFetch(200, { analyzed: 1 });
    const req = new NextRequest('https://app.test/api/backend/api/v1/dashboard?limit=5', {
      headers: { cookie: 'paymentops_session=abc' },
    });
    const res = await GET(req, { params: Promise.resolve({ path: ['api', 'v1', 'dashboard'] }) });

    expect(res.status).toBe(200);
    expect(calls[0].url).toBe('http://paymentops-api:8000/api/v1/dashboard?limit=5');
    const headers = calls[0].init.headers as Headers;
    expect(headers.get('X-Client-Id')).toBe('operator-client');
    expect(headers.get('X-Actor-Identity')).toBe('operator@example.com');
  });

  it('strips browser-supplied actor and credential headers', async () => {
    const calls = stubFetch();
    const req = new NextRequest('https://app.test/api/backend/api/v1/info', {
      headers: {
        cookie: 'paymentops_session=abc',
        'x-actor-identity': 'spoofed@attacker.test',
        'x-client-secret': 'stolen',
      },
    });
    await GET(req, { params: Promise.resolve({ path: ['api', 'v1', 'info'] }) });

    const headers = calls[0].init.headers as Headers;
    expect(headers.get('X-Actor-Identity')).toBe('operator@example.com');
    expect(headers.get('X-Client-Secret')).toBe('operator-secret');
  });

  it('requires a matching CSRF token for mutating requests', async () => {
    const calls = stubFetch(200, { ok: true });
    const blocked = new NextRequest('https://app.test/api/backend/api/v1/cases/x/actions', {
      method: 'POST',
      headers: { cookie: 'paymentops_session=abc', 'content-type': 'application/json' },
      body: JSON.stringify({ action: 'approve' }),
    });
    const res = await POST(blocked, { params: Promise.resolve({ path: ['api', 'v1', 'cases', 'x', 'actions'] }) });
    expect(res.status).toBe(403);
    expect(calls).toHaveLength(0);

    const allowed = new NextRequest('https://app.test/api/backend/api/v1/cases/x/actions', {
      method: 'POST',
      headers: {
        cookie: 'paymentops_session=abc; paymentops_csrf=tok-123',
        'content-type': 'application/json',
        'x-csrf-token': 'tok-123',
      },
      body: JSON.stringify({ action: 'approve' }),
    });
    const ok = await POST(allowed, { params: Promise.resolve({ path: ['api', 'v1', 'cases', 'x', 'actions'] }) });
    expect(ok.status).toBe(200);
    expect(calls).toHaveLength(1);
  });

  it('preserves structured backend errors', async () => {
    stubFetch(422, { detail: 'unsupported ISO version' });
    const req = new NextRequest('https://app.test/api/backend/api/v1/iso/analyze', {
      method: 'POST',
      headers: {
        cookie: 'paymentops_session=abc; paymentops_csrf=t',
        'content-type': 'application/json',
        'x-csrf-token': 't',
      },
      body: JSON.stringify({ xml: '<Document/>' }),
    });
    const res = await POST(req, { params: Promise.resolve({ path: ['api', 'v1', 'iso', 'analyze'] }) });
    expect(res.status).toBe(422);
    expect(await res.json()).toEqual({ detail: 'unsupported ISO version' });
  });

  it('returns a safe 502 when the upstream is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('fetch failed');
    }));
    const req = new NextRequest('https://app.test/api/backend/api/v1/dashboard', {
      headers: { cookie: 'paymentops_session=abc' },
    });
    const res = await GET(req, { params: Promise.resolve({ path: ['api', 'v1', 'dashboard'] }) });
    expect(res.status).toBe(502);
  });

  it('denies a VIEWER a mutating action with 403', async () => {
    validateSessionToken.mockResolvedValue({ ...USER, role: 'VIEWER' });
    const calls = stubFetch();
    const req = new NextRequest('https://app.test/api/backend/api/v1/cases/x/actions', {
      method: 'POST',
      headers: {
        cookie: 'paymentops_session=abc; paymentops_csrf=t',
        'content-type': 'application/json',
        'x-csrf-token': 't',
      },
      body: JSON.stringify({ action: 'approve' }),
    });
    const res = await POST(req, { params: Promise.resolve({ path: ['api', 'v1', 'cases', 'x', 'actions'] }) });
    expect(res.status).toBe(403);
    expect(calls).toHaveLength(0);
  });

  it('allows an OPERATOR a mutating action', async () => {
    validateSessionToken.mockResolvedValue({ ...USER, role: 'OPERATOR' });
    const calls = stubFetch(200, { ok: true });
    const req = new NextRequest('https://app.test/api/backend/api/v1/cases/x/actions', {
      method: 'POST',
      headers: {
        cookie: 'paymentops_session=abc; paymentops_csrf=t',
        'content-type': 'application/json',
        'x-csrf-token': 't',
      },
      body: JSON.stringify({ action: 'approve' }),
    });
    const res = await POST(req, { params: Promise.resolve({ path: ['api', 'v1', 'cases', 'x', 'actions'] }) });
    expect(res.status).toBe(200);
    expect(calls).toHaveLength(1);
  });

  it('denies an OPERATOR an administrative action with 403', async () => {
    validateSessionToken.mockResolvedValue({ ...USER, role: 'OPERATOR' });
    const calls = stubFetch();
    const req = new NextRequest('https://app.test/api/backend/api/v1/clients', {
      method: 'POST',
      headers: {
        cookie: 'paymentops_session=abc; paymentops_csrf=t',
        'content-type': 'application/json',
        'x-csrf-token': 't',
      },
      body: JSON.stringify({ organization_id: 'org-1' }),
    });
    const res = await POST(req, { params: Promise.resolve({ path: ['api', 'v1', 'clients'] }) });
    expect(res.status).toBe(403);
    expect(calls).toHaveLength(0);
  });

  it('allows an ADMIN an administrative action', async () => {
    validateSessionToken.mockResolvedValue({ ...USER, role: 'ADMIN' });
    const calls = stubFetch(201, { client_id: 'cn_x' });
    const req = new NextRequest('https://app.test/api/backend/api/v1/clients', {
      method: 'POST',
      headers: {
        cookie: 'paymentops_session=abc; paymentops_csrf=t',
        'content-type': 'application/json',
        'x-csrf-token': 't',
      },
      body: JSON.stringify({ organization_id: 'org-1' }),
    });
    const res = await POST(req, { params: Promise.resolve({ path: ['api', 'v1', 'clients'] }) });
    expect(res.status).toBe(201);
    expect(calls).toHaveLength(1);
  });
});
