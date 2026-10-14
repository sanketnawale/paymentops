'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import AppShell from '@/components/AppShell';
import { Button, Card, CardHead, EmptyState, ErrorState, Notice, PageHeader, Skeleton, TableWrap } from '@/components/ui';
import { analyzeIso, listIsoMessages, type IsoAnalysisResult, type IsoMessage } from '@/lib/api';
import { badgeClass, formatDateTime, labelize } from '@/lib/status';

const SUPPORTED = [
  'pacs.008.001.08',
  'pain.001.001.13',
  'pacs.002.001.16',
  'pacs.009.001.13',
  'camt.053.001.14',
  'camt.054.001.14',
];

export default function IsoMessagesPage() {
  const [messages, setMessages] = useState<IsoMessage[]>([]);
  const [family, setFamily] = useState('');
  const [version, setVersion] = useState('');
  const [status, setStatus] = useState('');
  const [xml, setXml] = useState('');
  const [result, setResult] = useState<IsoAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setMessages(await listIsoMessages({ family, version, status }));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load ISO messages');
    } finally {
      setLoading(false);
    }
  }, [family, version, status]);

  useEffect(() => {
    load();
  }, [load]);

  const onAnalyze = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await analyzeIso(xml);
      setResult(r);
      setXml('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analyze failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="ISO 20022 lifecycle"
        title="ISO Messages"
        description="Registry-based ISO 20022 analysis. Parsing a message never executes or settles a payment."
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}

      <Card>
        <CardHead title="Analyze a message" sub={`Supported: ${SUPPORTED.join(', ')}`} />
        <div className="card-body">
          <textarea
            className="mono"
            rows={6}
            value={xml}
            onChange={(e) => setXml(e.target.value)}
            placeholder="Paste an ISO 20022 XML payload (pacs.008, pain.001, pacs.002, pacs.009, camt.053, camt.054)…"
            aria-label="ISO XML payload"
          />
          <Button onClick={onAnalyze} disabled={busy || !xml.trim()} style={{ marginTop: '0.75rem' }}>
            {busy ? 'Analyzing…' : 'Analyze'}
          </Button>
        </div>
      </Card>

      {result ? (
        <Card>
          <CardHead
            title="Result"
            sub={`${result.message_definition} (${result.message_version})`}
            actions={<span className={badgeClass(result.schema_validation ? 'VALID' : 'INVALID')}>{result.schema_validation ? 'Schema valid' : 'Schema invalid'}</span>}
          />
          <div className="card-body">
            <ul className="status-list">
              <li><span className="label">Message family</span><span>{result.message_family ?? '—'}</span></li>
              <li><span className="label">Schema version</span><span className="mono">{result.schema_version ?? '—'}</span></li>
              <li><span className="label">Normalized status</span><span>{labelize(result.normalized_status)} {result.raw_status ? `(raw ${result.raw_status})` : ''}</span></li>
              <li><span className="label">Correlation</span><span className={badgeClass(result.correlation_status)}>{labelize(result.correlation_status)}</span></li>
              <li><span className="label">Account entries</span><span>{result.account_entry_count ?? 0}</span></li>
              <li>
                <span className="label">Lifecycle</span>
                <span>{result.lifecycle_id ? <Link href={`/lifecycles/${result.lifecycle_id}`} className="mono">{result.lifecycle_id.slice(0, 20)}</Link> : '—'}</span>
              </li>
            </ul>
            {(result.correlation_evidence ?? []).length > 0 ? (
              <p className="muted small">Evidence: {(result.correlation_evidence ?? []).join(', ')}</p>
            ) : null}
            {(result.schema_issues ?? []).length > 0 ? (
              <Notice tone="danger">{(result.schema_issues ?? []).length} schema issue(s) — see analysis output.</Notice>
            ) : null}
          </div>
        </Card>
      ) : null}

      <Card noPad>
        <div className="filters" style={{ padding: '1rem', borderBottom: '1px solid var(--cn-border)' }}>
          <label><span className="field-label">Family</span><input type="text" value={family} onChange={(e) => setFamily(e.target.value)} placeholder="pacs / pain / camt" /></label>
          <label><span className="field-label">Version</span><input type="text" value={version} onChange={(e) => setVersion(e.target.value)} placeholder="camt.053.001.14" /></label>
          <label><span className="field-label">Status</span><input type="text" value={status} onChange={(e) => setStatus(e.target.value)} placeholder="ANALYZED" /></label>
        </div>
        <CardHead title="Recent messages" sub="Ingested ISO 20022 messages" />
        {loading ? (
          <div style={{ padding: '1.25rem' }}><Skeleton lines={4} /></div>
        ) : messages.length === 0 ? (
          <EmptyState title="No ISO messages yet" />
        ) : (
          <TableWrap>
            <table className="data">
              <thead>
                <tr><th>Message</th><th>Definition</th><th>Version</th><th>Schema</th><th>Status</th><th>Created</th></tr>
              </thead>
              <tbody>
                {messages.map((m) => (
                  <tr key={m.id}>
                    <td className="mono">{m.message_id ?? m.id.slice(0, 12)}</td>
                    <td>{m.message_definition}</td>
                    <td className="mono">{m.message_version}</td>
                    <td><span className={badgeClass(m.schema_validation ? 'VALID' : 'INVALID')}>{m.schema_validation ? 'Valid' : 'Invalid'}</span></td>
                    <td>{labelize(m.normalized_status ?? m.status)}</td>
                    <td className="muted small">{formatDateTime(m.created_at)}</td>
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
