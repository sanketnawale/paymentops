'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, Download } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Button, Card, CardHead, ErrorState, Metric, PageHeader, Skeleton } from '@/components/ui';
import { getBatch, type BatchJobSummary } from '@/lib/api';
import { badgeClass, formatDateTime, labelize } from '@/lib/status';

export default function BatchDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [batch, setBatch] = useState<BatchJobSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const b = await getBatch(id);
      setBatch(b);
      setError(null);
      if (b.status === 'RUNNING' || b.status === 'QUEUED') {
        setTimeout(load, 2000);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load batch');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const pct = batch && batch.total_records > 0 ? Math.round((batch.processed_records / batch.total_records) * 100) : 0;

  const downloadReport = () => {
    if (!batch) return;
    const blob = new Blob([JSON.stringify(batch.report ?? {}, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `batch-${id.slice(0, 12)}-report.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow={`Batch / ${id.slice(0, 12)}`}
        title="Batch analysis"
        description={batch ? `Profile ${batch.profile_id} · version ${batch.profile_version}` : undefined}
        actions={<Link href="/batches" className="btn btn-ghost"><ArrowLeft size={14} /> All batches</Link>}
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}
      {loading && !batch ? <Card><Skeleton lines={4} /></Card> : null}

      {batch ? (
        <>
          <div className="metric-grid">
            <Metric label="Status" value={labelize(batch.status)} detail={`${pct}% processed`} />
            <Metric label="Total records" value={batch.total_records} />
            <Metric label="Ready" value={batch.ready_count} tone="ok" />
            <Metric label="Repairable" value={batch.repairable_count} tone="warn" />
            <Metric label="Review" value={batch.review_required_count} tone="warn" />
            <Metric label="Unresolved" value={batch.unresolved_count} tone="danger" />
            <Metric label="Failed" value={batch.failed_count} tone="danger" />
          </div>

          <Card>
            <CardHead title="Progress" sub="Live async job state" actions={<span className={badgeClass(batch.status)}>{labelize(batch.status)}</span>} />
            <div className="card-body">
              <div className="progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
                <span style={{ width: `${pct}%` }} />
              </div>
              <ul className="status-list" style={{ marginTop: '1rem' }}>
                <li><span className="label">Processed</span><span className="mono">{batch.processed_records} / {batch.total_records}</span></li>
                <li><span className="label">Created</span><span>{formatDateTime(batch.created_at)}</span></li>
                <li><span className="label">Completed</span><span>{formatDateTime(batch.completed_at)}</span></li>
              </ul>
              {['COMPLETED', 'PARTIAL'].includes(batch.status) ? (
                <Button variant="ghost" onClick={downloadReport} style={{ marginTop: '0.75rem' }}>
                  <Download size={14} /> Download report
                </Button>
              ) : null}
            </div>
          </Card>
        </>
      ) : null}
    </AppShell>
  );
}
