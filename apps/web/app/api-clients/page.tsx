'use client';

import { useCallback, useEffect, useState } from 'react';
import { KeyRound, Plus } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Button, Card, CardHead, EmptyState, ErrorState, Modal, Notice, PageHeader, Skeleton, TableWrap } from '@/components/ui';
import { createApiClient, listApiClients, type ApiClientSummary } from '@/lib/api';
import { badgeClass, formatDateTime, labelize } from '@/lib/status';

export default function ApiClientsPage() {
  const [clients, setClients] = useState<ApiClientSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(false);
  const [orgId, setOrgId] = useState('');
  const [created, setCreated] = useState<{ client_id: string; secret: string } | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setClients(await listApiClients());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load API clients');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const create = async () => {
    setBusy(true);
    setCreateError(null);
    try {
      const res = await createApiClient(orgId.trim());
      setCreated({ client_id: res.client_id, secret: res.secret });
      await load();
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : 'Unable to create client');
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="Access control"
        title="API clients"
        description="Machine identities that submit payment data for analysis. Secrets are shown once and never stored in the browser."
        actions={<Button onClick={() => { setModal(true); setCreated(null); setCreateError(null); }}><Plus size={14} /> Create API client</Button>}
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}

      <Card noPad>
        <CardHead title="Clients" sub="Scoped to your organization" />
        {loading ? (
          <div style={{ padding: '1.25rem' }}><Skeleton lines={4} /></div>
        ) : clients.length === 0 ? (
          <EmptyState title="No API clients" message="Create a client to submit data for analysis." />
        ) : (
          <TableWrap>
            <table className="data">
              <thead>
                <tr><th>Client ID</th><th>Allowed profiles</th><th>Status</th><th>Last used</th><th>Created</th></tr>
              </thead>
              <tbody>
                {clients.map((c) => (
                  <tr key={c.client_id}>
                    <td className="row" style={{ gap: '0.4rem' }}><KeyRound size={13} aria-hidden="true" /><span className="mono">{c.client_id}</span></td>
                    <td className="muted small">{c.allowed_profiles.length ? c.allowed_profiles.join(', ') : 'All published profiles'}</td>
                    <td><span className={badgeClass(c.status)}>{labelize(c.status)}</span></td>
                    <td className="muted small">{formatDateTime(c.last_used_at)}</td>
                    <td className="muted small">{formatDateTime(c.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )}
      </Card>

      {modal ? (
        <Modal title="Create API client" onClose={() => setModal(false)}>
          {created ? (
            <>
              <Notice tone="warn">Copy the secret now. It is shown once and cannot be retrieved later.</Notice>
              <ul className="status-list">
                <li><span className="label">Client ID</span><span className="mono">{created.client_id}</span></li>
                <li><span className="label">Secret</span><span className="mono" style={{ wordBreak: 'break-all' }}>{created.secret}</span></li>
              </ul>
              <Button onClick={() => setModal(false)} style={{ marginTop: '0.75rem' }}>Done</Button>
            </>
          ) : (
            <>
              <label><span className="field-label">Organization ID</span><input type="text" value={orgId} onChange={(e) => setOrgId(e.target.value)} placeholder="organization UUID" /></label>
              {createError ? <p className="small" style={{ color: 'var(--cn-danger)' }} role="alert">{createError}</p> : null}
              <Button onClick={create} disabled={busy || !orgId.trim()} style={{ marginTop: '0.75rem' }}>{busy ? 'Creating…' : 'Create client'}</Button>
            </>
          )}
        </Modal>
      ) : null}
    </AppShell>
  );
}
