'use client';

import { useEffect, useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Card, CardHead, ErrorState, Notice, PageHeader, Skeleton } from '@/components/ui';
import { getInfo, getReadiness, type PlatformInfo, type ReadinessResult } from '@/lib/api';
import { badgeClass, labelize } from '@/lib/status';

export default function SettingsPage() {
  const [info, setInfo] = useState<PlatformInfo | null>(null);
  const [ready, setReady] = useState<ReadinessResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getInfo(), getReadiness()])
      .then(([i, r]) => {
        setInfo(i);
        setReady(r);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Unable to load settings'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Organization"
        title="Settings"
        description="Workspace configuration for retention, address intelligence, API access and security."
      />

      {error ? <ErrorState message={error} /> : null}
      {loading ? <Card><Skeleton lines={4} /></Card> : null}

      {info ? (
        <div className="grid-2">
          <Card>
            <CardHead title="Platform" sub="Environment and product information" />
            <div className="card-body">
              <ul className="status-list">
                <li><span className="label">Product</span><span>{info.product}</span></li>
                <li><span className="label">Release</span><span>{info.release ?? 'v1 Evaluation Release'}</span></li>
                <li><span className="label">Version</span><span className="mono">{info.version}</span></li>
                <li><span className="label">Build</span><span className="mono">{info.build_sha ? info.build_sha.slice(0, 12) : 'unknown'}</span></li>
                <li><span className="label">Build date</span><span className="mono">{info.build_date ?? 'unknown'}</span></li>
                <li><span className="label">Environment</span><span className={badgeClass(info.environment.toUpperCase())}>{info.environment}</span></li>
                <li><span className="label">Zero retention</span><span>{info.zero_retention_enabled ? 'Enabled' : 'Disabled'}</span></li>
              </ul>
            </div>
          </Card>

          <Card>
            <CardHead title="Address intelligence" sub="Deterministic address resolution" />
            <div className="card-body">
              <ul className="status-list">
                <li><span className="label">Address intelligence</span><span className="badge badge-ok">Enabled</span></li>
                <li><span className="label">Coverage</span><span className="muted small">IT, IN, SA, GB, DE, FR, ES, NL (development corpus)</span></li>
              </ul>
              <Notice tone="warn" style={{ marginTop: '0.75rem' }}>
                Additional geography datasets are configured according to production/customer requirements.
              </Notice>
            </div>
          </Card>

          <Card>
            <CardHead title="API & AI" sub="Platform capabilities" />
            <div className="card-body">
              <ul className="status-list">
                <li><span className="label">Database configured</span><span>{info.database_configured ? 'Yes' : 'No'}</span></li>
                <li><span className="label">Redis configured</span><span>{info.redis_configured ? 'Yes' : 'No'}</span></li>
                <li><span className="label">AI provider</span><span>{info.ai_enabled ? info.ai_provider : 'Disabled (non-authoritative)'}</span></li>
              </ul>
              <Notice tone="accent" style={{ marginTop: '0.75rem' }}>
                AI is optional and non-authoritative. Deterministic validation is the source of truth.
              </Notice>
            </div>
          </Card>

          <Card>
            <CardHead title="Security & readiness" sub="Dependency health" />
            <div className="card-body">
              <ul className="status-list">
                {(ready?.checks ?? []).map((c) => (
                  <li key={c.name}>
                    <span className="label">{labelize(c.name)}</span>
                    <span className={badgeClass(c.ok ? 'READY' : 'UNRESOLVED')}>{c.ok ? 'Ready' : 'Unavailable'}</span>
                  </li>
                ))}
                {(ready?.checks ?? []).length === 0 ? <li className="muted">No dependency checks available.</li> : null}
              </ul>
              <p className="muted small" style={{ marginTop: '0.75rem' }}>
                <ShieldCheck size={13} aria-hidden="true" /> Workspace settings are managed by the platform operator.
                Retention and security policies are enforced server-side.
              </p>
            </div>
          </Card>
        </div>
      ) : null}
    </AppShell>
  );
}
