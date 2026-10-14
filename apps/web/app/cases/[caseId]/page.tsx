'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { AlertTriangle, ArrowLeft, ShieldCheck } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Button, Card, CardHead, EmptyState, ErrorState, Notice, PageHeader, Skeleton } from '@/components/ui';
import { caseAction, getCase, type CaseDetail } from '@/lib/api';
import { badgeClass, formatDateTime, labelize } from '@/lib/status';

export default function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setDetail(await getCase(caseId));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load case');
    }
  }, [caseId]);

  useEffect(() => {
    load();
  }, [load]);

  const act = async (action: string) => {
    setBusy(true);
    setActionError(null);
    try {
      await caseAction(caseId, action, note || undefined);
      setNote('');
      await load();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Action failed');
    } finally {
      setBusy(false);
    }
  };

  const finished = detail ? ['APPROVED', 'REJECTED', 'CLOSED'].includes(detail.status) : false;

  return (
    <AppShell>
      <PageHeader
        eyebrow={`Case / ${caseId}`}
        title={detail?.message_type ? `${detail.message_type} analysis` : 'Case investigation'}
        description={detail ? `${labelize(detail.status)} · profile v${detail.integration_profile_version ?? '—'} · mapping ${detail.mapping_version ?? '—'}` : undefined}
        actions={<Link href="/cases" className="btn btn-ghost"><ArrowLeft size={14} /> All cases</Link>}
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}

      {!detail && !error ? <Card><Skeleton lines={5} /></Card> : null}

      {detail ? (
        <>
          <Notice tone="accent">
            <ShieldCheck size={15} aria-hidden="true" />
            <span>
              <strong>Analysis only.</strong> Approval in PaymentOps approves an analytical/data-repair decision only.
              It does not authorize or execute a payment.
            </span>
          </Notice>

          <div className="grid-sidebar">
            <div className="stack">
              <Card>
                <CardHead title="Summary" sub="Case metadata and validation state" actions={<span className={badgeClass(detail.status)}>{labelize(detail.status)}</span>} />
                <div className="card-body">
                  <ul className="status-list">
                    <li><span className="label">Validation</span><span className={badgeClass(detail.validation_status)}>{labelize(detail.validation_status)}</span></li>
                    <li><span className="label">Address readiness</span><span className={badgeClass(detail.address_readiness)}>{labelize(detail.address_readiness)}</span></li>
                    <li><span className="label">Repair status</span><span>{labelize(detail.repair_status)}</span></li>
                    <li><span className="label">Address provider</span><span>{detail.address_provider ?? '—'} {detail.address_provider_coverage ? `(${detail.address_provider_coverage})` : ''}</span></li>
                    <li><span className="label">Ruleset version</span><span className="mono">{detail.ruleset_version ?? '—'}</span></li>
                    <li><span className="label">Mapping version</span><span className="mono">{detail.mapping_version ?? '—'}</span></li>
                    <li><span className="label">Engine version</span><span className="mono">{detail.engine_version ?? '—'}</span></li>
                    <li><span className="label">Input hash</span><span className="mono">{detail.input_hash ? `${detail.input_hash.slice(0, 16)}…` : '—'}</span></li>
                  </ul>
                </div>
              </Card>

              <Card>
                <CardHead title="Rule findings" sub="Deterministic findings against the source payload" />
                <div className="card-body">
                  {(detail.findings ?? []).length === 0 ? (
                    <EmptyState title="No rule findings" message="No deterministic rule findings were recorded for this case." />
                  ) : (
                    <ul className="status-list">
                      {(detail.findings ?? []).map((f, i) => (
                        <li key={`${f.rule_id}-${i}`}>
                          <span>
                            <strong className="mono">{f.rule_id}</strong> · {f.message}
                          </span>
                          <span className={badgeClass(f.severity)}>{labelize(f.severity)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </Card>

              <Card>
                <CardHead title="Audit timeline" sub="Append-oriented record of case events" />
                <div className="card-body">
                  {(detail.audit ?? []).length === 0 ? (
                    <EmptyState title="No audit events" />
                  ) : (
                    <div className="timeline">
                      {(detail.audit ?? []).map((a, i) => (
                        <div className="timeline-item" key={i}>
                          <p style={{ margin: 0, fontWeight: 600, fontSize: '0.8rem' }}>{labelize(a.event)}</p>
                          <p className="muted small" style={{ margin: '0.2rem 0 0' }}>
                            {a.actor ?? 'system'} · {formatDateTime(a.timestamp)}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </Card>
            </div>

            <div className="stack">
              <Card>
                <CardHead title="Operator actions" sub="Decisions are analytical and audited" />
                <div className="card-body">
                  <label>
                    <span className="field-label">Note (optional)</span>
                    <input type="text" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add a note for the audit trail" />
                  </label>
                  {actionError ? <p className="small" style={{ color: 'var(--cn-danger)' }} role="alert">{actionError}</p> : null}
                  <div className="stack" style={{ marginTop: '1rem' }}>
                    <Button onClick={() => act('approve')} disabled={busy || finished}>Approve repair candidate</Button>
                    <Button variant="ghost" onClick={() => act('reject')} disabled={busy || finished}>Reject</Button>
                    <Button variant="ghost" onClick={() => act('close')} disabled={busy || finished}>Close case</Button>
                  </div>
                  {finished ? (
                    <p className="muted small" style={{ marginTop: '0.75rem' }}>
                      <AlertTriangle size={13} aria-hidden="true" /> Case is {labelize(detail.status)}. Actions are disabled.
                    </p>
                  ) : null}
                </div>
              </Card>
            </div>
          </div>
        </>
      ) : null}
    </AppShell>
  );
}
