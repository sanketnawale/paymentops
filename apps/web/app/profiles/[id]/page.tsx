'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, Lock } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Button, Card, CardHead, EmptyState, ErrorState, Notice, PageHeader, Skeleton, TableWrap, Tabs } from '@/components/ui';
import { getProfile, getProfileVersions, testProfile, type ProfileDetail } from '@/lib/api';
import { badgeClass, formatDateTime, labelize } from '@/lib/status';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'mapping', label: 'Mapping' },
  { id: 'rules', label: 'Rules' },
  { id: 'test', label: 'Test' },
  { id: 'versions', label: 'Versions' },
];

export default function ProfileDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [profile, setProfile] = useState<ProfileDetail | null>(null);
  const [versions, setVersions] = useState<{ version_number: number; mapping_version: string; ruleset_version: string; published_at: string }[]>([]);
  const [tab, setTab] = useState('overview');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [testPayload, setTestPayload] = useState('');
  const [testResult, setTestResult] = useState<Record<string, unknown> | null>(null);
  const [testing, setTesting] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = await getProfile(id);
      setProfile(p);
      getProfileVersions(id).then(setVersions).catch(() => setVersions([]));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load profile');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const runTest = async () => {
    setTesting(true);
    setTestError(null);
    try {
      setTestResult(await testProfile(id, testPayload));
    } catch (e) {
      setTestError(e instanceof Error ? e.message : 'Test failed');
    } finally {
      setTesting(false);
    }
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="Integration profile"
        title={profile?.name ?? 'Profile'}
        description={profile ? `${profile.input_format} source contract` : undefined}
        actions={<Link href="/profiles" className="btn btn-ghost"><ArrowLeft size={14} /> All profiles</Link>}
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}
      {loading && !profile ? <Card><Skeleton lines={4} /></Card> : null}

      {profile ? (
        <>
          <Tabs tabs={TABS} active={tab} onChange={setTab} />

          {tab === 'overview' ? (
            <div className="grid-sidebar">
              <Card>
                <CardHead title="Profile overview" sub="Governed configuration in effect" actions={<span className={badgeClass(profile.status)}>{labelize(profile.status)}</span>} />
                <div className="card-body">
                  <ul className="status-list">
                    <li><span className="label">Input format</span><span className="mono">{profile.input_format}</span></li>
                    <li><span className="label">Output format</span><span className="mono">{profile.output_format ?? '—'}</span></li>
                    <li><span className="label">Version</span><span className="mono">v{profile.version_number ?? 1}</span></li>
                    <li><span className="label">Mapping version</span><span className="mono">{profile.mapping?.mapping_version ?? '—'}</span></li>
                    <li><span className="label">Retention</span><span>{labelize(profile.retention_policy)}</span></li>
                    <li><span className="label">Address policy</span><span>{labelize(profile.address_policy)}</span></li>
                    <li><span className="label">AI policy</span><span>{labelize(profile.ai_policy)}</span></li>
                    <li><span className="label">Published</span><span>{formatDateTime(profile.published_at)}</span></li>
                  </ul>
                </div>
              </Card>
              <Card>
                <CardHead title="Allowed ISO messages" sub="Exact versions this profile may ingest" />
                <div className="card-body">
                  {(profile.allowed_messages ?? []).length === 0 ? (
                    <EmptyState title="No explicit restriction" message="All supported ISO message versions are permitted." />
                  ) : (
                    <ul className="status-list">
                      {(profile.allowed_messages ?? []).map((m) => (
                        <li key={m}><span className="mono">{m}</span></li>
                      ))}
                    </ul>
                  )}
                </div>
              </Card>
            </div>
          ) : null}

          {tab === 'mapping' ? (
            <Card noPad>
              <CardHead title="Structured mapping" sub="Allowlisted transforms — arbitrary code is not supported" />
              <div className="card-body" style={{ paddingBottom: 0 }}>
                <Notice tone="accent"><Lock size={14} aria-hidden="true" /> Only approved transforms are available. Arbitrary code execution is not supported.</Notice>
              </div>
              <TableWrap>
                <table className="data">
                  <thead>
                    <tr><th>Source</th><th>Canonical target</th><th>Transform</th><th>Requirement</th></tr>
                  </thead>
                  <tbody>
                    {(profile.mapping?.fields ?? []).map((f) => (
                      <tr key={`${f.source}-${f.target}`}>
                        <td className="mono">{f.source}</td>
                        <td className="mono">{f.target}</td>
                        <td>{(f.transforms ?? []).join(', ') || '—'}</td>
                        <td>{labelize(f.required)}</td>
                      </tr>
                    ))}
                    {(profile.mapping?.fields ?? []).length === 0 && (
                      <tr><td colSpan={4} className="table-empty">No mapping fields configured.</td></tr>
                    )}
                  </tbody>
                </table>
              </TableWrap>
            </Card>
          ) : null}

          {tab === 'rules' ? (
            <Card>
              <CardHead title="Customer rules" sub="Declarative rules applied on top of system/default rules" />
              <div className="card-body">
                {(profile.rules ?? []).length === 0 ? (
                  <EmptyState title="No customer rules" message="System and default rules still apply." />
                ) : (
                  <ul className="status-list">
                    {(profile.rules ?? []).map((r) => (
                      <li key={r.rule_id}>
                        <span><strong className="mono">{r.rule_id}</strong> · {r.description ?? r.field ?? ''}</span>
                        <span className={badgeClass(r.severity)}>{labelize(r.severity)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Card>
          ) : null}

          {tab === 'test' ? (
            <div className="grid-2">
              <Card>
                <CardHead title="Sample input" sub="Dry test — no operational case is created" />
                <div className="card-body">
                  <textarea
                    className="mono"
                    rows={12}
                    value={testPayload}
                    onChange={(e) => setTestPayload(e.target.value)}
                    placeholder="Paste a sample payload"
                    aria-label="Test payload"
                  />
                  {testError ? <p className="small" style={{ color: 'var(--cn-danger)' }} role="alert">{testError}</p> : null}
                  <Button onClick={runTest} disabled={testing || !testPayload.trim()} style={{ marginTop: '0.75rem' }}>
                    {testing ? 'Running…' : 'Run dry test'}
                  </Button>
                </div>
              </Card>
              <Card>
                <CardHead title="Result" sub="Mapping and validation preview" />
                <div className="card-body">
                  {testResult ? <pre className="code">{JSON.stringify(testResult, null, 2)}</pre> : <EmptyState title="No result yet" message="Run a dry test to see the mapped payload." />}
                </div>
              </Card>
            </div>
          ) : null}

          {tab === 'versions' ? (
            <Card noPad>
              <CardHead title="Published versions" sub="Immutable snapshots" />
              <TableWrap>
                <table className="data">
                  <thead>
                    <tr><th>Version</th><th>Mapping</th><th>Ruleset</th><th>Published</th></tr>
                  </thead>
                  <tbody>
                    {versions.map((v) => (
                      <tr key={v.version_number}>
                        <td className="mono">v{v.version_number}</td>
                        <td className="mono">{v.mapping_version}</td>
                        <td className="mono">{v.ruleset_version}</td>
                        <td className="muted small">{formatDateTime(v.published_at)}</td>
                      </tr>
                    ))}
                    {versions.length === 0 && <tr><td colSpan={4} className="table-empty">No published versions.</td></tr>}
                  </tbody>
                </table>
              </TableWrap>
            </Card>
          ) : null}
        </>
      ) : null}
    </AppShell>
  );
}
