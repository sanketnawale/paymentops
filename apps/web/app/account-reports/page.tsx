'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Play } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Button, Card, CardHead, EmptyState, ErrorState, PageHeader, Skeleton, TableWrap } from '@/components/ui';
import { listAccountReports, runAccountReconciliation, type AccountReport } from '@/lib/api';
import { badgeClass, formatDateTime, labelize } from '@/lib/status';

export default function AccountReportsPage() {
  const [reports, setReports] = useState<AccountReport[]>([]);
  const [reportType, setReportType] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [missing, setMissing] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setReports(await listAccountReports({ report_type: reportType }));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load account reports');
    } finally {
      setLoading(false);
    }
  }, [reportType]);

  useEffect(() => {
    load();
  }, [load]);

  const runRecon = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await runAccountReconciliation(48);
      setMissing(res.count);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reconciliation failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="Account reporting"
        title="Account Reports"
        description="camt.053 statements and camt.054 notifications — analyzed as account-reporting evidence only."
        actions={<Button variant="ghost" onClick={runRecon} disabled={busy}><Play size={14} /> {busy ? 'Running…' : 'Run missing-event reconciliation'}</Button>}
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}
      {missing !== null ? <p className="muted small">Missing account events flagged: {missing}</p> : null}

      <Card noPad>
        <div className="filters" style={{ padding: '1rem', borderBottom: '1px solid var(--cn-border)' }}>
          <label>
            <span className="field-label">Report type</span>
            <select value={reportType} onChange={(e) => setReportType(e.target.value)} aria-label="Filter by report type">
              <option value="">All</option>
              <option value="STATEMENT">STATEMENT (camt.053)</option>
              <option value="NOTIFICATION">NOTIFICATION (camt.054)</option>
            </select>
          </label>
        </div>
        <CardHead title="Reports" sub="Account statements and notifications" />
        {loading ? (
          <div style={{ padding: '1.25rem' }}><Skeleton lines={4} /></div>
        ) : reports.length === 0 ? (
          <EmptyState title="No account reports yet" message="Ingest a camt.053 or camt.054 message to begin." />
        ) : (
          <TableWrap>
            <table className="data">
              <thead>
                <tr><th>Report</th><th>Type</th><th>Version</th><th>Account</th><th>Period</th><th>Entries</th><th>Created</th></tr>
              </thead>
              <tbody>
                {reports.map((r) => (
                  <tr key={r.id}>
                    <td><Link href={`/account-reports/${r.id}`} className="mono">{r.statement_id ?? r.notification_id ?? r.id.slice(0, 12)}</Link></td>
                    <td><span className={badgeClass(r.report_type)}>{labelize(r.report_type)}</span></td>
                    <td className="mono">{r.message_version}</td>
                    <td className="mono">{r.account_iban ?? '—'}</td>
                    <td className="muted small">{r.period_start ?? '—'}{r.period_end ? ` → ${r.period_end}` : ''}</td>
                    <td>{r.entry_count}</td>
                    <td className="muted small">{formatDateTime(r.created_at)}</td>
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
