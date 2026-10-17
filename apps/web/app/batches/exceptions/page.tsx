'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {
  Boxes,
  Download,
  FlaskConical,
  Plus,
  ShieldCheck,
  Trash2,
} from 'lucide-react';
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
  createExceptionBatch,
  exportExceptionBatch,
  getExceptionBatch,
  listExceptionBatches,
  testExceptionItemRepair,
  type ExceptionBatchDetail,
  type ExceptionBatchItemInput,
  type ExceptionBatchSummary,
} from '@/lib/api';
import { badgeClass, formatDateTime, labelize } from '@/lib/status';
import {
  ACTIVE_BATCH_STATUSES as ACTIVE,
  canTest,
  isClean,
  isEvaluated,
  itemOutcomeLabel,
} from '@/lib/batchStatus';

const MAX_ITEMS = 5;
const MAX_XML_BYTES = 262_144;
const MAX_EVIDENCE_BYTES = 65_536;
const POLL_MS = 3500;

interface Row {
  xml: string;
  xmlName: string;
  evidence: string;
  evidenceName: string;
}

const emptyRow = (): Row => ({ xml: '', xmlName: '', evidence: '', evidenceName: '' });

function readFile(
  file: File | undefined,
  maxBytes: number,
  onText: (text: string, name: string) => void,
  onError: (message: string) => void,
) {
  if (!file) return;
  if (file.size > maxBytes) {
    onError(`The selected file exceeds the ${Math.round(maxBytes / 1024)} KiB limit.`);
    return;
  }
  const reader = new FileReader();
  reader.onload = () => onText(String(reader.result ?? ''), file.name);
  reader.onerror = () => onError('The file could not be read.');
  reader.readAsText(file);
}

export default function BatchExceptionDeskPage() {
  const [batches, setBatches] = useState<ExceptionBatchSummary[]>([]);
  const [detail, setDetail] = useState<ExceptionBatchDetail | null>(null);
  const [rows, setRows] = useState<Row[]>([emptyRow()]);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [itemBusy, setItemBusy] = useState<string | null>(null);
  const idempotency = useRef<string>('');
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const loadList = useCallback(async () => {
    try {
      setBatches(await listExceptionBatches());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load batches');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadDetail = useCallback(async (batchId: string, poll = false) => {
    try {
      const next = await getExceptionBatch(batchId);
      setDetail(next);
      if (poll && next.items.some((i) => ACTIVE.has(i.status))) {
        timer.current = setTimeout(() => loadDetail(batchId, true), POLL_MS);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load batch');
    }
  }, []);

  useEffect(() => {
    loadList();
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [loadList]);

  const updateRow = (index: number, patch: Partial<Row>) =>
    setRows((current) => current.map((r, i) => (i === index ? { ...r, ...patch } : r)));

  const addRow = () => setRows((c) => (c.length < MAX_ITEMS ? [...c, emptyRow()] : c));
  const removeRow = (index: number) =>
    setRows((c) => (c.length > 1 ? c.filter((_, i) => i !== index) : c));

  const submit = async () => {
    setFormError(null);
    const items: ExceptionBatchItemInput[] = [];
    for (const [i, row] of rows.entries()) {
      if (!row.xml.trim()) {
        setFormError(`Row ${i + 1}: an ISO 20022 XML file is required.`);
        return;
      }
      let evidence: Record<string, unknown> | null = null;
      if (row.evidence.trim()) {
        try {
          evidence = JSON.parse(row.evidence) as Record<string, unknown>;
        } catch {
          setFormError(`Row ${i + 1}: the evidence file is not valid JSON.`);
          return;
        }
      }
      items.push({ xml: row.xml, evidence, filename: row.xmlName || null });
    }
    setBusy(true);
    idempotency.current = idempotency.current || `ui-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    try {
      const created = await createExceptionBatch(items, idempotency.current);
      setDetail(created);
      setRows([emptyRow()]);
      idempotency.current = '';
      await loadList();
      loadDetail(created.batch_id, true);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Batch submission failed');
    } finally {
      setBusy(false);
    }
  };

  const testItem = async (itemId: string) => {
    if (!detail) return;
    setItemBusy(itemId);
    try {
      setDetail(await testExceptionItemRepair(detail.batch_id, itemId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Repair test failed');
    } finally {
      setItemBusy(null);
    }
  };

  const downloadExport = async () => {
    if (!detail) return;
    try {
      const report = await exportExceptionBatch(detail.batch_id);
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${detail.batch_id}-review.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Export failed');
    }
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="AI investigation"
        title="Batch Exception Desk"
        description="Process up to five synthetic pacs.008 cases as one bounded batch. Each item is a single transaction with its own optional evidence."
        actions={
          <Link href="/investigations" className="btn btn-ghost">
            <Boxes size={14} /> Investigations
          </Link>
        }
      />

      <Notice tone="accent">
        <ShieldCheck size={15} aria-hidden="true" />
        <span>
          <strong>Synthetic data only.</strong> Batch progress is investigation progress — not
          validation, sandbox success, or human approval. Repairs are tested only on sandbox copies;
          originals are never modified and no payment is executed.
        </span>
      </Notice>

      {error ? <ErrorState message={error} onRetry={loadList} /> : null}

      <div className="grid-sidebar">
        <div className="stack">
          <Card>
            <CardHead title="New batch" sub={`Up to ${MAX_ITEMS} items · XML required · evidence optional per row`} />
            <div className="card-body">
              {rows.map((row, index) => (
                <div key={index} className="stack" style={{ borderTop: index ? '1px solid var(--cn-border)' : 'none', paddingTop: index ? '0.75rem' : 0, marginTop: index ? '0.75rem' : 0 }}>
                  <div className="row-between">
                    <span className="field-label" style={{ margin: 0 }}>Row {index + 1}</span>
                    <Button variant="ghost" size="sm" onClick={() => removeRow(index)} disabled={rows.length === 1} aria-label={`Remove row ${index + 1}`}>
                      <Trash2 size={13} /> Remove
                    </Button>
                  </div>
                  <label>
                    <span className="field-label">ISO 20022 XML (required)</span>
                    <input
                      type="file"
                      accept=".xml,application/xml,text/xml"
                      aria-label={`Row ${index + 1} XML file`}
                      onChange={(e) =>
                        readFile(e.target.files?.[0], MAX_XML_BYTES, (text, name) => updateRow(index, { xml: text, xmlName: name }), setFormError)
                      }
                    />
                  </label>
                  {row.xmlName ? <p className="muted small" style={{ margin: 0 }}>XML: <span className="mono">{row.xmlName}</span></p> : null}
                  <label>
                    <span className="field-label">Supporting-evidence JSON (optional, this item only)</span>
                    <input
                      type="file"
                      accept=".json,application/json"
                      aria-label={`Row ${index + 1} evidence file`}
                      onChange={(e) =>
                        readFile(e.target.files?.[0], MAX_EVIDENCE_BYTES, (text, name) => updateRow(index, { evidence: text, evidenceName: name }), setFormError)
                      }
                    />
                  </label>
                  {row.evidenceName ? <p className="muted small" style={{ margin: 0 }}>Evidence: <span className="mono">{row.evidenceName}</span></p> : null}
                </div>
              ))}

              <div className="row" style={{ marginTop: '0.75rem' }}>
                <Button variant="ghost" size="sm" onClick={addRow} disabled={rows.length >= MAX_ITEMS}>
                  <Plus size={13} /> Add row
                </Button>
                <span className="muted small">{rows.length} / {MAX_ITEMS} rows</span>
              </div>

              {formError ? <p className="small" style={{ color: 'var(--cn-danger)' }} role="alert">{formError}</p> : null}
              <Button onClick={submit} disabled={busy} style={{ marginTop: '0.75rem' }}>
                <Boxes size={14} /> {busy ? 'Submitting…' : 'Submit batch'}
              </Button>
            </div>
          </Card>

          <Card>
            <CardHead title="Recent batches" sub="Tenant-scoped" />
            <div className="card-body">
              {loading ? (
                <Skeleton lines={3} />
              ) : batches.length === 0 ? (
                <EmptyState title="No batches yet" message="Submit a batch of up to five synthetic cases." />
              ) : (
                <ul className="status-list">
                  {batches.map((b) => (
                    <li key={b.batch_id}>
                      <span>
                        <button className="btn-link mono" onClick={() => { idempotency.current = ''; setDetail(null); loadDetail(b.batch_id, true); }}>
                          {b.batch_id}
                        </button>
                        <br />
                        <span className="muted small">
                          {b.completed}/{b.total_items} completed · {b.failed} failed · {b.rejected} rejected · {formatDateTime(b.created_at)}
                        </span>
                      </span>
                      <span className={badgeClass(b.status)}>{labelize(b.status)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Card>
        </div>

        <Card>
          <CardHead
            title={detail ? `Batch ${detail.batch_id}` : 'Batch detail'}
            sub="Per-item progress, original findings, sandbox test state and errors"
            actions={
              detail ? (
                <div className="row">
                  <Button variant="ghost" size="sm" onClick={() => loadDetail(detail.batch_id, true)}>Refresh</Button>
                  <Button variant="ghost" size="sm" onClick={downloadExport}><Download size={13} /> Review export</Button>
                </div>
              ) : null
            }
          />
          <div className="card-body">
            {!detail ? (
              <EmptyState title="Select a batch" message="Submit a new batch or open one from the list." />
            ) : (
              <>
                <ul className="status-list">
                  <li><span className="label">Status</span><span className={badgeClass(detail.status)}>{labelize(detail.status)}</span></li>
                  <li><span className="label">Items</span><span>{detail.completed}/{detail.total_items} completed</span></li>
                  <li><span className="label">Created</span><span>{formatDateTime(detail.created_at)}</span></li>
                </ul>

                {detail.items.map((item) => {
                  const outcome = itemOutcomeLabel(item);
                  const evaluated = isEvaluated(item);
                  return (
                    <div key={item.item_id} className="stack" style={{ borderTop: '1px solid var(--cn-border)', marginTop: '0.75rem', paddingTop: '0.75rem' }}>
                      <div className="row-between">
                        <span>
                          <strong>Item {item.item_index + 1}</strong>{' '}
                          <span className="muted small mono">{item.display_filename ?? item.item_id}</span>
                        </span>
                        <span className={badgeClass(outcome.tone)}>{outcome.text}</span>
                      </div>
                      <ul className="status-list">
                        <li><span className="label">Progress</span><span className={badgeClass(item.status)}>{labelize(item.status)}</span></li>
                        <li>
                          <span className="label">Investigation</span>
                          <span>
                            {item.investigation_id ? (
                              <Link href={`/investigations/${item.investigation_id}`} className="mono">{item.investigation_id}</Link>
                            ) : ('—')}
                          </span>
                        </li>
                        <li>
                          <span className="label">Validation / findings</span>
                          {evaluated ? (
                            <span>{(item.original_findings ?? []).length} · {(item.original_findings ?? []).map((f) => f.rule_id).join(', ') || 'none'}</span>
                          ) : (
                            <span className="muted">Not evaluated</span>
                          )}
                        </li>
                        <li>
                          <span className="label">Proposed (server-validated)</span>
                          {evaluated ? (
                            <span>{(item.proposed_changes ?? []).map((c) => `${c.target}=${c.value}`).join(', ') || 'none'}</span>
                          ) : (
                            <span className="muted">Not evaluated</span>
                          )}
                        </li>
                        <li>
                          <span className="label">Sandbox test</span>
                          {evaluated ? (
                            <span>{(item.sandbox?.applied_changes ?? []).map((c) => `${c.target}=${c.value}`).join(', ') || 'Not tested'}</span>
                          ) : (
                            <span className="muted">Not evaluated</span>
                          )}
                        </li>
                        <li>
                          <span className="label">Remaining findings</span>
                          {evaluated ? (
                            <span>{(item.remaining_findings ?? []).length} · {(item.remaining_findings ?? []).map((f) => f.rule_id).join(', ') || (item.sandbox ? 'none' : 'n/a')}</span>
                          ) : (
                            <span className="muted">Not evaluated</span>
                          )}
                        </li>
                      </ul>

                      {(item.unresolved_findings ?? []).length > 0 ? (
                        <p className="muted small">Unresolved (need human review): <span className="mono">{(item.unresolved_findings ?? []).map((f) => `${f.rule_id}@${f.target}`).join(', ')}</span></p>
                      ) : null}
                      {isClean(item) ? (
                        <p className="muted small">No repair needed — the deterministic engine raised no findings for this item.</p>
                      ) : null}
                      {item.error ? (
                        <Notice tone="danger"><span>{item.status === 'REJECTED' ? 'Rejected: ' : 'Error: '}{item.error}</span></Notice>
                      ) : null}

                      <div>
                        <Button
                          size="sm"
                          onClick={() => testItem(item.item_id)}
                          disabled={itemBusy === item.item_id || !canTest(item)}
                        >
                          <FlaskConical size={13} /> {itemBusy === item.item_id ? 'Testing…' : 'Test supported repairs'}
                        </Button>
                        {!canTest(item) ? (
                          <span className="muted small" style={{ marginLeft: '0.5rem' }}>
                            {(item.sandbox?.applied_changes ?? []).length > 0
                              ? 'Already tested on the sandbox copy.'
                              : (item.proposed_changes ?? []).length === 0
                                ? 'No supported repair to test.'
                                : 'Available once the investigation completes.'}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  );
                })}

                <p className="muted small" style={{ marginTop: '0.75rem' }}>{detail.disclaimer}</p>
              </>
            )}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
