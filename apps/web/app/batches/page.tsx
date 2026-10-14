'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Database, Plus } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Button, Card, CardHead, EmptyState, ErrorState, PageHeader, Skeleton, TableWrap } from '@/components/ui';
import { listBatches, type BatchJobSummary } from '@/lib/api';
import { badgeClass, formatDateTime, labelize } from '@/lib/status';

export default function BatchesPage() {
  const [batches, setBatches] = useState<BatchJobSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setBatches(await listBatches());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load batches');
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
        eyebrow="Batch analysis"
        title="Batches"
        description="Monitor file-based analysis jobs and inspect aggregate readiness with record-level traceability."
        actions={<Link href="/batches/new" className="btn"><Plus size={14} /> New batch</Link>}
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}

      <Card noPad>
        <CardHead title="Batch jobs" sub="Files submitted to PaymentOps" actions={<Button variant="ghost" size="sm" onClick={load}>Refresh</Button>} />
        {loading ? (
          <div style={{ padding: '1.25rem' }}><Skeleton lines={4} /></div>
        ) : batches.length === 0 ? (
          <EmptyState title="No batch jobs yet" message="Submit a CSV batch to begin." />
        ) : (
          <TableWrap>
            <table className="data">
              <thead>
                <tr>
                  <th>Batch</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Ready</th>
                  <th>Repairable</th>
                  <th>Review</th>
                  <th>Failed</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {batches.map((b) => {
                  const pct = b.total_records ? Math.round((b.processed_records / b.total_records) * 100) : 0;
                  return (
                    <tr key={b.job_id}>
                      <td>
                        <Link href={`/batches/${b.job_id}`} className="row" style={{ gap: '0.5rem' }}>
                          <Database size={14} aria-hidden="true" /> <span className="mono">{b.job_id.slice(0, 12)}</span>
                        </Link>
                      </td>
                      <td><span className={badgeClass(b.status)}>{labelize(b.status)}</span></td>
                      <td style={{ minWidth: '9rem' }}>
                        <div className="progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
                          <span style={{ width: `${pct}%` }} />
                        </div>
                        <span className="muted small">{b.processed_records}/{b.total_records} ({pct}%)</span>
                      </td>
                      <td>{b.ready_count}</td>
                      <td>{b.repairable_count}</td>
                      <td>{b.review_required_count}</td>
                      <td>{b.failed_count}</td>
                      <td className="muted small">{formatDateTime(b.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </TableWrap>
        )}
      </Card>
    </AppShell>
  );
}
