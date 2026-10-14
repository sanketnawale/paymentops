import { NextRequest } from 'next/server';
import { describe, expect, it } from 'vitest';
import { middleware } from './middleware';

function req(path: string, cookie?: string): NextRequest {
  const headers: Record<string, string> = {};
  if (cookie) headers.cookie = cookie;
  return new NextRequest(`https://app.test${path}`, { headers });
}

describe('route protection middleware', () => {
  it('redirects anonymous /dashboard to /login', () => {
    const res = middleware(req('/dashboard'));
    expect(res.status).toBe(307);
    expect(res.headers.get('location')).toContain('/login');
  });

  it('redirects anonymous /cases to /login with next param', () => {
    const res = middleware(req('/cases'));
    expect(res.status).toBe(307);
    const location = res.headers.get('location') ?? '';
    expect(location).toContain('/login');
    expect(location).toContain('next=%2Fcases');
  });

  it('redirects anonymous root to /login', () => {
    const res = middleware(req('/'));
    expect(res.status).toBe(307);
    expect(res.headers.get('location')).toContain('/login');
  });

  it('sends authenticated root to /dashboard', () => {
    const res = middleware(req('/', 'paymentops_session=abc'));
    expect(res.status).toBe(307);
    expect(res.headers.get('location')).toContain('/dashboard');
  });

  it('allows authenticated access to protected routes', () => {
    const res = middleware(req('/account-reports', 'paymentops_session=abc'));
    expect(res.headers.get('location')).toBeNull();
  });

  it('allows anonymous access to /login', () => {
    const res = middleware(req('/login'));
    expect(res.headers.get('location')).toBeNull();
  });
});
