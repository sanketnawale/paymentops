import { type NextRequest, NextResponse } from 'next/server';

// Route protection. Anonymous users are redirected to /login for all application routes.
// The authenticated API proxy (/api/backend/*) performs its own full session validation, so
// this middleware only guards page navigation (cookie presence; the proxy enforces validity).

const SESSION_COOKIE = 'paymentops_session';

const PROTECTED_PREFIXES = [
  '/dashboard',
  '/analyze',
  '/cases',
  '/batches',
  '/investigations',
  '/profiles',
  '/matching',
  '/reconciliation',
  '/iso-messages',
  '/lifecycles',
  '/account-reports',
  '/account-entries',
  '/readiness',
  '/audit',
  '/api-clients',
  '/settings',
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE)?.value);

  if (pathname === '/') {
    const url = request.nextUrl.clone();
    url.pathname = hasSession ? '/dashboard' : '/login';
    url.search = '';
    return NextResponse.redirect(url);
  }

  const isProtected = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );

  if (isProtected && !hasSession) {
    const url = request.nextUrl.clone();
    url.pathname = '/login';
    url.search = '';
    url.searchParams.set('next', pathname);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  // Run on pages only; exclude Next internals, static files, and API routes (the proxy and
  // auth route handlers validate their own sessions).
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|.*\\..*).*)'],
};
