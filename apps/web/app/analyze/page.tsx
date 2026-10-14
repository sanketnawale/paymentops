'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { FileSearch, ShieldCheck } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Button, Card, CardHead, EmptyState, ErrorState, Notice, PageHeader, Tabs } from '@/components/ui';
import { analyzeProfile, listProfiles, type Profile } from '@/lib/api';
import { badgeClass, formatDateTime, labelize } from '@/lib/status';

interface ProfileAnalysisResult {
  case_id?: string;
  integration_profile_version?: string;
  mapping_version?: string;
  ruleset_version?: string;
  engine_version?: string;
  address_provider?: string;
  address_provider_version?: string;
  address_provider_coverage?: string;
  original_validation_status?: string;
  address_readiness?: string;
  repair_status?: string;
  candidate_validation_status?: string;
  candidate_diff?: { path: string; before: string | null; after: string | null; source: string; status: string }[];
  rule_findings?: { rule_id: string; severity: string; message: string; target?: string }[];
  address_analyses?: { party?: string | null; readiness?: string | null; evidence_level?: string | null; country_code?: string | null; town_name?: string | null }[];
  input_hash?: string;
  output_hash?: string;
  warnings?: string[];
  processed_at?: string;
}

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'rules', label: 'Rules' },
  { id: 'address', label: 'Address intelligence' },
  { id: 'repair', label: 'Repair candidate' },
];

export default function AnalyzePage() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [profileId, setProfileId] = useState('');
  const [mode, setMode] = useState<'paste' | 'upload'>('paste');
  const [payload, setPayload] = useState('');
  const [result, setResult] = useState<ProfileAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState('overview');

  useEffect(() => {
    listProfiles()
      .then((p) => {
        setProfiles(p);
        if (p.length > 0 && p[0].id) setProfileId(p[0].id);
      })
      .catch(() => setProfiles([]));
  }, []);

  const onFile = (file: File | undefined) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setPayload(String(reader.result ?? ''));
    reader.readAsText(file);
  };

  const run = async () => {
    if (!profileId || !payload.trim()) {
      setError('Select a profile and provide a payload.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setResult((await analyzeProfile(profileId, payload)) as ProfileAnalysisResult);
      setTab('overview');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="Payment analysis"
        title="Analyze payment data"
        description="Profile a source payload against controlled mapping and validation rules."
        actions={<Link href="/cases" className="btn btn-ghost">View cases</Link>}
      />

      <Notice tone="accent">
        <ShieldCheck size={15} aria-hidden="true" />
        <span>PaymentOps analyzes payment data only. It does not authorize, execute or settle payments.</span>
      </Notice>

      {error ? <ErrorState message={error} /> : null}

      <div className="grid-sidebar">
        <Card>
          <CardHead title="Input source" sub="Choose a profile, then add one sample record" />
          <div className="card-body">
            <label>
              <span className="field-label">Integration profile</span>
              <select value={profileId} onChange={(e) => setProfileId(e.target.value)} aria-label="Integration profile">
                <option value="">— select —</option>
                {profiles.map((p) => (
                  <option key={p.id} value={p.id}>{p.name} ({p.input_format})</option>
                ))}
              </select>
            </label>

            <div className="tabs" role="tablist" style={{ marginTop: '1rem' }}>
              <button role="tab" className="tab" aria-selected={mode === 'paste'} onClick={() => setMode('paste')}>Paste</button>
              <button role="tab" className="tab" aria-selected={mode === 'upload'} onClick={() => setMode('upload')}>Upload</button>
            </div>

            {mode === 'upload' ? (
              <label>
                <span className="field-label">File</span>
                <input type="file" onChange={(e) => onFile(e.target.files?.[0])} aria-label="Upload payload" />
              </label>
            ) : null}

            <label style={{ display: 'block', marginTop: '0.75rem' }}>
              <span className="field-label">Payload (XML / JSON / CSV)</span>
              <textarea
                className="mono"
                rows={10}
                value={payload}
                onChange={(e) => setPayload(e.target.value)}
                placeholder="Paste a payload…"
                aria-label="Payload"
              />
            </label>

            <Button onClick={run} disabled={busy} style={{ marginTop: '0.75rem' }}>
              <FileSearch size={14} /> {busy ? 'Analyzing…' : 'Analyze'}
            </Button>
          </div>
        </Card>

        <div className="stack">
          {result ? (
            <>
              <Card>
                <CardHead
                  title="Result"
                  actions={<span className={badgeClass(result.address_readiness)}>{labelize(result.address_readiness)}</span>}
                />
                <div className="card-body">
                  <Tabs tabs={TABS} active={tab} onChange={setTab} />
                  {tab === 'overview' ? (
                    <ul className="status-list">
                      <li><span className="label">Case</span><span className="mono">{result.case_id ?? '—'}</span></li>
                      <li><span className="label">Validation</span><span className={badgeClass(result.original_validation_status)}>{labelize(result.original_validation_status)}</span></li>
                      <li><span className="label">Repair status</span><span>{labelize(result.repair_status)}</span></li>
                      <li><span className="label">Address provider</span><span>{result.address_provider ?? '—'} {result.address_provider_coverage ? `(${result.address_provider_coverage})` : ''}</span></li>
                      <li><span className="label">Profile version</span><span className="mono">{result.integration_profile_version ?? '—'}</span></li>
                      <li><span className="label">Mapping version</span><span className="mono">{result.mapping_version ?? '—'}</span></li>
                      <li><span className="label">Ruleset version</span><span className="mono">{result.ruleset_version ?? '—'}</span></li>
                      <li><span className="label">Engine version</span><span className="mono">{result.engine_version ?? '—'}</span></li>
                      <li><span className="label">Processed</span><span>{formatDateTime(result.processed_at)}</span></li>
                    </ul>
                  ) : null}
                  {tab === 'rules' ? (
                    (result.rule_findings ?? []).length === 0 ? (
                      <EmptyState title="No rule findings" />
                    ) : (
                      <ul className="status-list">
                        {(result.rule_findings ?? []).map((f, i) => (
                          <li key={`${f.rule_id}-${i}`}>
                            <span><strong className="mono">{f.rule_id}</strong> · {f.message}</span>
                            <span className={badgeClass(f.severity)}>{labelize(f.severity)}</span>
                          </li>
                        ))}
                      </ul>
                    )
                  ) : null}
                  {tab === 'address' ? (
                    (result.address_analyses ?? []).length === 0 ? (
                      <EmptyState title="No address analysis" />
                    ) : (
                      <ul className="status-list">
                        {(result.address_analyses ?? []).map((a, i) => (
                          <li key={i}>
                            <span>{a.party ?? 'party'} · {a.country_code ?? '—'} {a.town_name ? `(${a.town_name})` : ''}</span>
                            <span className={badgeClass(a.readiness)}>{labelize(a.readiness)}</span>
                          </li>
                        ))}
                      </ul>
                    )
                  ) : null}
                  {tab === 'repair' ? (
                    <>
                      <ul className="status-list">
                        <li><span className="label">Candidate validation</span><span className={badgeClass(result.candidate_validation_status)}>{labelize(result.candidate_validation_status)}</span></li>
                        <li><span className="label">Output hash</span><span className="mono">{result.output_hash ? `${result.output_hash.slice(0, 16)}…` : '—'}</span></li>
                      </ul>
                      {(result.candidate_diff ?? []).length === 0 ? (
                        <EmptyState title="No repair changes" />
                      ) : (
                        <ul className="status-list">
                          {(result.candidate_diff ?? []).map((d, i) => (
                            <li key={i}>
                              <span className="mono">{d.path}</span>
                              <span className="muted small">{d.before ?? '—'} → {d.after ?? '—'} ({labelize(d.status)})</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </>
                  ) : null}
                </div>
              </Card>
              {(result.warnings ?? []).length > 0 ? (
                <Card><CardHead title="Warnings" /><div className="card-body"><ul className="status-list">{(result.warnings ?? []).map((w, i) => <li key={i}>{w}</li>)}</ul></div></Card>
              ) : null}
            </>
          ) : (
            <Card><EmptyState title="No analysis yet" message="Select a profile and analyze a payload." /></Card>
          )}
        </div>
      </div>
    </AppShell>
  );
}
