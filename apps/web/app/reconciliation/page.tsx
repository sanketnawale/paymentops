'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Download, Play } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Button, Card, CardHead, EmptyState, ErrorState, Notice, PageHeader, Skeleton, TableWrap } from '@/components/ui';
import {
  createReconciliation,
  getReconciliationReport,
  listReconciliations,
  type MatchRecord,
  type ReconciliationRun,
} from '@/lib/api';
import { badgeClass, formatDateTime, labelize } from '@/lib/status';

const SAMPLE_SOURCE = `[
  {"record_id":"inv-1","record_type":"INVOICE","organization_id":"","amount":"12500","currency":"EUR","remittance_reference":"INV-92881","creditor_name":"ACME INDUSTRIA SPA"}
]`;
const SAMPLE_CANDIDATE = `[
  {"record_id":"pay-1","record_type":"PAYMENT","organization_id":"","amount":"12500","currency":"EUR","remittance_reference":"INV92881","creditor_name":"ACME INDUSTRIA S.P.A."}
]`;

export default function ReconciliationPage() {
  const [runs, setRuns] = useState<ReconciliationRun[]>([]);
  const [source, setSource] = useState(SAMPLE_SOURCE);
  const [candidate, setCandidate] = useState(SAMPLE_CANDIDATE);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRuns(await listReconciliations());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load reconciliation runs');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const source_records = JSON.parse(source) as MatchRecord[];
      const candidate_records = JSON.parse(candidate) as MatchRecord[];
      const res = await createReconciliation({ source_records, candidate_records });
      await load();
      if (res.run_id) window.location.href = `/matching/${res.run_id}`;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to start reconciliation');
    } finally {
      setBusy(false);
    }
  };

  const download = async (runId: string) => {
    try {
      const csv = await getReconciliationReport(runId);
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `reconciliation-${runId.slice(0, 12)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Download failed');
    }
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="Reconciliation"
        title="Reconciliation runs"
        description="Batch reconciliation of a source dataset against a candidate dataset. Results are non-transactional decisions only."
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}

      <Card>
        <CardHead title="Start reconciliation" sub="Provide source and candidate datasets as JSON arrays" />
        <div className="card-body">
          <Notice tone="accent">Records are matched deterministically. No payment is executed, authorized or settled.</Notice>
          <div className="grid-2">
            <label><span className="field-label">Source dataset (JSON)</span>
              <textarea className="mono" rows={8} value={source} onChange={(e) => setSource(e.target.value)} aria-label="Source dataset" />
            </label>
            <label><span className="field-label">Candidate dataset (JSON)</span>
              <textarea className="mono" rows={8} value={candidate} onChange={(e) => setCandidate(e.target.value)} aria-label="Candidate dataset" />
            </label>
          </div>
          <Button onClick={start} disabled={busy} style={{ marginTop: '0.75rem' }}>
            <Play size={14} /> {busy ? 'Starting…' : 'Start reconciliation'}
          </Button>
        </div>
      </Card>

      <Card noPad>
        <CardHead title="Runs" sub="Outcomes by classification" actions={<Button variant="ghost" size="sm" onClick={load}>Refresh</Button>} />
        {loading ? (
          <div style={{ padding: '1.25rem' }}><Skeleton lines={4} /></div>
        ) : runs.length === 0 ? (
          <EmptyState title="No reconciliation runs yet" />
        ) : (
          <TableWrap>
            <table className="data">
              <thead>
                <tr><th>Run</th><th>Status</th><th>Total</th><th>Matched</th><th>Possible</th><th>Review</th><th>Unmatched</th><th>Duplicate</th><th>Created</th><th /></tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.run_id}>
                    <td><Link href={`/matching/${r.run_id}`} className="mono">{r.run_id.slice(0, 12)}</Link></td>
                    <td><span className={badgeClass(r.status)}>{labelize(r.status)}</span></td>
                    <td>{r.total}</td>
                    <td>{r.matched}</td>
                    <td>{r.possible_match}</td>
                    <td>{r.review_required}</td>
                    <td>{r.unmatched}</td>
                    <td>{r.duplicate_candidate}</td>
                    <td className="muted small">{formatDateTime(r.created_at)}</td>
                    <td><Button variant="ghost" size="sm" onClick={() => download(r.run_id)} aria-label={`Download report for ${r.run_id}`}><Download size={13} /></Button></td>
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
