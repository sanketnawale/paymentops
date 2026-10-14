'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, GitBranch } from 'lucide-react';
import AppShell from '@/components/AppShell';
import { Card, EmptyState, ErrorState, PageHeader, Skeleton } from '@/components/ui';
import { listProfiles, type Profile } from '@/lib/api';
import { badgeClass, labelize } from '@/lib/status';

export default function ProfilesPage() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setProfiles(await listProfiles());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load profiles');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Configuration"
        title="Integration profiles"
        description="Published contracts that map source payloads to canonical payment data and a governed ruleset."
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}

      {loading ? (
        <Card><Skeleton lines={3} /></Card>
      ) : profiles.length === 0 ? (
        <Card><EmptyState title="No integration profiles" message="Create a profile to begin ingesting payment data." /></Card>
      ) : (
        <div className="metric-grid">
          {profiles.map((p) => (
            <Card key={p.id}>
              <div className="row-between">
                <span className="metric-icon" aria-hidden="true"><GitBranch size={17} /></span>
                <span className={badgeClass(p.status)}>{labelize(p.status)}</span>
              </div>
              <Link href={`/profiles/${p.id}`} className="display" style={{ display: 'block', marginTop: '1rem', fontSize: '1rem', fontWeight: 600 }}>
                {p.name}
              </Link>
              <p className="muted small" style={{ marginTop: '0.25rem' }}>{p.description || 'No description'}</p>
              <ul className="status-list" style={{ marginTop: '0.75rem' }}>
                <li><span className="label">Input format</span><span className="mono">{p.input_format}</span></li>
                <li><span className="label">Version</span><span className="mono">v{p.version_number ?? 1}</span></li>
              </ul>
              <Link href={`/profiles/${p.id}`} className="row small" style={{ marginTop: '0.75rem', gap: '0.35rem' }}>
                Open profile <ArrowRight size={13} aria-hidden="true" />
              </Link>
            </Card>
          ))}
        </div>
      )}
    </AppShell>
  );
}
