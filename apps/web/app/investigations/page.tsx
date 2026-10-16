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
  uploadInvestigation,
  type DemoCase,
  type InvestigationSummary,
} from '@/lib/api';
import { badgeClass, formatDateTime, labelize } from '@/lib/status';

const MAX_XML_BYTES = 262_144;

function readFile(
  file: File | undefined,
  onText: (text: string, name: string) => void,
  onError: (message: string) => void,
) {
  if (!file) return;
  if (file.size > MAX_XML_BYTES) {
    onError('The selected file exceeds the 256 KiB limit.');
    return;
  }
  const reader = new FileReader();
  reader.onload = () => onText(String(reader.result ?? ''), file.name);
  reader.onerror = () => onError('The file could not be read.');
  reader.readAsText(file);
}

export default function InvestigationsPage() {
  const router = useRouter();
  const [demoCases, setDemoCases] = useState<DemoCase[]>([]);
  const [selected, setSelected] = useState('');
  const [investigations, setInvestigations] = useState<InvestigationSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  // Upload state (synthetic-only journey).
  const [xmlText, setXmlText] = useState('');
  const [xmlName, setXmlName] = useState('');
  const [evidenceText, setEvidenceText] = useState('');
  const [evidenceName, setEvidenceName] = useState('');
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

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

  const upload = async () => {
    setUploadError(null);
    if (!xmlText.trim()) {
      setUploadError('Select an ISO 20022 pacs.008 XML file.');
      return;
    }
    let evidence: Record<string, unknown> | null = null;
    if (evidenceText.trim()) {
      try {
        evidence = JSON.parse(evidenceText) as Record<string, unknown>;
      } catch {
        setUploadError('The supporting-evidence file is not valid JSON.');
        return;
      }
    }
    setUploadBusy(true);
    try {
      const investigation = await uploadInvestigation(xmlText, evidence, true);
      router.push(`/investigations/${investigation.investigation_id}`);
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : 'Upload failed');
      setUploadBusy(false);
    }
  };

  const current = demoCases.find((c) => c.key === selected);

  return (
    <AppShell>
      <PageHeader
        eyebrow="AI investigation"
        title="Payment investigations"
        description="Investigate a synthetic ISO 20022 case (sample or your own upload) using the PaymentOps Investigator."
      />

      <Notice tone="accent">
        <ShieldCheck size={15} aria-hidden="true" />
        <span>
          <strong>Synthetic data only.</strong> Upload a synthetic pacs.008.001.08 file. Deterministic
          validation is authoritative; the agent interprets. Nothing is authorized, executed, or
          settled, and uploaded files are never used as storage paths.
        </span>
      </Notice>

      {error ? <ErrorState message={error} onRetry={load} /> : null}

      <div className="grid-sidebar">
        <div className="stack">
          <Card>
            <CardHead title="Upload synthetic payment" sub="One pacs.008.001.08 XML + optional evidence JSON" />
            <div className="card-body">
              <label>
                <span className="field-label">ISO 20022 XML file (required)</span>
                <input
                  type="file"
                  accept=".xml,application/xml,text/xml"
                  aria-label="ISO 20022 XML file"
                  onChange={(e) =>
                    readFile(
                      e.target.files?.[0],
                      (text, name) => {
                        setXmlText(text);
                        setXmlName(name);
                      },
                      setUploadError,
                    )
                  }
                />
              </label>
              {xmlName ? <p className="muted small" style={{ marginTop: '0.25rem' }}>Selected: <span className="mono">{xmlName}</span></p> : null}

              <label style={{ display: 'block', marginTop: '0.5rem' }}>
                <span className="field-label">Supporting-evidence JSON (optional)</span>
                <input
                  type="file"
                  accept=".json,application/json"
                  aria-label="Supporting-evidence JSON file"
                  onChange={(e) =>
                    readFile(
                      e.target.files?.[0],
                      (text, name) => {
                        setEvidenceText(text);
                        setEvidenceName(name);
                      },
                      setUploadError,
                    )
                  }
                />
              </label>
              {evidenceName ? <p className="muted small" style={{ marginTop: '0.25rem' }}>Selected: <span className="mono">{evidenceName}</span></p> : null}
              <p className="muted small" style={{ marginTop: '0.5rem' }}>
                Without evidence the investigation still runs, but unsupported repairs are rejected.
                See the evidence schema in the sample bundle README.
              </p>

              {uploadError ? (
                <p className="small" style={{ color: 'var(--cn-danger)' }} role="alert">{uploadError}</p>
              ) : null}

              <Button onClick={upload} disabled={uploadBusy} style={{ marginTop: '0.75rem' }}>
                <Brain size={14} /> {uploadBusy ? 'Starting…' : 'Start investigation'}
              </Button>

              <p className="field-label" style={{ marginTop: '0.75rem' }}>Sample bundles (download)</p>
              <ul className="status-list">
                <li>
                  <span>
                    <strong>Complete evidence</strong> — debtor + creditor towns
                    <br />
                    <a href="/examples/uploads/complete/pacs008_missing_town.xml" download className="mono small">pacs008_missing_town.xml</a>
                    {' · '}
                    <a href="/examples/uploads/complete/evidence.json" download className="mono small">evidence.json</a>
                  </span>
                </li>
                <li>
                  <span>
                    <strong>Incomplete evidence</strong> — debtor town only (expert review)
                    <br />
                    <a href="/examples/uploads/incomplete/pacs008_missing_town.xml" download className="mono small">pacs008_missing_town.xml</a>
                    {' · '}
                    <a href="/examples/uploads/incomplete/evidence.json" download className="mono small">evidence.json</a>
                  </span>
                </li>
              </ul>
            </div>
          </Card>

          <Card>
            <CardHead title="Try a sample" sub="Bundled synthetic demo cases" />
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
        </div>

        <Card>
          <CardHead title="Recent investigations" sub="Tenant-scoped" />
          <div className="card-body">
            {loading ? (
              <Skeleton lines={4} />
            ) : investigations.length === 0 ? (
              <EmptyState
                title="No investigations yet"
                message="Upload a synthetic payment or try a sample on the left."
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
