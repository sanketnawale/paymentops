'use client';

import { useState } from 'react';
import Link from 'next/link';
import AppShell from '@/components/AppShell';
import { Button, Card, CardHead, EmptyState, ErrorState, Notice, PageHeader, TableWrap } from '@/components/ui';
import { evaluateMatch, searchCandidates, type CandidateMatch, type MatchDecision, type MatchRecord } from '@/lib/api';
import { badgeClass, labelize } from '@/lib/status';

const EMPTY: MatchRecord = {
  record_id: '',
  record_type: 'PAYMENT',
  organization_id: '',
  amount: '',
  currency: 'EUR',
  remittance_reference: '',
  creditor_name: '',
  value_date: '',
  debtor_account: '',
};

export default function MatchingPage() {
  const [a, setA] = useState<MatchRecord>({ ...EMPTY, record_id: 'source-1', record_type: 'INVOICE' });
  const [b, setB] = useState<MatchRecord>({ ...EMPTY, record_id: 'candidate-1', record_type: 'PAYMENT' });
  const [decision, setDecision] = useState<MatchDecision | null>(null);
  const [candidates, setCandidates] = useState<CandidateMatch[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (mode: 'evaluate' | 'candidates') => {
    setBusy(true);
    setError(null);
    try {
      if (mode === 'evaluate') {
        setDecision(await evaluateMatch({ record_a: a, record_b: b }));
        setCandidates([]);
      } else {
        setCandidates(await searchCandidates(a));
        setDecision(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed');
    } finally {
      setBusy(false);
    }
  };

  const recordForm = (label: string, r: MatchRecord, set: (v: MatchRecord) => void) => (
    <Card>
      <CardHead title={label} />
      <div className="card-body">
        <div className="stack">
          <label><span className="field-label">Record ID</span><input type="text" value={r.record_id} onChange={(e) => set({ ...r, record_id: e.target.value })} /></label>
          <label><span className="field-label">Type</span>
            <select value={r.record_type} onChange={(e) => set({ ...r, record_type: e.target.value })}>
              {['PAYMENT', 'EXPECTED_PAYMENT', 'INVOICE', 'LEDGER_ENTRY', 'ACCOUNT_EVENT'].map((t) => <option key={t}>{t}</option>)}
            </select>
          </label>
          <label><span className="field-label">Amount</span><input type="text" value={String(r.amount ?? '')} onChange={(e) => set({ ...r, amount: e.target.value })} /></label>
          <label><span className="field-label">Currency</span><input type="text" value={r.currency ?? ''} onChange={(e) => set({ ...r, currency: e.target.value })} /></label>
          <label><span className="field-label">End-to-end ID</span><input type="text" value={r.end_to_end_id ?? ''} onChange={(e) => set({ ...r, end_to_end_id: e.target.value })} /></label>
          <label><span className="field-label">Transaction ID</span><input type="text" value={r.transaction_id ?? ''} onChange={(e) => set({ ...r, transaction_id: e.target.value })} /></label>
          <label><span className="field-label">Reference</span><input type="text" value={r.remittance_reference ?? ''} onChange={(e) => set({ ...r, remittance_reference: e.target.value })} /></label>
          <label><span className="field-label">Creditor name</span><input type="text" value={r.creditor_name ?? ''} onChange={(e) => set({ ...r, creditor_name: e.target.value })} /></label>
        </div>
      </div>
    </Card>
  );

  return (
    <AppShell>
      <PageHeader
        eyebrow="Reconciliation intelligence"
        title="Matching"
        description="Deterministic matching intelligence. A confirmed match is a reconciliation decision only — it never executes or settles a payment."
      />

      {error ? <ErrorState message={error} /> : null}

      <div className="grid-2">
        {recordForm('Source record', a, setA)}
        {recordForm('Candidate record', b, setB)}
      </div>

      <Card>
        <div className="card-body row">
          <Button onClick={() => run('evaluate')} disabled={busy}>Evaluate pair</Button>
          <Button variant="ghost" onClick={() => run('candidates')} disabled={busy}>Search candidates</Button>
          <Link href="/reconciliation" className="btn btn-ghost">Reconciliation runs</Link>
        </div>
      </Card>

      {decision ? (
        <Card>
          <CardHead
            title="Decision"
            sub="match_score is a deterministic score, not a probability"
            actions={<span className={badgeClass(decision.classification)}>{labelize(decision.classification)}</span>}
          />
          <div className="card-body">
            <ul className="status-list">
              <li><span className="label">Match score (deterministic)</span><span className="mono">{decision.match_score}</span></li>
              <li><span className="label">Policy / engine</span><span className="mono">{decision.policy_version} / {decision.engine_version}</span></li>
            </ul>
            {decision.critical_conflicts.length > 0 ? (
              <Notice tone="danger">
                Critical conflicts: {decision.critical_conflicts.map((c) => c.field).join(', ')}
              </Notice>
            ) : null}
            <TableWrap>
              <table className="data">
                <thead><tr><th>Field</th><th>Similarity</th><th>Weight</th><th>Status</th><th>Explanation</th></tr></thead>
                <tbody>
                  {decision.field_results.map((f) => (
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
          </div>
        </Card>
      ) : null}

      {candidates.length > 0 ? (
        <Card>
          <CardHead title="Ranked candidates" sub="Ordered by deterministic score" />
          <TableWrap>
            <table className="data">
              <thead><tr><th>Candidate</th><th>Score</th><th>Classification</th><th>Conflicts</th></tr></thead>
              <tbody>
                {candidates.map((c) => (
                  <tr key={c.candidate_id}>
                    <td className="mono">{c.candidate_id}</td>
                    <td>{c.match_score}</td>
                    <td><span className={badgeClass(c.classification)}>{labelize(c.classification)}</span></td>
                    <td>{c.critical_conflicts.length}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        </Card>
      ) : null}

      {!decision && candidates.length === 0 ? (
        <Card><EmptyState title="No evaluation yet" message="Enter two records and evaluate, or search candidates for the source record." /></Card>
      ) : null}
    </AppShell>
  );
}
