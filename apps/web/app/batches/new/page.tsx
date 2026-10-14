'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '@/components/AppShell';
import { Button, Card, CardHead, PageHeader } from '@/components/ui';
import { createBatch, listProfiles, type Profile } from '@/lib/api';

export default function NewBatchPage() {
  const router = useRouter();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [profileId, setProfileId] = useState('');
  const [csv, setCsv] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listProfiles()
      .then((p) => setProfiles(p))
      .catch(() => setProfiles([]));
  }, []);

  const submit = async () => {
    if (!profileId || !csv.trim()) {
      setError('Select a profile and provide CSV content.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await createBatch(profileId, csv);
      router.push(`/batches/${res.job_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Submit failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="Batch analysis"
        title="New batch"
        description="Submit a CSV payload for asynchronous analysis against a published integration profile."
      />

      <Card>
        <CardHead title="Batch input" sub="Header row required" />
        <div className="card-body">
          <div className="stack">
            <label>
              <span className="field-label">Integration profile</span>
              <select value={profileId} onChange={(e) => setProfileId(e.target.value)} aria-label="Integration profile">
                <option value="">— select —</option>
                {profiles.map((p) => (
                  <option key={p.id} value={p.id}>{p.name} ({p.input_format})</option>
                ))}
              </select>
            </label>
            <label>
              <span className="field-label">CSV content</span>
              <textarea
                className="mono"
                value={csv}
                onChange={(e) => setCsv(e.target.value)}
                rows={10}
                placeholder={'id,amount,ccy,name,city,country\n1,100.00,EUR,Acme,Milano,IT'}
                aria-label="CSV content"
              />
            </label>
            {error ? <p className="small" style={{ color: 'var(--cn-danger)' }} role="alert">{error}</p> : null}
            <div>
              <Button onClick={submit} disabled={submitting}>{submitting ? 'Submitting…' : 'Submit batch'}</Button>
            </div>
          </div>
        </div>
      </Card>
    </AppShell>
  );
}
