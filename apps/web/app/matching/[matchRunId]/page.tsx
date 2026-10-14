'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Button, Card, CardHead, EmptyState, ErrorState, Notice, PageHeader, Skeleton, TableWrap } from '@/components/ui';
import { decideCandidate, getReconciliation, type MatchCandidate, type ReconciliationRun } from '@/lib/api';
import { badgeClass, labelize } from '@/lib/status';

export default function MatchDetailPage() {
  const { matchRunId } = useParams<{ matchRunId: string }>();
  const [run, setRun] = useState<ReconciliationRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRun(await getReconciliation(matchRunId));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load match run');
    } finally {
      setLoading(false);
    }
  }, [matchRunId]);

  useEffect(() => {
    load();
  }, [load]);

  const act = async (candidateId: string, action: string) => {
    setBusy(true);
    setActionError(null);
    try {
      await decideCandidate(candidateId, action, note || undefined);
      setNote('');
      await load();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Action failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow={`Match run / ${matchRunId.slice(0, 12)}`}
        title="Match investigation"
        description="Field-by-field deterministic comparison with operator review."
        actions={<Link href="/matching" className="btn btn-ghost"><ArrowLeft size={14} /> Matching</Link>}
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}
      {loading && !run ? <Card><Skeleton lines={4} /></Card> : null}

      {run ? (
        <>
          <div className="metric-grid">
            <div className="metric"><p className="metric-label">Status</p><p className="metric-value">{labelize(run.status)}</p></div>
            <div className="metric"><p className="metric-label">Total</p><p className="metric-value">{run.total}</p></div>
            <div className="metric"><p className="metric-label">Matched</p><p className="metric-value" style={{ color: 'var(--cn-ok)' }}>{run.matched}</p></div>
            <div className="metric"><p className="metric-label">Possible</p><p className="metric-value" style={{ color: 'var(--cn-warn)' }}>{run.possible_match}</p></div>
            <div className="metric"><p className="metric-label">Review</p><p className="metric-value" style={{ color: 'var(--cn-warn)' }}>{run.review_required}</p></div>
            <div className="metric"><p className="metric-label">Unmatched</p><p className="metric-value" style={{ color: 'var(--cn-danger)' }}>{run.unmatched}</p></div>
            <div className="metric"><p className="metric-label">Duplicate</p><p className="metric-value">{run.duplicate_candidate}</p></div>
          </div>

          <Card>
            <CardHead title="Candidates" sub="Each candidate shows field-level evidence" actions={<span className="muted small">Policy v{run.policy_version ?? '—'}</span>} />
            <div className="card-body">
              {actionError ? <Notice tone="danger">{actionError}</Notice> : null}
              <label><span className="field-label">Note (applies to next action)</span><input type="text" value={note} onChange={(e) => setNote(e.target.value)} /></label>
            </div>
            {(run.candidates ?? []).length === 0 ? (
              <EmptyState title="No candidates" message="This run produced no candidate matches." />
            ) : (
              (run.candidates ?? []).map((c: MatchCandidate) => <CandidateBlock key={c.candidate_id} c={c} onAction={act} busy={busy} />)
            )}
          </Card>
        </>
      ) : null}
    </AppShell>
  );
}

function CandidateBlock({
  c,
  onAction,
  busy,
}: {
  c: MatchCandidate;
  onAction: (id: string, action: string) => void;
  busy: boolean;
}) {
  const fields = c.field_results ?? [];
  const decided = ['CONFIRMED', 'REJECTED', 'DUPLICATE', 'REVIEW_REQUIRED'].includes(c.status);
  return (
    <div className="card-body" style={{ borderTop: '1px solid var(--cn-border)' }}>
      <div className="row-between">
        <p className="mono small">{c.source_record_id} → {c.candidate_record_id}</p>
        <span className={badgeClass(c.classification)}>{labelize(c.classification)}</span>
      </div>
      <ul className="status-list">
        <li><span className="label">Match score (deterministic)</span><span className="mono">{c.match_score}</span></li>
        <li><span className="label">Status</span><span>{labelize(c.status)}</span></li>
      </ul>
      {fields.length > 0 ? (
        <TableWrap>
          <table className="data">
            <thead><tr><th>Field</th><th>Similarity</th><th>Weight</th><th>Status</th><th>Explanation</th></tr></thead>
            <tbody>
              {fields.map((f) => (
                <tr key={f.field}>
                  <td className="mono">{f.field}</td>
                  <td>{f.similarity}</td>
                  <td>{f.weight}</td>
                  <td><span className={badgeClass(f.status)}>{labelize(f.status)}</span></td>
                  <td className="mono muted">{f.explanation_code ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      ) : null}
      <div className="row" style={{ marginTop: '0.75rem' }}>
        <Button size="sm" onClick={() => onAction(c.candidate_id, 'confirm')} disabled={busy || decided}>Confirm match</Button>
        <Button size="sm" variant="ghost" onClick={() => onAction(c.candidate_id, 'reject')} disabled={busy || decided}>Reject</Button>
        <Button size="sm" variant="ghost" onClick={() => onAction(c.candidate_id, 'duplicate')} disabled={busy || decided}>Mark duplicate</Button>
        <Button size="sm" variant="ghost" onClick={() => onAction(c.candidate_id, 'review')} disabled={busy || decided}>Review</Button>
      </div>
      {decided ? <p className="muted small" style={{ marginTop: '0.5rem' }}>Candidate is {labelize(c.status)}. Actions disabled.</p> : null}
    </div>
  );
}
