'use client';

import { type FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Lock, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui';

const MARKETING_URL = process.env.NEXT_PUBLIC_MARKETING_URL ?? 'https://paymentops.cloudnova.tech';

function safeNextPath(): string {
  if (typeof window === 'undefined') return '/dashboard';
  const next = new URLSearchParams(window.location.search).get('next');
  if (next && next.startsWith('/') && !next.startsWith('//')) return next;
  return '/dashboard';
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError('Enter your work email and password to continue.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      if (res.ok) {
        router.replace(safeNextPath());
        router.refresh();
        return;
      }
      const body = (await res.json().catch(() => ({}))) as { detail?: string };
      if (res.status === 503) {
        setError('Service temporarily unavailable. Please try again shortly.');
      } else if (res.status === 403) {
        setError(body.detail ?? 'Account disabled. Contact your administrator.');
      } else {
        setError('Invalid email or password.');
      }
    } catch {
      setError('Service temporarily unavailable. Please try again shortly.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-shell">
      <section className="login-aside" aria-label="About CloudNova PaymentOps">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">C</span>
          <span className="brand-name">
            CloudNova <span>PaymentOps</span>
          </span>
        </div>
        <div style={{ maxWidth: '26rem' }}>
          <p className="page-eyebrow" style={{ color: '#e0a082' }}>Payment data intelligence</p>
          <h1 className="display" style={{ fontSize: '2.6rem', lineHeight: 1.05, letterSpacing: '-0.04em', margin: '1rem 0 0' }}>
            Make every payment state explainable.
          </h1>
          <p style={{ marginTop: '1.25rem', fontSize: '0.9rem', lineHeight: 1.7, color: 'var(--cn-sidebar-muted)' }}>
            A control surface for analysts who validate, repair, match and reconcile payment data —
            with a deterministic, auditable evidence trail.
          </p>
        </div>
        <p className="row" style={{ color: 'var(--cn-sidebar-faint)', fontSize: '0.72rem' }}>
          <ShieldCheck size={14} aria-hidden="true" /> Payment data intelligence &amp; exception operations
        </p>
      </section>

      <section className="login-main">
        <div className="login-form-wrap">
          <div className="brand" style={{ marginBottom: '2rem' }}>
            <span className="brand-mark" aria-hidden="true">C</span>
            <span className="brand-name" style={{ color: 'var(--cn-text)' }}>
              CloudNova <span style={{ opacity: 0.6 }}>PaymentOps</span>
            </span>
          </div>

          <p className="page-eyebrow">Authorized user access</p>
          <h2 className="page-title" style={{ fontSize: '1.6rem' }}>Sign in to PaymentOps</h2>
          <p className="muted small" style={{ marginTop: '0.5rem' }}>
            Payment Data Intelligence &amp; Exception Operations
          </p>

          <form onSubmit={onSubmit} className="stack" style={{ marginTop: '1.75rem' }} aria-label="Sign in">
            <label>
              <span className="field-label">Work email</span>
              <input
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-label="Work email"
                required
              />
            </label>
            <label>
              <span className="field-label">Password</span>
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-label="Password"
                required
              />
            </label>
            {error ? <p className="small" style={{ color: 'var(--cn-danger)', margin: 0 }} role="alert">{error}</p> : null}
            <Button type="submit" disabled={busy}>
              <Lock size={14} /> {busy ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>

          <div style={{ marginTop: '1rem' }}>
            <Button variant="ghost" disabled title="Enterprise SSO is not yet available" style={{ width: '100%' }}>
              Enterprise SSO — coming later
            </Button>
          </div>

          <div className="stack" style={{ marginTop: '1.25rem' }}>
            <a className="small" href={MARKETING_URL}>Learn about PaymentOps</a>
            <a className="small" href={`${MARKETING_URL}/request-demo`}>Request access / Request demo</a>
          </div>

          <p className="muted" style={{ marginTop: '1.75rem', fontSize: '0.72rem', lineHeight: 1.6 }}>
            Authorized users only. Activity may be logged for security and audit purposes.
          </p>
          <p className="muted" style={{ marginTop: '0.5rem', fontSize: '0.72rem', lineHeight: 1.6 }}>
            PaymentOps analyzes and reconciles payment data. It does not execute, authorize, settle,
            debit or credit payments.
          </p>
        </div>
      </section>
    </div>
  );
}
