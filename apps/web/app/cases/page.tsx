'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Search } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Button, Card, ErrorState, PageHeader, Skeleton, TableWrap } from '@/components/ui';
import { listCases, type CaseSummary } from '@/lib/api';
import { badgeClass, formatDateTime, labelize } from '@/lib/status';

const STATUS_FILTERS = ['ALL', 'NEW', 'ANALYZED', 'REPAIR_PROPOSED', 'REVIEW_REQUIRED', 'APPROVED', 'REJECTED', 'CLOSED'];

export default function CasesPage() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [status, setStatus] = useState('ALL');
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setCases(await listCases());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load cases');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(
    () =>
      cases.filter(
        (c) =>
          (status === 'ALL' || c.status === status) &&
          `${c.case_id} ${c.message_type ?? ''} ${c.mapping_version ?? ''}`.toLowerCase().includes(search.toLowerCase()),
      ),
    [cases, status, search],
  );

  return (
    <AppShell>
      <PageHeader
        eyebrow="Human review"
        title="Cases"
        description="Controlled operator work with an explicit reason, evidence, and accountable outcome."
        actions={<Button variant="ghost" onClick={load} disabled={loading}>Refresh</Button>}
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}

      <Card noPad>
        <div className="filters" style={{ padding: '1rem', borderBottom: '1px solid var(--cn-border)' }}>
          <label style={{ flex: 1, minWidth: '16rem' }}>
            <span className="field-label">Search</span>
            <span className="row" style={{ position: 'relative' }}>
              <Search size={14} style={{ position: 'absolute', left: 10, color: 'var(--cn-text-muted)' }} aria-hidden="true" />
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search case, type, mapping version"
                style={{ paddingLeft: '2rem' }}
                aria-label="Search cases"
              />
            </span>
          </label>
          <label>
            <span className="field-label">Status</span>
            <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
              {STATUS_FILTERS.map((s) => (
                <option key={s} value={s}>{s === 'ALL' ? 'All statuses' : labelize(s)}</option>
              ))}
            </select>
          </label>
          <span className="muted small">{filtered.length} shown</span>
        </div>

        {loading ? (
          <div style={{ padding: '1.25rem' }}><Skeleton lines={5} /></div>
        ) : (
          <TableWrap>
            <table className="data">
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Type</th>
                  <th>Profile version</th>
                  <th>Status</th>
                  <th>Readiness</th>
                  <th>Repair</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => (
                  <tr key={c.case_id}>
                    <td><Link href={`/cases/${c.case_id}`} className="mono">{c.case_id}</Link></td>
                    <td>{c.message_type ?? '—'}</td>
                    <td className="mono">{c.integration_profile_version ?? '—'}</td>
                    <td><span className={badgeClass(c.status)}>{labelize(c.status)}</span></td>
                    <td><span className={badgeClass(c.address_readiness)}>{labelize(c.address_readiness)}</span></td>
                    <td>{labelize(c.repair_status)}</td>
                    <td className="muted small">{formatDateTime(c.created_at)}</td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr><td colSpan={7} className="table-empty">No cases match the current filters.</td></tr>
                )}
              </tbody>
            </table>
          </TableWrap>
        )}
      </Card>
    </AppShell>
  );
}
