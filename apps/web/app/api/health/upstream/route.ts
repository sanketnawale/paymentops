import { NextResponse } from 'next/server';
import { internalApiUrl } from '@/lib/server/session';

// Unauthenticated upstream health probe. Returns only liveness of the private backend; no
// tenant data is exposed. The authenticated API surface lives under /api/backend/*.
export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  try {
    const res = await fetch(`${internalApiUrl()}/health`, { cache: 'no-store' });
    if (!res.ok) {
      return NextResponse.json({ status: 'unavailable' }, { status: 503 });
    }
    return NextResponse.json({ status: 'ok', upstream: 'ok' });
  } catch {
    return NextResponse.json({ status: 'unavailable' }, { status: 503 });
  }
}
