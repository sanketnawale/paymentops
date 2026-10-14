import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { CSRF_COOKIE, SESSION_COOKIE, internalApiUrl, operatorHeaders } from '@/lib/server/session';

export async function POST() {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;

  if (token) {
    // Best-effort server-side revocation; never block logout on upstream errors.
    try {
      await fetch(`${internalApiUrl()}/api/v1/auth/logout`, {
        method: 'POST',
        headers: { ...operatorHeaders(), 'X-Session-Token': token },
        cache: 'no-store',
      });
    } catch {
      // ignore
    }
  }

  cookieStore.delete(SESSION_COOKIE);
  cookieStore.delete(CSRF_COOKIE);
  return new NextResponse(null, { status: 204 });
}
