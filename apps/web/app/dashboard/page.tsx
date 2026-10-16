'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Activity, AlertTriangle, Brain, CheckCircle2, ClipboardCheck, FlaskConical, ShieldCheck, Upload } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Button, Card, CardHead, EmptyState, ErrorState, Metric, Notice, PageHeader, Skeleton, TableWrap } from '@/components/ui';
import { getDashboard, listInvestigations, type DashboardMetrics, type InvestigationSummary } from '@/lib/api';
import { badgeClass, formatDateTime, labelize } from '@/lib/status';

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [investigations, setInvestigations] = useState<InvestigationSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [m, inv] = await Promise.all([getDashboard(), listInvestigations()]);
      setMetrics(m);
      setInvestigations(inv);
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

  const inv = metrics?.investigations;
  const business =
    (metrics?.analyzed ?? 0) + (metrics?.ready ?? 0) + (metrics?.repairable ?? 0) +
    (metrics?.review_required ?? 0) + (metrics?.unresolved ?? 0) + (metrics?.open_cases ?? 0);

  return (
    <AppShell>
      <PageHeader
        eyebrow="AI investigation (hackathon)"
        title="Payment investigations overview"
        description="Evidence-backed investigation of synthetic ISO 20022 cases: upload or sample → Evolus/AMD agent → PaymentOps engine → sandbox repair test."
        actions={
          <>
            <Button variant="ghost" onClick={load} disabled={loading}>Refresh</Button>
            <Link href="/investigations" className="btn btn-ghost"><Brain size={14} /> Try a sample</Link>
            <Link href="/investigations" className="btn"><Upload size={14} /> Upload synthetic payment</Link>
          </>
        }
      />

      <Notice tone="accent">
        <ShieldCheck size={15} aria-hidden="true" />
        <span>
          Synthetic data only. <strong>Workflow completion</strong> (the agent finished),{' '}
          <strong>sandbox validation</strong> (a proposed change passed deterministic re-validation), and{' '}
          <strong>human approval</strong> are three different things. Sandbox copies are <strong>not</strong>{' '}
          executed payments, and nothing is authorized, executed, or settled.
        </span>
      </Notice>

      {error ? <ErrorState message={error} onRetry={load} /> : null}

      {loading && !metrics ? (
        <Card><Skeleton lines={4} /></Card>
      ) : metrics ? (
        <>
          <div className="metric-grid">
            <Metric label="Investigations" value={(inv?.total ?? 0).toLocaleString()} detail={`${inv?.uploads ?? 0} uploaded · ${inv?.samples ?? 0} samples`} icon={<Brain size={17} />} />
            <Metric label="Running" value={(inv?.running ?? 0).toLocaleString()} detail="Workflow in progress" tone="warn" icon={<Activity size={17} />} />
            <Metric label="Completed (workflow)" value={(inv?.completed ?? 0).toLocaleString()} detail="Agent run finished — not a validation result" tone="ok" icon={<CheckCircle2 size={17} />} />
            <Metric label="Failed" value={(inv?.failed ?? 0).toLocaleString()} detail="Integration/run failure" tone="danger" icon={<AlertTriangle size={17} />} />
            <Metric label="Sandbox tests" value={(inv?.sandbox_tests ?? 0).toLocaleString()} detail="Proposed repairs tested on a copy" icon={<FlaskConical size={17} />} />
            <Metric label="Sandbox validated" value={(inv?.sandbox_validated ?? 0).toLocaleString()} detail="Deterministic re-validation passed" tone="ok" icon={<CheckCircle2 size={17} />} />
            <Metric label="Review required" value={(inv?.review_required ?? 0).toLocaleString()} detail="Unresolved findings / rejected changes" tone="warn" icon={<ClipboardCheck size={17} />} />
          </div>

          <Card noPad>
            <CardHead
              title="Recent investigations"
              sub="Latest synthetic cases (uploaded and sample)"
              actions={<Link href="/investigations" className="small">Open investigations</Link>}
            />
            <TableWrap>
              <table className="data">
                <thead>
                  <tr>
                    <th>Investigation</th>
                    <th>Input</th>
                    <th>Workflow</th>
                    <th>Rule findings</th>
                    <th>Repair</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {investigations.slice(0, 6).map((i) => (
                    <tr key={i.investigation_id}>
                      <td><Link href={`/investigations/${i.investigation_id}`} className="mono">{i.investigation_id}</Link></td>
                      <td>{labelize(i.demo_case_key)}</td>
                      <td><span className={badgeClass(i.status)}>{labelize(i.status)}</span></td>
                      <td>{i.rule_count}</td>
                      <td>{i.error ? <span className="badge badge-danger badge-plain">failed</span> : labelize(i.validation_status)}</td>
                      <td className="muted small">{formatDateTime(i.created_at)}</td>
                    </tr>
                  ))}
                  {investigations.length === 0 && (
                    <tr><td colSpan={6} className="table-empty">No investigations yet — upload a synthetic payment or try a sample.</td></tr>
                  )}
                </tbody>
              </table>
            </TableWrap>
          </Card>

          <Card>
            <CardHead
              title="Business modules (existing — not part of the hackathon demo)"
              sub="These reflect the copied PaymentOps modules. They are not populated by, or integrated with, the Evolus/AMD investigator."
            />
            <div className="card-body">
              {business === 0 ? (
                <EmptyState title="No business-module records in this deployment" message="Investigation data is shown above and is kept separate from these business statistics." />
              ) : (
                <div className="metric-grid">
                  <Metric label="Analyzed (business)" value={(metrics.analyzed ?? 0).toLocaleString()} />
                  <Metric label="Ready" value={(metrics.ready ?? 0).toLocaleString()} tone="ok" />
                  <Metric label="Open cases" value={(metrics.open_cases ?? 0).toLocaleString()} />
                  <Metric label="Running batches" value={(metrics.running_batches ?? 0).toLocaleString()} />
                  <Metric label="Account reconciled" value={(metrics.account_reconciled ?? 0).toLocaleString()} tone="ok" />
                </div>
              )}
            </div>
          </Card>
        </>
      ) : null}

      <p className="muted small">
        PaymentOps analyzes payment data only. It does not execute, authorize, settle, debit or credit payments.
      </p>
    </AppShell>
  );
}
