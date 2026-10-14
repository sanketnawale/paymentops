'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Brain, ShieldCheck } from 'lucide-react';
import AppShell from '@/components/AppShell';
import {
  Button,
  Card,
  CardHead,
  EmptyState,
  ErrorState,
  Notice,
  PageHeader,
  Skeleton,
} from '@/components/ui';
import {
  listDemoCases,
  listInvestigations,
  startInvestigation,
  type DemoCase,
  type InvestigationSummary,
} from '@/lib/api';
import { badgeClass, formatDateTime, labelize } from '@/lib/status';

export default function InvestigationsPage() {
  const router = useRouter();
  const [demoCases, setDemoCases] = useState<DemoCase[]>([]);
  const [selected, setSelected] = useState('');
  const [investigations, setInvestigations] = useState<InvestigationSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [cases, list] = await Promise.all([listDemoCases(), listInvestigations()]);
      setDemoCases(cases);
      setInvestigations(list);
      setSelected((current) => current || cases[0]?.key || '');
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load investigations');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const start = async () => {
    if (!selected) {
      setError('Select a synthetic demo case.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const investigation = await startInvestigation(selected);
      router.push(`/investigations/${investigation.investigation_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to start investigation');
      setBusy(false);
    }
  };

  const current = demoCases.find((c) => c.key === selected);

  return (
    <AppShell>
      <PageHeader
        eyebrow="AI investigation"
        title="Payment investigations"
        description="Start an evidence-backed investigation of a synthetic ISO 20022 case using the PaymentOps Investigator."
      />

      <Notice tone="accent">
        <ShieldCheck size={15} aria-hidden="true" />
        <span>
          <strong>Investigation only.</strong> Deterministic validation is authoritative. The agent
          interprets the engine&apos;s findings; it does not authorize, execute, or settle payments.
        </span>
      </Notice>

      {error ? <ErrorState message={error} onRetry={load} /> : null}

      <div className="grid-sidebar">
        <Card>
          <CardHead title="Start an investigation" sub="Synthetic demo cases only" />
          <div className="card-body">
            <label>
              <span className="field-label">Synthetic demo case</span>
              <select
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                aria-label="Synthetic demo case"
              >
                <option value="">— select —</option>
                {demoCases.map((c) => (
                  <option key={c.key} value={c.key}>
                    {c.name} ({c.message_version})
                  </option>
                ))}
              </select>
            </label>
            {current ? (
              <p className="muted small" style={{ marginTop: '0.5rem' }}>
                {current.description}
                <br />
                <span className="mono">origin: {current.origin}</span>
              </p>
            ) : null}
            <Button onClick={start} disabled={busy || loading} style={{ marginTop: '0.75rem' }}>
              <Brain size={14} /> {busy ? 'Starting…' : 'Investigate'}
            </Button>
          </div>
        </Card>

        <Card>
          <CardHead title="Recent investigations" sub="Tenant-scoped" />
          <div className="card-body">
            {loading ? (
              <Skeleton lines={4} />
            ) : investigations.length === 0 ? (
              <EmptyState
                title="No investigations yet"
                message="Start one from a synthetic demo case on the left."
              />
            ) : (
              <ul className="status-list">
                {investigations.map((inv) => (
                  <li key={inv.investigation_id}>
                    <span>
                      <Link href={`/investigations/${inv.investigation_id}`} className="mono">
                        {inv.investigation_id}
                      </Link>
                      <br />
                      <span className="muted small">
                        {labelize(inv.demo_case_key)} · {inv.message_version} ·{' '}
                        {inv.rule_count} finding{inv.rule_count === 1 ? '' : 's'} ·{' '}
                        {formatDateTime(inv.created_at)}
                      </span>
                    </span>
                    <span className={badgeClass(inv.status)}>{labelize(inv.status)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
