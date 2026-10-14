'use client';

import { useCallback, useEffect, useState } from 'react';
import { BookOpen, ShieldCheck } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Card, CardHead, EmptyState, ErrorState, Metric, Notice, PageHeader, Skeleton } from '@/components/ui';
import { getDashboard, type DashboardMetrics } from '@/lib/api';

const DEV_COVERAGE = [
  ['Italy', 'IT'],
  ['India', 'IN'],
  ['Saudi Arabia', 'SA'],
  ['United Kingdom', 'GB'],
  ['Germany', 'DE'],
  ['France', 'FR'],
  ['Spain', 'ES'],
  ['Netherlands', 'NL'],
];

export default function ReadinessPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setMetrics(await getDashboard());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load readiness');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const total = metrics
    ? metrics.ready + metrics.repairable + metrics.review_required + metrics.unresolved
    : 0;
  const overall = total ? Math.round((metrics!.ready / total) * 1000) / 10 : 0;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Customer report"
        title="Readiness report"
        description="A defensible view of payment-data coverage, exceptions, and supported geography."
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}
      {loading && !metrics ? <Card><Skeleton lines={3} /></Card> : null}

      {metrics ? (
        <>
          <div className="metric-grid">
            <Metric label="Overall readiness" value={`${overall}%`} detail="Ready share of analyzed records" tone="ok" icon={<ShieldCheck size={17} />} />
            <Metric label="Ready" value={metrics.ready.toLocaleString()} tone="ok" />
            <Metric label="Repairable" value={metrics.repairable.toLocaleString()} tone="warn" />
            <Metric label="Review required" value={metrics.review_required.toLocaleString()} tone="warn" />
            <Metric label="Unresolved" value={metrics.unresolved.toLocaleString()} tone="danger" />
          </div>

          <div className="grid-2" style={{ marginTop: '1.25rem' }}>
            <Card>
              <CardHead title="Development address coverage" sub="Countries available in the development corpus" />
              <div className="card-body">
                {DEV_COVERAGE.length === 0 ? (
                  <EmptyState title="No coverage" />
                ) : (
                  <ul className="status-list">
                    {DEV_COVERAGE.map(([name, code]) => (
                      <li key={code}><span>{name}</span><span className="mono">{code}</span></li>
                    ))}
                  </ul>
                )}
                <Notice tone="warn" style={{ marginTop: '0.75rem' }}>
                  <BookOpen size={15} aria-hidden="true" />
                  <span>Additional geography datasets are configured according to production/customer requirements. This is not a claim of global coverage.</span>
                </Notice>
              </div>
            </Card>

            <Card>
              <CardHead title="Coverage states" sub="How PaymentOps reports geography" />
              <div className="card-body">
                <ul className="status-list">
                  <li><span className="badge badge-ok">SUPPORTED</span><span className="muted small">Address fully analysed</span></li>
                  <li><span className="badge badge-danger">UNSUPPORTED_GEOGRAPHY</span><span className="muted small">Outside development corpus</span></li>
                  <li><span className="badge badge-muted">UNKNOWN</span><span className="muted small">Insufficient evidence</span></li>
                </ul>
              </div>
            </Card>
          </div>
        </>
      ) : null}
    </AppShell>
  );
}
