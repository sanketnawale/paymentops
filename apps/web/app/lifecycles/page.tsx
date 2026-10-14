'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import AppShell from '@/components/AppShell';
import { Card, CardHead, EmptyState, ErrorState, PageHeader, Skeleton, TableWrap } from '@/components/ui';
import { listLifecycles, type Lifecycle } from '@/lib/api';
import { badgeClass, formatDateTime, formatMinor, labelize } from '@/lib/status';

export default function LifecyclesPage() {
  const [lifecycles, setLifecycles] = useState<Lifecycle[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setLifecycles(await listLifecycles());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load lifecycles');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="ISO 20022 lifecycle"
        title="Payment lifecycles"
        description="Cross-message analytical lifecycles correlated from initiation through status and account reporting."
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}

      <Card noPad>
        <CardHead title="Lifecycles" sub="Analytical state only — PaymentOps does not execute these events" />
        {loading ? (
          <div style={{ padding: '1.25rem' }}><Skeleton lines={4} /></div>
        ) : lifecycles.length === 0 ? (
          <EmptyState title="No lifecycles yet" message="Analyze a payment or ingest an ISO message to create one." />
        ) : (
          <TableWrap>
            <table className="data">
              <thead>
                <tr><th>Lifecycle</th><th>End-to-end</th><th>Transaction</th><th>Amount</th><th>Status</th><th>Updated</th></tr>
              </thead>
              <tbody>
                {lifecycles.map((l) => (
                  <tr key={l.lifecycle_id}>
                    <td><Link href={`/lifecycles/${l.lifecycle_id}`} className="mono">{l.lifecycle_id}</Link></td>
                    <td className="mono">{l.end_to_end_id ?? '—'}</td>
                    <td className="mono">{l.transaction_id ?? '—'}</td>
                    <td>{formatMinor(l.amount_minor, l.currency)}</td>
                    <td><span className={badgeClass(l.current_status)}>{labelize(l.current_status)}</span></td>
                    <td className="muted small">{formatDateTime(l.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )}
      </Card>
    </AppShell>
  );
}
