'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { AlertTriangle, ArrowLeft, Brain, ShieldCheck } from 'lucide-react';
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
import { getInvestigation, type InvestigationDetail } from '@/lib/api';
import { badgeClass, formatDateTime, labelize } from '@/lib/status';

const TERMINAL = new Set(['COMPLETED', 'FAILED', 'PREPARED']);
const MAX_POLLS = 40;
const POLL_MS = 3000;

export default function InvestigationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<InvestigationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
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

  const running = detail ? !TERMINAL.has(detail.status) : false;
  const findings = detail?.deterministic_findings?.rule_findings ?? [];
  const agent = detail?.agent_result;
  const firstRuleFinding = findings[0];

  return (
    <AppShell>
      <PageHeader
        eyebrow={`Investigation / ${id}`}
        title={detail ? `Case ${labelize(detail.demo_case_key)}` : 'Investigation'}
        description={
          detail
            ? `${detail.message_version} · ruleset ${detail.ruleset_version ?? '—'} · engine ${detail.engine_version ?? '—'}`
            : undefined
        }
        actions={
          <div className="row">
            <Button variant="ghost" size="sm" onClick={() => load()} aria-label="Refresh">
              Refresh
            </Button>
            <Link href="/investigations" className="btn btn-ghost">
              <ArrowLeft size={14} /> All investigations
            </Link>
          </div>
        }
      />

      <Notice tone="accent">
        <ShieldCheck size={15} aria-hidden="true" />
        <span>
          <strong>Investigation only.</strong> {detail?.disclaimer ?? 'Deterministic validation is authoritative. The agent interprets; it does not authorize or execute payments.'}
        </span>
      </Notice>

      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}
      {!detail && !error ? (
        <Card>
          <Skeleton lines={5} />
        </Card>
      ) : null}

      {detail ? (
        <div className="grid-sidebar">
          <div className="stack">
            <Card>
              <CardHead
                title="Summary"
                sub="Deterministic validation state and integration metadata"
                actions={<span className={badgeClass(detail.status)}>{labelize(detail.status)}</span>}
              />
              <div className="card-body">
                <ul className="status-list">
                  <li>
                    <span className="label">Validation</span>
                    <span className={badgeClass(detail.validation_status)}>
                      {labelize(detail.validation_status)}
                    </span>
                  </li>
                  <li>
                    <span className="label">Message version</span>
                    <span className="mono">{detail.message_version}</span>
                  </li>
                  <li>
                    <span className="label">Input hash (SHA-256)</span>
                    <span className="mono">{detail.input_hash.slice(0, 16)}…</span>
                  </li>
                  <li>
                    <span className="label">Agent status</span>
                    <span>{detail.agent_status ?? (running ? 'in progress' : '—')}</span>
                  </li>
                  <li>
                    <span className="label">Evolus execution</span>
                    <span className="mono">
                      {detail.evolus_execution_id ? `${detail.evolus_execution_id.slice(0, 14)}…` : '—'}
                    </span>
                  </li>
                  <li>
                    <span className="label">Created</span>
                    <span>{formatDateTime(detail.created_at)}</span>
                  </li>
                  <li>
                    <span className="label">Updated</span>
                    <span>{formatDateTime(detail.updated_at)}</span>
                  </li>
                </ul>
              </div>
            </Card>

            <Card>
              <CardHead title="Deterministic findings" sub="Produced by the PaymentOps engine (authoritative)" />
              <div className="card-body">
                {findings.length === 0 ? (
                  <EmptyState
                    title="No deterministic rule findings"
                    message="The engine reported no rule findings for this case. This is not proof of payment safety or account ownership."
                  />
                ) : (
                  <ul className="status-list">
                    {findings.map((f, i) => (
                      <li key={`${f.rule_id}-${i}`}>
                        <span>
                          <strong className="mono">{f.rule_id}</strong> · {f.message}
                          {f.target ? (
                            <>
                              <br />
                              <span className="muted small mono">{f.target}</span>
                            </>
                          ) : null}
                          {f.evidence && f.evidence.length > 0 ? (
                            <>
                              <br />
                              <span className="muted small">{f.evidence.join('; ')}</span>
                            </>
                          ) : null}
                        </span>
                        <span className={badgeClass(f.severity)}>{labelize(f.severity)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Card>
          </div>

          <div className="stack">
            <Card>
              <CardHead
                title="Investigator findings"
                sub="Agent interpretation of the engine output"
                actions={<Brain size={15} aria-hidden="true" />}
              />
              <div className="card-body">
                {detail.error ? (
                  <Notice tone="danger">
                    <AlertTriangle size={15} aria-hidden="true" />
                    <span>
                      <strong>Integration failure.</strong> {detail.error}
                    </span>
                  </Notice>
                ) : null}

                {running && !detail.error ? (
                  <Notice tone="accent">
                    <span>
                      Investigation in progress. This page refreshes automatically while the Evolus
                      workflow runs.
                    </span>
                  </Notice>
                ) : null}

                {detail.status === 'COMPLETED' && !detail.error ? (
                  agent && (agent.explanation || agent.cited_rules?.length) ? (
                    <>
                      {agent.explanation ? (
                        <p style={{ marginTop: 0, whiteSpace: 'pre-wrap' }}>{agent.explanation}</p>
                      ) : null}
                      {agent.cited_rules && agent.cited_rules.length > 0 ? (
                        <>
                          <p className="field-label" style={{ marginTop: '0.75rem' }}>
                            Cited rules
                          </p>
                          <ul className="status-list">
                            {agent.cited_rules.map((rule) => (
                              <li key={rule}>
                                <span className="mono">{rule}</span>
                              </li>
                            ))}
                          </ul>
                        </>
                      ) : null}
                      <p className="field-label" style={{ marginTop: '0.75rem' }}>
                        Missing evidence
                      </p>
                      {agent.missing_evidence && agent.missing_evidence.length > 0 ? (
                        <ul className="status-list">
                          {agent.missing_evidence.map((item, i) => (
                            <li key={i}>
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="muted small">None reported.</p>
                      )}
                      <p className="field-label" style={{ marginTop: '0.75rem' }}>
                        Recommended human next step
                      </p>
                      <p style={{ marginTop: 0 }}>
                        {agent.recommended_next_step ?? 'Not provided by the agent.'}
                      </p>
                    </>
                  ) : (
                    <EmptyState
                      title="No agent output"
                      message="The run completed but returned no parseable agent explanation."
                    />
                  )
                ) : null}

                {detail.status === 'FAILED' && !detail.error ? (
                  <Notice tone="danger">
                    <AlertTriangle size={15} aria-hidden="true" />
                    <span>The investigation run reported a failure.</span>
                  </Notice>
                ) : null}

                {detail.status === 'PREPARED' ? (
                  <Notice tone="accent">
                    <span>
                      Prepared deterministically. The Evolus agent workflow was not started for
                      this run (prepare-only mode).
                    </span>
                  </Notice>
                ) : null}
              </div>
            </Card>

            <Card>
              <CardHead title="Synthetic input" sub="Immutable bundled demo payload" />
              <div className="card-body">
                {detail.synthetic_input ? (
                  <pre
                    className="mono"
                    style={{
                      margin: 0,
                      maxHeight: 320,
                      overflow: 'auto',
                      whiteSpace: 'pre-wrap',
                      fontSize: '0.72rem',
                    }}
                  >
                    {detail.synthetic_input}
                  </pre>
                ) : (
                  <EmptyState title="Input unavailable" />
                )}
                <p className="muted small" style={{ marginTop: '0.5rem' }}>
                  Synthetic data only. Engine finding for reference:{' '}
                  <span className="mono">{firstRuleFinding?.rule_id ?? 'none'}</span>.
                </p>
              </div>
            </Card>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
