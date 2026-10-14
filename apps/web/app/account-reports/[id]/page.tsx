'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Card, CardHead, EmptyState, ErrorState, PageHeader, Skeleton, TableWrap } from '@/components/ui';
import { getAccountReport, type AccountReport } from '@/lib/api';
import { badgeClass, formatDateTime, formatMinor, labelize } from '@/lib/status';

export default function AccountReportDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [report, setReport] = useState<AccountReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setReport(await getAccountReport(id));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load account report');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const entries = (report?.entries ?? []).filter((e) => (filter ? e.reconciliation_status === filter : true));

  return (
    <AppShell>
      <PageHeader
        eyebrow="Account reporting"
        title={report?.statement_id ?? report?.notification_id ?? 'Account report'}
        description={report ? `${report.report_type} · ${report.message_version}` : undefined}
        actions={<Link href="/account-reports" className="btn btn-ghost"><ArrowLeft size={14} /> All reports</Link>}
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}
      {loading && !report ? <Card><Skeleton lines={4} /></Card> : null}

      {report ? (
        <>
          <div className="grid-sidebar">
            <Card>
              <CardHead title="Report summary" actions={<span className={badgeClass(report.report_type)}>{labelize(report.report_type)}</span>} />
              <div className="card-body">
                <ul className="status-list">
                  <li><span className="label">Message ID</span><span className="mono">{report.message_id ?? '—'}</span></li>
                  <li><span className="label">Version</span><span className="mono">{report.message_version}</span></li>
                  <li><span className="label">Account</span><span className="mono">{report.account_iban ?? '—'} {report.account_currency ?? ''}</span></li>
                  <li><span className="label">Period</span><span>{report.period_start ?? '—'} → {report.period_end ?? '—'}</span></li>
                  <li><span className="label">Entries</span><span>{report.entry_count}</span></li>
                  <li><span className="label">Created</span><span>{formatDateTime(report.created_at)}</span></li>
                </ul>
              </div>
            </Card>

            <div className="stack">
              {(report.balances ?? []).length > 0 ? (
                <Card>
                  <CardHead title="Balances" sub="Contextual reporting data (camt.053)" />
                  <div className="card-body">
                    <ul className="status-list">
                      {(report.balances ?? []).map((b, i) => (
                        <li key={i}><span className="label">{b.balance_type} · {b.credit_debit}</span><span>{formatMinor(b.amount_minor, b.currency)}</span></li>
                      ))}
                    </ul>
                  </div>
                </Card>
              ) : null}

              <Card>
                <CardHead title="Reconciliation summary" sub="Account-entry classifications" />
                <div className="card-body">
                  {Object.keys(report.reconciliation_summary ?? {}).length === 0 ? (
                    <EmptyState title="No entries" />
                  ) : (
                    <ul className="status-list">
                      {Object.entries(report.reconciliation_summary ?? {}).map(([k, v]) => (
                        <li key={k}><span className={badgeClass(k)}>{labelize(k)}</span><span>{v}</span></li>
                      ))}
                    </ul>
                  )}
                </div>
              </Card>
            </div>
          </div>

          <Card noPad>
            <CardHead
              title="Entries"
              sub="Account movements"
              actions={
                <select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter entries" style={{ width: 'auto' }}>
                  <option value="">All statuses</option>
                  {['RECONCILED', 'UNMATCHED_ACCOUNT_ENTRY', 'AMOUNT_MISMATCH', 'CURRENCY_MISMATCH', 'ACCOUNT_MISMATCH', 'DUPLICATE_ACCOUNT_ENTRY'].map((s) => (
                    <option key={s} value={s}>{labelize(s)}</option>
                  ))}
                </select>
              }
            />
            <TableWrap>
              <table className="data">
                <thead>
                  <tr><th>Entry</th><th>Amount</th><th>CD</th><th>Booking</th><th>End-to-end</th><th>Status</th><th>Reconciliation</th></tr>
                </thead>
                <tbody>
                  {entries.map((e) => (
                    <tr key={e.id}>
                      <td><Link href={`/account-entries/${e.id}`} className="mono">{e.entry_reference ?? e.id.slice(0, 12)}</Link></td>
                      <td>{formatMinor(e.amount_minor, e.currency)}</td>
                      <td>{e.credit_debit ?? '—'}</td>
                      <td className="muted small">{e.booking_date ?? '—'}</td>
                      <td className="mono">{e.end_to_end_id ?? '—'}</td>
                      <td>{labelize(e.status)}</td>
                      <td><span className={badgeClass(e.reconciliation_status)}>{labelize(e.reconciliation_status)}</span></td>
                    </tr>
                  ))}
                  {entries.length === 0 && <tr><td colSpan={7} className="table-empty">No entries match.</td></tr>}
                </tbody>
              </table>
            </TableWrap>
          </Card>
        </>
      ) : null}
    </AppShell>
  );
}
