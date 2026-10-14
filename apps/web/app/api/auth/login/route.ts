import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import {
  CSRF_COOKIE,
  SESSION_COOKIE,
  csrfCookieOptions,
  internalApiUrl,
  operatorHeaders,
  sessionCookieOptions,
} from '@/lib/server/session';

const SESSION_MAX_AGE_SECONDS = 8 * 60 * 60;

export async function POST(request: Request) {
  let payload: { email?: unknown; password?: unknown };
  try {
    payload = (await request.json()) as { email?: unknown; password?: unknown };
  } catch {
    return NextResponse.json({ detail: 'Invalid request.' }, { status: 400 });
  }

  const email = typeof payload.email === 'string' ? payload.email.trim() : '';
  const password = typeof payload.password === 'string' ? payload.password : '';
  if (!email || !password) {
    return NextResponse.json({ detail: 'Email and password are required.' }, { status: 400 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${internalApiUrl()}/api/v1/auth/login`, {
      method: 'POST',
      headers: { ...operatorHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
      cache: 'no-store',
    });
  } catch {
    return NextResponse.json(
      { detail: 'Service temporarily unavailable. Please try again.' },
      { status: 503 },
    );
  }

  if (!upstream.ok) {
    const body = (await upstream.json().catch(() => ({}))) as { detail?: unknown };
    const detail = typeof body.detail === 'string' ? body.detail : 'Invalid email or password.';
    return NextResponse.json({ detail }, { status: upstream.status });
  }

  const data = (await upstream.json()) as { session_token?: string; user?: unknown };
  if (!data.session_token) {
    return NextResponse.json({ detail: 'Authentication failed.' }, { status: 502 });
  }

  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE, data.session_token, sessionCookieOptions(SESSION_MAX_AGE_SECONDS));
  cookieStore.set(CSRF_COOKIE, crypto.randomUUID(), csrfCookieOptions(SESSION_MAX_AGE_SECONDS));

  return NextResponse.json({ user: data.user });
}
