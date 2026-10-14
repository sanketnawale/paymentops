import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const cookieSet = vi.fn();
const cookieDelete = vi.fn();

vi.mock('next/headers', () => ({
  cookies: async () => ({
    set: cookieSet,
    delete: cookieDelete,
    get: () => undefined,
  }),
}));

vi.mock('@/lib/server/session', () => ({
  SESSION_COOKIE: 'paymentops_session',
  CSRF_COOKIE: 'paymentops_csrf',
  internalApiUrl: () => 'http://paymentops-api:8000',
  operatorHeaders: () => ({ 'X-Client-Id': 'cid', 'X-Client-Secret': 'csec' }),
  sessionCookieOptions: (maxAge: number) => ({ httpOnly: true, maxAge }),
  csrfCookieOptions: (maxAge: number) => ({ httpOnly: false, maxAge }),
  validateSessionToken: vi.fn(),
  isAuthorizedTenant: () => true,
}));

import { POST as login } from './login/route';
import { POST as logout } from './logout/route';

function jsonRequest(body: unknown): Request {
  return new Request('https://app.test/api/auth/login', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
}

beforeEach(() => {
  cookieSet.mockReset();
  cookieDelete.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('login route handler', () => {
  it('sets an HttpOnly session cookie on success', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ session_token: 'tok', user: { id: 'u1' } }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    ));
    const res = await login(jsonRequest({ email: 'a@b.com', password: 'secret' }));
    expect(res.status).toBe(200);
    expect(cookieSet).toHaveBeenCalledTimes(2);
    const sessionCall = cookieSet.mock.calls.find((c) => c[0] === 'paymentops_session');
    expect(sessionCall?.[1]).toBe('tok');
    expect(sessionCall?.[2]?.httpOnly).toBe(true);
  });

  it('returns a generic error on invalid credentials (no enumeration)', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ detail: 'Invalid email or password.' }), { status: 401 }),
    ));
    const res = await login(jsonRequest({ email: 'a@b.com', password: 'wrong' }));
    expect(res.status).toBe(401);
    expect(cookieSet).not.toHaveBeenCalled();
  });

  it('surfaces the disabled-account message', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ detail: 'Account disabled. Contact your administrator.' }), {
        status: 403,
      }),
    ));
    const res = await login(jsonRequest({ email: 'a@b.com', password: 'x' }));
    expect(res.status).toBe(403);
  });

  it('returns 503 when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('fetch failed');
    }));
    const res = await login(jsonRequest({ email: 'a@b.com', password: 'x' }));
    expect(res.status).toBe(503);
  });

  it('rejects missing fields', async () => {
    const res = await login(jsonRequest({ email: '', password: '' }));
    expect(res.status).toBe(400);
  });
});

describe('logout route handler', () => {
  it('clears the session and csrf cookies', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 204 })));
    const res = await logout();
    expect(res.status).toBe(204);
    expect(cookieDelete).toHaveBeenCalledWith('paymentops_session');
    expect(cookieDelete).toHaveBeenCalledWith('paymentops_csrf');
  });
});
