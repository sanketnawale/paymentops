'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Button, Card, CardHead, EmptyState, ErrorState, PageHeader, Skeleton, TableWrap } from '@/components/ui';
import { listAuditEvents, type AuditEvent } from '@/lib/api';
import { badgeClass, formatDateTime, labelize } from '@/lib/status';

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setEvents(await listAuditEvents({ limit: 200 }));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load audit events');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(
    () =>
      events.filter((e) =>
        `${e.event} ${e.actor ?? ''} ${e.resource ?? ''} ${e.case_id ?? ''}`.toLowerCase().includes(search.toLowerCase()),
      ),
    [events, search],
  );

  return (
    <AppShell>
      <PageHeader
        eyebrow="Governance"
        title="Audit log"
        description="A read-only, append-oriented record of analysis, configuration and operator events."
        actions={<Button variant="ghost" onClick={load} disabled={loading}>Refresh</Button>}
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}

      <Card noPad>
        <div className="filters" style={{ padding: '1rem', borderBottom: '1px solid var(--cn-border)' }}>
          <label style={{ flex: 1, minWidth: '16rem' }}>
            <span className="field-label">Search</span>
            <span className="row" style={{ position: 'relative' }}>
              <Search size={14} style={{ position: 'absolute', left: 10, color: 'var(--cn-text-muted)' }} aria-hidden="true" />
              <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search event, actor, resource" style={{ paddingLeft: '2rem' }} aria-label="Search audit events" />
            </span>
          </label>
          <span className="muted small">{filtered.length} events</span>
        </div>
        <CardHead title="Events" sub="Non-sensitive metadata only" />
        {loading ? (
          <div style={{ padding: '1.25rem' }}><Skeleton lines={6} /></div>
        ) : filtered.length === 0 ? (
          <EmptyState title="No audit events" />
        ) : (
          <TableWrap>
            <table className="data">
              <thead>
                <tr><th>Time</th><th>Actor</th><th>Event</th><th>Resource</th><th>Profile version</th><th>Result</th></tr>
              </thead>
              <tbody>
                {filtered.map((e) => (
                  <tr key={e.id}>
                    <td className="muted small mono">{formatDateTime(e.timestamp)}</td>
                    <td>{e.actor ?? 'system'}</td>
                    <td><strong>{labelize(e.event)}</strong></td>
                    <td className="mono">{e.resource ?? e.case_id ?? '—'}</td>
                    <td className="mono">{e.profile_version ?? '—'}</td>
                    <td><span className={badgeClass(e.result)}>{labelize(e.result)}</span></td>
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
