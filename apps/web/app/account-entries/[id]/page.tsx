'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, Database, ShieldCheck } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Card, CardHead, ErrorState, Notice, PageHeader, Skeleton } from '@/components/ui';
import { getAccountEntry, type AccountEntry } from '@/lib/api';
import { badgeClass, formatDateTime, formatMinor, labelize } from '@/lib/status';

export default function AccountEntryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [entry, setEntry] = useState<AccountEntry | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setEntry(await getAccountEntry(id));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load account entry');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const row = (k: string, v: string | number | null | undefined) => (
    <li><span className="label">{k}</span><span>{v ?? '—'}</span></li>
  );

  return (
    <AppShell>
      <PageHeader
        eyebrow="Account reporting"
        title={entry?.entry_reference ?? 'Account entry'}
        description={entry ? `Observed bank data · ${entry.credit_debit ?? ''}` : undefined}
        actions={<Link href="/account-reports" className="btn btn-ghost"><ArrowLeft size={14} /> All reports</Link>}
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}
      {loading && !entry ? <Card><Skeleton lines={5} /></Card> : null}

      {entry ? (
        <div className="grid-sidebar">
          <Card>
            <CardHead
              title="Observed bank data"
              sub="Values as reported in the camt message (unmodified evidence)"
              actions={<span className="row muted small" style={{ gap: '0.35rem' }}><Database size={13} aria-hidden="true" /> Bank message</span>}
            />
            <div className="card-body">
              <ul className="status-list">
                {row('Amount', formatMinor(entry.amount_minor, entry.currency))}
                {row('Credit / Debit', entry.credit_debit)}
                {row('Booking date', entry.booking_date)}
                {row('Value date', entry.value_date)}
                {row('Status', labelize(entry.status))}
                {row('Entry reference', entry.entry_reference)}
                {row('Account servicer reference', entry.account_servicer_reference)}
                {row('End-to-end ID', entry.end_to_end_id)}
                {row('Instruction ID', entry.instruction_id)}
                {row('Transaction ID', entry.transaction_id)}
                {row('UETR', entry.uetr)}
                {row('Bank transaction code', [entry.bank_tx_code, entry.bank_tx_family, entry.bank_tx_sub_family].filter(Boolean).join(' / '))}
                {row('Remittance', entry.remittance_reference)}
              </ul>
            </div>
          </Card>

          <Card>
            <CardHead
              title="PaymentOps classification"
              sub="Analytical reconciliation result — not bank data"
              actions={<span className={badgeClass(entry.reconciliation_status)}>{labelize(entry.reconciliation_status)}</span>}
            />
            <div className="card-body">
              <Notice tone="accent">
                <ShieldCheck size={15} aria-hidden="true" />
                <span>Analytical reconciliation only. PaymentOps never modifies a bank account or ledger.</span>
              </Notice>
              <ul className="status-list">
                {row('Classification', labelize(entry.reconciliation_status))}
                {row('Match score (deterministic)', entry.match_score ?? '—')}
                <li>
                  <span className="label">Related lifecycle</span>
                  <span>{entry.lifecycle_id ? <Link href={`/lifecycles/${entry.lifecycle_id}`} className="mono">{entry.lifecycle_id.slice(0, 20)}</Link> : '—'}</span>
                </li>
              </ul>
              {(entry.evidence ?? []).length > 0 ? (
                <p className="muted small">Evidence: {(entry.evidence ?? []).join(', ')}</p>
              ) : null}
              {(entry.conflicts ?? []).length > 0 ? (
                <p className="small" style={{ color: 'var(--cn-danger)' }}>Conflicts: {(entry.conflicts ?? []).join(', ')}</p>
              ) : null}
              <p className="muted small">Ingested {formatDateTime(entry.created_at)}</p>
            </div>
          </Card>
        </div>
      ) : null}
    </AppShell>
  );
}
