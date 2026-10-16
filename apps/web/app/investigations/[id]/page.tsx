'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { AlertTriangle, ArrowLeft, Brain, FlaskConical, ShieldCheck } from 'lucide-react';
import AppShell from '@/components/AppShell';
import Markdown from '@/components/Markdown';
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
import { getInvestigation, testRepair, type InvestigationDetail } from '@/lib/api';
import { badgeClass, formatDateTime, labelize } from '@/lib/status';

const TERMINAL = new Set(['COMPLETED', 'FAILED', 'PREPARED']);
const MAX_POLLS = 40;
const POLL_MS = 3000;

export default function InvestigationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<InvestigationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [repairBusy, setRepairBusy] = useState(false);
  const [repairError, setRepairError] = useState<string | null>(null);
  const polls = useRef(0);

  const load = useCallback(async (): Promise<InvestigationDetail | null> => {
    try {
      const next = await getInvestigation(id);
      setDetail(next);
      setError(null);
      return next;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load investigation');
      return null;
    }
  }, [id]);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      const next = await load();
      if (!active || !next) return;
      if (!TERMINAL.has(next.status) && polls.current < MAX_POLLS) {
        polls.current += 1;
        timer = setTimeout(tick, POLL_MS);
      }
    };
    tick();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [load]);

  const runRepairTest = async () => {
    setRepairBusy(true);
    setRepairError(null);
    try {
      setDetail(await testRepair(id));
    } catch (e) {
      setRepairError(e instanceof Error ? e.message : 'Repair test failed');
    } finally {
      setRepairBusy(false);
    }
  };

  const running = detail ? !TERMINAL.has(detail.status) : false;
  const findings = detail?.deterministic_findings?.rule_findings ?? [];
  const agent = detail?.agent_result;
  const record = detail?.supporting_record;
  const repair = detail?.repair;
  const proposal = repair?.proposal;
  const sandbox = repair?.test;
  const inputLabel = detail?.input_label ?? 'sample';

  return (
    <AppShell>
      <PageHeader
        eyebrow={`Investigation / ${id}`}
        title={detail ? `${labelize(inputLabel ?? 'sample')} input · ${labelize(detail.demo_case_key)}` : 'Investigation'}
        description={
          detail
            ? `${detail.message_version} · ruleset ${detail.ruleset_version ?? '—'} · engine ${detail.engine_version ?? '—'}`
            : undefined
        }
        actions={
          <div className="row">
            <Button variant="ghost" size="sm" onClick={() => load()} aria-label="Refresh">Refresh</Button>
            <Link href="/investigations" className="btn btn-ghost"><ArrowLeft size={14} /> All investigations</Link>
          </div>
        }
      />

      <Notice tone="accent">
        <ShieldCheck size={15} aria-hidden="true" />
        <span><strong>Investigation only.</strong> {detail?.disclaimer}</span>
      </Notice>

      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}
      {!detail && !error ? <Card><Skeleton lines={5} /></Card> : null}

      {detail ? (
        <div className="grid-sidebar">
          {/* LEFT: engine truth */}
          <div className="stack">
            <Card>
              <CardHead
                title="Summary"
                sub="Deterministic engine state and integration metadata"
                actions={<span className={badgeClass(detail.status)}>{labelize(detail.status)}</span>}
              />
              <div className="card-body">
                <ul className="status-list">
                  <li>
                    <span className="label">Schema validity (XSD)</span>
                    <span className={badgeClass(detail.validation_status)}>{labelize(detail.validation_status)}</span>
                  </li>
                  <li>
                    <span className="label">Address readiness (engine)</span>
                    <span className={badgeClass(detail.deterministic_findings?.address_readiness)}>
                      {labelize(detail.deterministic_findings?.address_readiness)}
                    </span>
                  </li>
                  <li>
                    <span className="label">Input</span>
                    <span>{labelize(inputLabel ?? 'sample')} · <span className="muted small">{detail.case_origin ?? '—'}</span></span>
                  </li>
                  <li>
                    <span className="label">Workflow status</span>
                    <span>{labelize(detail.status)}{running ? ' · in progress' : ''}</span>
                  </li>
                  <li>
                    <span className="label">Created</span>
                    <span>{formatDateTime(detail.created_at)}</span>
                  </li>
                </ul>
              </div>
            </Card>

            <Card>
              <CardHead title="Deterministic findings" sub="Real PaymentOps engine output (authoritative)" />
              <div className="card-body">
                <p className="muted small" style={{ marginTop: 0 }}>
                  Schema validity and address readiness are reported separately above; the findings
                  below are deterministic rule results, not the agent&apos;s opinion.
                </p>
                {findings.length === 0 ? (
                  <EmptyState
                    title="No deterministic rule findings"
                    message="A finding was not raised. This does not by itself prove that every address or payment check passed."
                  />
                ) : (
                  <ul className="status-list">
                    {findings.map((f, i) => (
                      <li key={`${f.rule_id}-${i}`}>
                        <span>
                          <strong className="mono">{f.rule_id}</strong> · {f.message}
                          {f.target ? (<><br /><span className="muted small mono">{f.target}</span></>) : null}
                          {f.evidence && f.evidence.length > 0 ? (<><br /><span className="muted small">{f.evidence.join('; ')}</span></>) : null}
                        </span>
                        <span className={badgeClass(f.severity)}>{labelize(f.severity)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Card>
          </div>

          {/* RIGHT: agent interpretation + evidence + sandbox repair */}
          <div className="stack">
            <Card>
              <CardHead title="Investigator report" sub="Agent interpretation of the engine output" actions={<Brain size={15} aria-hidden="true" />} />
              <div className="card-body">
                {detail.error ? (
                  <Notice tone="danger"><AlertTriangle size={15} aria-hidden="true" /><span><strong>Integration failure.</strong> {detail.error}</span></Notice>
                ) : null}
                {running && !detail.error ? (
                  <Notice tone="accent"><span>Investigation in progress. This page refreshes automatically while the Evolus workflow runs.</span></Notice>
                ) : null}

                {detail.status === 'COMPLETED' && !detail.error ? (
                  detail.answer_text || agent?.explanation ? (
                    <>
                      {agent?.answer_separation_reliable === false ? (
                        <Notice tone="warn">
                          <span>Formatting note: the final answer could not be cleanly separated from the model&apos;s inline reasoning, so the full parsed text is shown. Nothing was removed.</span>
                        </Notice>
                      ) : null}
                      <Markdown>{detail.answer_text || agent?.explanation || ''}</Markdown>
                      <p className="field-label" style={{ marginTop: '0.75rem' }}>Rule agreement (agent mentions ∩ engine)</p>
                      {agent?.agreement_rules && agent.agreement_rules.length > 0 ? (
                        <ul className="status-list">{agent.agreement_rules.map((r) => (<li key={r}><span className="mono">{r}</span></li>))}</ul>
                      ) : (<p className="muted small">None.</p>)}
                      <p className="muted small" style={{ marginTop: '0.5rem' }}>
                        A matching rule id is agreement, not proof the explanation is correct.
                      </p>
                      <p className="field-label" style={{ marginTop: '0.75rem' }}>Missing evidence</p>
                      {agent?.missing_evidence && agent.missing_evidence.length > 0 ? (
                        <ul className="status-list">{agent.missing_evidence.map((m, i) => (<li key={i}><span>{m}</span></li>))}</ul>
                      ) : (<p className="muted small">None reported.</p>)}
                      <p className="field-label" style={{ marginTop: '0.75rem' }}>Recommended human next step</p>
                      <p style={{ marginTop: 0 }}>{agent?.recommended_next_step ?? proposal?.recommended_next_step ?? 'Not provided by the agent.'}</p>
                    </>
                  ) : (
                    <EmptyState title="No agent output" message="The run completed but returned no parseable agent explanation." />
                  )
                ) : null}

                {detail.status === 'FAILED' && !detail.error ? (
                  <Notice tone="danger"><AlertTriangle size={15} aria-hidden="true" /><span>The investigation run reported a failure.</span></Notice>
                ) : null}
                {detail.status === 'PREPARED' ? (
                  <Notice tone="accent"><span>Prepared deterministically. The Evolus agent workflow was not started for this run (prepare-only mode).</span></Notice>
                ) : null}
              </div>
            </Card>

            {record ? (
              <Card>
                <CardHead title="Supporting evidence" sub={`${record.record_id} · synthetic record`} />
                <div className="card-body">
                  <p className="muted small" style={{ marginTop: 0 }}>{record.label} — {record.source}</p>
                  <ul className="status-list">
                    {(record.entries ?? []).map((e) => (
                      <li key={e.ref}>
                        <span><strong className="mono">{e.party}</strong> · {e.field} = <strong>{e.value}</strong><br /><span className="muted small mono">{e.ref}</span></span>
                      </li>
                    ))}
                  </ul>
                  {(record.gaps ?? []).map((g, i) => (<p key={`g${i}`} className="muted small">GAP: {g}</p>))}
                  {(record.contradictions ?? []).map((c, i) => (<p key={`c${i}`} className="muted small">CONTRADICTION: {c}</p>))}
                </div>
              </Card>
            ) : null}

            <Card>
              <CardHead
                title="Sandbox repair"
                sub="Proposed changes are tested on a copy of the input; the original is never modified"
                actions={<span className={badgeClass(repair?.status ?? 'NONE')}>{labelize(repair?.status ?? 'NONE')}</span>}
              />
              <div className="card-body">
                {proposal?.status === 'PROPOSAL_UNPARSEABLE' ? (
                  <Notice tone="warn"><span>No structured proposal could be parsed from the agent output: {proposal.error}</span></Notice>
                ) : null}

                <p className="field-label" style={{ marginTop: 0 }}>Proposed changes (not yet tested)</p>
                {(proposal?.changes ?? []).length === 0 ? (
                  <p className="muted small">No changes proposed.</p>
                ) : (
                  <ul className="status-list">
                    {(proposal?.changes ?? []).map((c, i) => (
                      <li key={i}><span><strong className="mono">{c.target}</strong> = {c.value}<br /><span className="muted small">evidence: <span className="mono">{c.evidence_ref}</span></span></span></li>
                    ))}
                  </ul>
                )}
                {(repair?.rejected_changes ?? []).length > 0 ? (
                  <>
                    <p className="field-label" style={{ marginTop: '0.75rem' }}>Rejected changes</p>
                    <ul className="status-list">
                      {(repair?.rejected_changes ?? []).map((r, i) => (
                        <li key={i}><span><strong className="mono">{r.target || '—'}</strong> · {r.reason}</span><span className={badgeClass('REJECTED')}>{labelize('REJECTED')}</span></li>
                      ))}
                    </ul>
                  </>
                ) : null}
                <Button onClick={runRepairTest} disabled={repairBusy || !proposal || proposal.status !== 'PROPOSED'} style={{ marginTop: '0.75rem' }}>
                  <FlaskConical size={14} /> {repairBusy ? 'Testing…' : 'Test proposed repair'}
                </Button>
                {repairError ? <p className="small" style={{ color: 'var(--cn-danger)' }} role="alert">{repairError}</p> : null}

                {sandbox ? (
                  <>
                    <p className="field-label" style={{ marginTop: '0.75rem' }}>Tested results (sandbox copy)</p>
                    <ul className="status-list">
                      <li><span className="label">Review status</span><span className={badgeClass(sandbox.review_status)}>{labelize(sandbox.review_status)}</span></li>
                      <li><span className="label">XSD valid</span><span>{String(sandbox.xsd_valid)}</span></li>
                      <li><span className="label">Findings: original → sandbox</span><span className="mono">{(sandbox.before_findings ?? []).map((f) => f.rule_id).join(', ') || 'none'} → {(sandbox.after_findings ?? []).map((f) => f.rule_id).join(', ') || 'none'}</span></li>
                      <li><span className="label">Re-validated by</span><span className="mono">{sandbox.revalidated_by ?? '—'}</span></li>
                    </ul>
                    {(sandbox.unresolved_findings ?? []).length > 0 ? (
                      <>
                        <p className="field-label" style={{ marginTop: '0.75rem' }}>Unresolved findings (need human review)</p>
                        <ul className="status-list">{(sandbox.unresolved_findings ?? []).map((f, i) => (<li key={i}><span className="mono">{f.rule_id}@{f.target}</span></li>))}</ul>
                      </>
                    ) : null}
                    {(sandbox.applied_changes ?? []).length > 0 ? (
                      <>
                        <p className="field-label" style={{ marginTop: '0.75rem' }}>Applied changes (sandbox only)</p>
                        <ul className="status-list">
                          {(sandbox.applied_changes ?? []).map((a, i) => (
                            <li key={i}><span className="mono">{a.path}</span><span className="muted small">{a.before ?? '—'} → {a.after}</span></li>
                          ))}
                        </ul>
                      </>
                    ) : null}
                    <p className="muted small" style={{ marginTop: '0.5rem' }}>
                      {sandbox.disclaimer} A sandbox passing the selected deterministic checks is{' '}
                      <strong>not proof of full address correctness</strong>.
                    </p>
                  </>
                ) : null}
              </div>
            </Card>

            {/* Developer diagnostics — collapsed by default */}
            <Card>
              <CardHead title="Developer diagnostics" sub="Collapsed: raw output, reasoning, hashes, input" />
              <div className="card-body">
                <details>
                  <summary className="field-label">Execution &amp; hashes</summary>
                  <ul className="status-list" style={{ marginTop: '0.5rem' }}>
                    <li><span className="label">Evolus execution</span><span className="mono">{detail.evolus_execution_id ?? '—'}</span></li>
                    <li><span className="label">Trace id</span><span className="mono">{detail.evolus_trace_id ?? '—'}</span></li>
                    <li><span className="label">Original hash</span><span className="mono">{detail.input_hash}</span></li>
                    <li><span className="label">Evidence hash</span><span className="mono">{detail.evidence_hash ?? '—'}</span></li>
                    <li><span className="label">Sandbox hash</span><span className="mono">{sandbox?.sandbox_hash ?? '—'}</span></li>
                  </ul>
                </details>
                {agent?.reasoning_inline_excerpt ? (
                  <details style={{ marginTop: '0.5rem' }}>
                    <summary className="field-label">Model reasoning (inline)</summary>
                    <pre className="mono" style={{ margin: 0, maxHeight: 200, overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: '0.72rem' }}>{agent.reasoning_inline_excerpt}</pre>
                  </details>
                ) : null}
                {agent?.output_text ? (
                  <details style={{ marginTop: '0.5rem' }}>
                    <summary className="field-label">Raw agent output</summary>
                    <pre className="mono" style={{ margin: 0, maxHeight: 260, overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: '0.72rem' }}>{agent.output_text}</pre>
                  </details>
                ) : null}
                <details style={{ marginTop: '0.5rem' }}>
                  <summary className="field-label">Synthetic input ({labelize(inputLabel ?? 'sample')})</summary>
                  {detail.synthetic_input ? (
                    <pre className="mono" style={{ margin: 0, maxHeight: 260, overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: '0.72rem' }}>{detail.synthetic_input}</pre>
                  ) : (<p className="muted small">Input unavailable.</p>)}
                </details>
              </div>
            </Card>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
