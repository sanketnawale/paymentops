'use client';

import { useEffect, useState } from 'react';
import AppShell from '@/components/AppShell';
import { Card, CardHead, ErrorState, PageHeader, Skeleton } from '@/components/ui';
import { getHealth, getInfo, getReadiness, type PlatformInfo, type ReadinessResult } from '@/lib/api';
import { badgeClass, labelize } from '@/lib/status';

export default function StatusPage() {
  const [info, setInfo] = useState<PlatformInfo | null>(null);
  const [ready, setReady] = useState<ReadinessResult | null>(null);
  const [health, setHealth] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getInfo(), getReadiness(), getHealth()])
      .then(([i, r, h]) => {
        setInfo(i);
        setReady(r);
        setHealth(h?.status ?? null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Unable to load status'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppShell>
      <PageHeader eyebrow="System" title="System status" description="Platform liveness, readiness and configuration." />

      {error ? <ErrorState message={error} /> : null}
      {loading ? <Card><Skeleton lines={3} /></Card> : null}

      {info ? (
        <div className="grid-2">
          <Card>
            <CardHead title="Platform" actions={<span className={badgeClass(health === 'ok' ? 'READY' : 'UNRESOLVED')}>{health === 'ok' ? 'Live' : 'Unknown'}</span>} />
            <div className="card-body">
              <ul className="status-list">
                <li><span className="label">Product</span><span>{info.product}</span></li>
                <li><span className="label">Version</span><span className="mono">{info.version}</span></li>
                <li><span className="label">Environment</span><span className={badgeClass(info.environment.toUpperCase())}>{info.environment}</span></li>
                <li><span className="label">AI</span><span>{info.ai_enabled ? info.ai_provider : 'Disabled (non-authoritative)'}</span></li>
              </ul>
            </div>
          </Card>

          <Card>
            <CardHead title="Readiness checks" sub="Dependencies" />
            <div className="card-body">
              <ul className="status-list">
                {(ready?.checks ?? []).map((c) => (
                  <li key={c.name}>
                    <span className="label">{labelize(c.name)}</span>
                    <span className={badgeClass(c.ok ? 'READY' : 'UNRESOLVED')}>{c.ok ? 'Ready' : 'Unavailable'}</span>
                  </li>
                ))}
                {(ready?.checks ?? []).length === 0 ? <li className="muted">No checks available.</li> : null}
              </ul>
            </div>
          </Card>
        </div>
      ) : null}
    </AppShell>
  );
}
