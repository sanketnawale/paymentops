'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Database,
  FileSearch,
  Scale,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Button, Card, CardHead, EmptyState, ErrorState, Metric, PageHeader, Skeleton, TableWrap } from '@/components/ui';
import {
  getDashboard,
  listBatches,
  listCases,
  listReconciliations,
  type BatchJobSummary,
  type CaseSummary,
  type DashboardMetrics,
  type ReconciliationRun,
} from '@/lib/api';
import { badgeClass, labelize } from '@/lib/status';

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [batches, setBatches] = useState<BatchJobSummary[]>([]);
  const [runs, setRuns] = useState<ReconciliationRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [m, c, b, r] = await Promise.all([
        getDashboard(),
        listCases(),
        listBatches(),
        listReconciliations().catch(() => []),
      ]);
      setMetrics(m);
      setCases(c);
      setBatches(b);
      setRuns(r);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load dashboard');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const matchTotals = runs.reduce(
    (acc, r) => {
      acc.matched += r.matched;
      acc.possible += r.possible_match;
      acc.review += r.review_required;
      acc.unmatched += r.unmatched;
      acc.duplicate += r.duplicate_candidate;
      return acc;
    },
    { matched: 0, possible: 0, review: 0, unmatched: 0, duplicate: 0 },
  );

  const readinessTotal =
    (metrics?.ready ?? 0) + (metrics?.repairable ?? 0) + (metrics?.review_required ?? 0) + (metrics?.unresolved ?? 0);
  const pct = (n: number) => (readinessTotal ? Math.round((n / readinessTotal) * 100) : 0);

  const topFindings = Object.entries(metrics?.top_findings ?? {}).sort((a, b) => b[1] - a[1]).slice(0, 6);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Operations overview"
        title="Payment-data readiness"
        description="A control surface for what entered the system, what is explainable, and where an operator is needed."
        actions={
          <>
            <Button variant="ghost" onClick={load} disabled={loading}>Refresh</Button>
            <Link href="/analyze" className="btn">
              <FileSearch size={14} /> Analyze payment
            </Link>
          </>
        }
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}

      {loading && !metrics ? (
        <Card><Skeleton lines={4} /></Card>
      ) : metrics ? (
        <>
          <div className="metric-grid">
            <Metric label="Payments analyzed" value={metrics.analyzed.toLocaleString()} detail="Total analyzed records" icon={<FileSearch size={17} />} />
            <Metric label="Ready" value={metrics.ready.toLocaleString()} detail={`${pct(metrics.ready)}% of analyzed`} tone="ok" icon={<CheckCircle2 size={17} />} />
            <Metric label="Repairable" value={metrics.repairable.toLocaleString()} detail="Candidate available" tone="warn" icon={<Zap size={17} />} />
            <Metric label="Review required" value={metrics.review_required.toLocaleString()} detail="Operator needed" tone="warn" icon={<ClipboardCheck size={17} />} />
            <Metric label="Unresolved" value={metrics.unresolved.toLocaleString()} detail="No candidate found" tone="danger" icon={<AlertTriangle size={17} />} />
            <Metric label="Matched" value={matchTotals.matched.toLocaleString()} detail="Matching engine" tone="ok" icon={<Scale size={17} />} />
            <Metric label="Possible matches" value={matchTotals.possible.toLocaleString()} detail="Review suggested" tone="warn" icon={<Scale size={17} />} />
            <Metric label="Account reconciled" value={(metrics.account_reconciled ?? 0).toLocaleString()} detail={`${metrics.reconciliation_rate ?? 0}% of account entries`} tone="ok" icon={<ShieldCheck size={17} />} />
            <Metric label="Account exceptions" value={((metrics.account_mismatches ?? 0) + (metrics.missing_account_event ?? 0) + (metrics.duplicate_entries ?? 0) + (metrics.unmatched_entries ?? 0)).toLocaleString()} detail="Mismatch / missing / duplicate / unmatched" tone="danger" icon={<AlertTriangle size={17} />} />
            <Metric label="Open cases" value={metrics.open_cases.toLocaleString()} detail="Requires operator attention" icon={<ClipboardCheck size={17} />} />
            <Metric label="Running batches" value={metrics.running_batches.toLocaleString()} detail={`${batches.length} total`} icon={<Database size={17} />} />
          </div>

          <div className="grid-sidebar" style={{ marginTop: '1.25rem' }}>
            <Card>
              <CardHead title="Readiness distribution" sub="Record outcomes across analyzed payments" />
              <div className="card-body">
                {readinessTotal === 0 ? (
                  <EmptyState title="No analyzed records yet" message="Analyze a payment or submit a batch to populate readiness." />
                ) : (
                  <>
                    <div style={{ display: 'flex', height: '0.75rem', borderRadius: 999, overflow: 'hidden', marginBottom: '1rem' }}>
                      <span style={{ width: `${pct(metrics.ready)}%`, background: 'var(--cn-ok)' }} title={`Ready ${metrics.ready}`} />
                      <span style={{ width: `${pct(metrics.repairable)}%`, background: '#b17a31' }} title={`Repairable ${metrics.repairable}`} />
                      <span style={{ width: `${pct(metrics.review_required)}%`, background: 'var(--cn-primary)' }} title={`Review ${metrics.review_required}`} />
                      <span style={{ width: `${pct(metrics.unresolved)}%`, background: 'var(--cn-danger)' }} title={`Unresolved ${metrics.unresolved}`} />
                    </div>
                    <ul className="status-list">
                      {[
                        ['Ready', metrics.ready, 'badge-ok'],
                        ['Repairable', metrics.repairable, 'badge-warn'],
                        ['Review required', metrics.review_required, 'badge-warn'],
                        ['Unresolved', metrics.unresolved, 'badge-danger'],
                      ].map(([label, value, cls]) => (
                        <li key={String(label)}>
                          <span className="row" style={{ gap: '0.5rem' }}>
                            <span className={`badge ${cls} badge-plain`} aria-hidden="true" />
                            {label}
                          </span>
                          <span className="mono">{Number(value).toLocaleString()} ({pct(Number(value))}%)</span>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            </Card>

            <Card>
              <CardHead title="Top findings" sub="Most frequent rule findings" />
              <div className="card-body">
                {topFindings.length === 0 ? (
                  <EmptyState title="No findings recorded" />
                ) : (
                  <ul className="status-list">
                    {topFindings.map(([rule, count]) => (
                      <li key={rule}>
                        <span className="mono">{rule}</span>
                        <span>{count.toLocaleString()}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Card>
          </div>

          <Card noPad>
            <CardHead
              title="Recent payment cases"
              sub="Latest analyzed records"
              actions={<Link href="/cases" className="small">View all</Link>}
            />
            <TableWrap>
              <table className="data">
                <thead>
                  <tr>
                    <th>Case</th>
                    <th>Type</th>
                    <th>Readiness</th>
                    <th>Repair</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.slice(0, 6).map((c) => (
                    <tr key={c.case_id}>
                      <td><Link href={`/cases/${c.case_id}`} className="mono">{c.case_id}</Link></td>
                      <td>{c.message_type ?? '—'}</td>
                      <td><span className={badgeClass(c.address_readiness)}>{labelize(c.address_readiness)}</span></td>
                      <td>{labelize(c.repair_status)}</td>
                      <td><span className={badgeClass(c.status)}>{labelize(c.status)}</span></td>
                    </tr>
                  ))}
                  {cases.length === 0 && (
                    <tr><td colSpan={5} className="table-empty">No cases yet.</td></tr>
                  )}
                </tbody>
              </table>
            </TableWrap>
          </Card>
        </>
      ) : null}

      <p className="muted small">
        PaymentOps analyzes and reconciles payment data. It does not execute, authorize, settle, debit or credit payments.
      </p>
    </AppShell>
  );
}
