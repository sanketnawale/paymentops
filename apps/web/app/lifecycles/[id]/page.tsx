'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, ShieldCheck } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Button, Card, CardHead, EmptyState, ErrorState, Notice, PageHeader, Skeleton } from '@/components/ui';
import { decideCorrelation, getLifecycle, type Correlation, type Lifecycle, type LifecycleEvent } from '@/lib/api';
import { badgeClass, formatDateTime, formatMinor, labelize } from '@/lib/status';

export default function LifecycleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [lifecycle, setLifecycle] = useState<Lifecycle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setLifecycle(await getLifecycle(id));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load lifecycle');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const act = async (correlationId: string, action: string) => {
    setBusy(true);
    setActionError(null);
    try {
      await decideCorrelation(id, correlationId, action, note || undefined);
      setNote('');
      await load();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Action failed');
    } finally {
      setBusy(false);
    }
  };

  const events = lifecycle?.events ?? [];

  return (
    <AppShell>
      <PageHeader
        eyebrow={`Payment lifecycle / ${id}`}
        title="Lifecycle timeline"
        description="Correlated ISO messages across initiation, transfer, status and account reporting."
        actions={<Link href="/lifecycles" className="btn btn-ghost"><ArrowLeft size={14} /> All lifecycles</Link>}
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}
      {loading && !lifecycle ? <Card><Skeleton lines={5} /></Card> : null}

      {lifecycle ? (
        <>
          <Notice tone="accent">
            <ShieldCheck size={15} aria-hidden="true" />
            <span>Analytical lifecycle only. PaymentOps did not perform any of these financial events.</span>
          </Notice>

          <div className="grid-sidebar">
            <Card>
              <CardHead title="Timeline" sub="Initiation → transfer → status → account reporting" actions={<span className={badgeClass(lifecycle.current_status)}>{labelize(lifecycle.current_status)}</span>} />
              <div className="card-body">
                {events.length === 0 ? (
                  <EmptyState title="No events yet" />
                ) : (
                  <div className="timeline">
                    {events.map((e: LifecycleEvent) => (
                      <div key={e.id} className={`timeline-item ${['ACCEPTED', 'RECONCILED', 'ACCOUNT_EVENT_CONFIRMED'].includes(e.status) ? 'ok' : ['REJECTED', 'UNMATCHED', 'UNRESOLVED'].includes(e.status) ? 'danger' : ''}`}>
                        <div className="row-between">
                          <p style={{ margin: 0, fontWeight: 600, fontSize: '0.85rem' }}>{labelize(e.event_type)}</p>
                          <span className={badgeClass(e.status)}>{labelize(e.status)}{e.raw_status_code ? ` (${e.raw_status_code})` : ''}</span>
                        </div>
                        <p className="muted small" style={{ margin: '0.25rem 0 0' }}>
                          {e.message_definition ?? '—'} ({e.message_version ?? '—'}) · {formatDateTime(e.timestamp)}
                        </p>
                        {(e.correlation_evidence ?? []).length > 0 ? (
                          <p className="muted small" style={{ margin: '0.25rem 0 0' }}>
                            Evidence: {(e.correlation_evidence ?? []).join(', ')}
                          </p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Card>

            <div className="stack">
              <Card>
                <CardHead title="References" sub="Lifecycle identifiers" />
                <div className="card-body">
                  <ul className="status-list">
                    <li><span className="label">End-to-end ID</span><span className="mono">{lifecycle.end_to_end_id ?? '—'}</span></li>
                    <li><span className="label">Instruction ID</span><span className="mono">{lifecycle.instruction_id ?? '—'}</span></li>
                    <li><span className="label">Transaction ID</span><span className="mono">{lifecycle.transaction_id ?? '—'}</span></li>
                    <li><span className="label">Original message</span><span className="mono">{lifecycle.original_message_id ?? '—'}</span></li>
                    <li><span className="label">Amount</span><span>{formatMinor(lifecycle.amount_minor, lifecycle.currency)}</span></li>
                    <li><span className="label">Created</span><span>{formatDateTime(lifecycle.created_at)}</span></li>
                    <li><span className="label">Updated</span><span>{formatDateTime(lifecycle.updated_at)}</span></li>
                  </ul>
                </div>
              </Card>

              <Card>
                <CardHead title="Correlation review" sub="Operator decisions on ambiguous correlations" />
                <div className="card-body">
                  {actionError ? <Notice tone="danger">{actionError}</Notice> : null}
                  <label><span className="field-label">Note (applies to next action)</span><input type="text" value={note} onChange={(e) => setNote(e.target.value)} /></label>
                  {(lifecycle.correlations ?? []).length === 0 ? (
                    <EmptyState title="No correlations recorded" />
                  ) : (
                    (lifecycle.correlations ?? []).map((c: Correlation) => {
                      const decided = ['CORRELATED', 'UNRESOLVED'].includes(c.correlation_status);
                      return (
                        <div key={c.id} style={{ borderTop: '1px solid var(--cn-border)', paddingTop: '0.75rem', marginTop: '0.75rem' }}>
                          <div className="row-between">
                            <span className="mono small">{c.source_message_id ?? '—'} → {c.candidate_message_id ?? '—'}</span>
                            <span className={badgeClass(c.correlation_status)}>{labelize(c.correlation_status)}</span>
                          </div>
                          {c.evidence.length > 0 ? <p className="muted small">Evidence: {c.evidence.join(', ')}</p> : null}
                          {c.conflicts.length > 0 ? <p className="small" style={{ color: 'var(--cn-danger)' }}>Conflicts: {c.conflicts.join(', ')}</p> : null}
                          <div className="row" style={{ marginTop: '0.5rem' }}>
                            <Button size="sm" onClick={() => act(c.id, 'confirm')} disabled={busy || decided}>Confirm correlation</Button>
                            <Button size="sm" variant="ghost" onClick={() => act(c.id, 'reject')} disabled={busy || decided}>Reject</Button>
                            <Button size="sm" variant="ghost" onClick={() => act(c.id, 'leave')} disabled={busy || decided}>Leave unresolved</Button>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </Card>
            </div>
          </div>
        </>
      ) : null}
    </AppShell>
  );
}
