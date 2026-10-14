import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { SESSION_COOKIE, isAuthorizedTenant, validateSessionToken } from '@/lib/server/session';

export async function GET() {
  const cookieStore = await cookies();
  const user = await validateSessionToken(cookieStore.get(SESSION_COOKIE)?.value);
  if (!user || !isAuthorizedTenant(user)) {
    return NextResponse.json({ detail: 'Not authenticated.' }, { status: 401 });
  }
  return NextResponse.json({ user });
}
