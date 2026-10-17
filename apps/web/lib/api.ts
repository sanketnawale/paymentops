export interface PlatformInfo {
  product: string;
  release?: string;
  version: string;
  build_sha?: string;
  build_date?: string;
  environment: string;
  ai_enabled: boolean;
  ai_provider: string;
  zero_retention_enabled: boolean;
  database_configured: boolean;
  redis_configured: boolean;
}

export interface HealthResult {
  status: string;
}

export interface ReadinessCheck {
  name: string;
  ok: boolean;
  detail: string;
}

export interface ReadinessResult {
  status: string;
  checks: ReadinessCheck[];
}

// Browser-facing base URL. Same-origin proxy path by default; the browser never talks to the
// internal Kubernetes service. Override only with a same-origin path in production.
export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? '/api/backend';

const REQUEST_TIMEOUT_MS = 30_000;

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

// Operator credentials are injected server-side by the /api/backend proxy. The browser must
// never hold API secrets, so no credential headers are set here.
function authHeaders(): Record<string, string> {
  return {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  };
}

// CSRF: echo the double-submit token (non-HttpOnly cookie) on mutating requests.
function csrfHeader(method: string | undefined): Record<string, string> {
  if (!method || ['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase())) return {};
  if (typeof document === 'undefined') return {};
  const match = document.cookie.match(/(?:^|; )paymentops_csrf=([^;]+)/);
  return match ? { 'X-CSRF-Token': decodeURIComponent(match[1]) } : {};
}

function redirectToLogin() {
  if (typeof window === 'undefined') return;
  if (window.location.pathname === '/login') return;
  window.location.href = '/login';
}

// Map backend structured errors into user-friendly messages (never expose stack traces).
function parseError(status: number, body: unknown): ApiError {
  const detail =
    typeof body === 'object' && body !== null
      ? (body as { detail?: unknown; error?: { code?: string; message?: string } }).detail ??
        (body as { error?: { code?: string; message?: string } }).error
      : undefined;

  if (typeof detail === 'string') {
    return new ApiError(detail, status);
  }
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: string; loc?: unknown[] } | undefined;
    const msg = first?.msg ?? 'Validation error';
    return new ApiError(msg, status);
  }
  if (typeof detail === 'object' && detail !== null) {
    const e = detail as { code?: string; message?: string };
    return new ApiError(e.message ?? `Request failed (${status})`, status, e.code);
  }
  if (status === 401) return new ApiError('Authentication failed. Check your credentials.', status);
  if (status === 403) return new ApiError('You are not authorized for this resource.', status);
  if (status === 404) return new ApiError('Resource not found.', status);
  if (status === 422) return new ApiError('The request could not be processed.', status);
  if (status === 413) return new ApiError('The payload is too large.', status);
  return new ApiError(`Request failed (${status})`, status);
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: init?.signal ?? controller.signal,
      headers: {
        ...authHeaders(),
        ...csrfHeader(init?.method),
        ...(init?.headers ?? {}),
      },
    });
  } catch (e) {
    clearTimeout(timeout);
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiError('The request timed out. Please try again.', 408);
    }
    throw new ApiError('Unable to reach the PaymentOps API.', 0);
  } finally {
    clearTimeout(timeout);
  }
  if (res.status === 401) {
    redirectToLogin();
    throw new ApiError('Your session has expired. Please sign in again.', 401);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw parseError(res.status, body);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export interface Profile {
  id?: string;
  name: string;
  description?: string;
  status?: string;
  input_format: string;
  version_number?: number;
}

export function listProfiles() {
  return apiJson<Profile[]>('/api/v1/integration-profiles');
}

export function createProfile(p: Profile) {
  return apiJson<Profile>('/api/v1/integration-profiles', { method: 'POST', body: JSON.stringify(p) });
}

export function publishProfile(id: string) {
  return apiJson<{ published: boolean }>(`/api/v1/integration-profiles/${id}/publish`, { method: 'POST' });
}

export interface CaseSummary {
  case_id: string;
  status: string;
  message_type?: string;
  message_version?: string;
  validation_status?: string;
  address_readiness?: string;
  repair_status?: string;
  address_provider_coverage?: string;
  mapping_version?: string;
  integration_profile_version?: string;
  ruleset_version?: string;
  created_at?: string | null;
}

export function listCases() {
  return apiJson<CaseSummary[]>('/api/v1/cases?limit=50');
}

export interface CaseDetail extends CaseSummary {
  organization_id?: string;
  validation_status?: string;
  address_provider?: string;
  address_provider_version?: string;
  address_provider_coverage?: string;
  input_hash?: string;
  output_hash?: string;
  disclaimer?: string;
  profile_id?: string;
  integration_profile_version?: string;
  mapping_version?: string;
  ruleset_version?: string;
  engine_version?: string;
  findings?: { rule_id: string; severity: string; target?: string | null; message?: string | null }[];
  audit?: { timestamp?: string | null; actor?: string | null; event: string }[];
}

export function getCase(caseId: string) {
  return apiJson<CaseDetail>(`/api/v1/cases/${caseId}`);
}

export function caseAction(caseId: string, action: string, note?: string, operator?: string) {
  return apiJson<{ case_id: string; status: string }>(`/api/v1/cases/${caseId}/actions`, {
    method: 'POST',
    body: JSON.stringify({ action, note, operator }),
  });
}

export interface BatchJobSummary {
  job_id: string;
  profile_id: string;
  profile_version: number;
  status: string;
  total_records: number;
  processed_records: number;
  ready_count: number;
  repairable_count: number;
  review_required_count: number;
  unresolved_count: number;
  failed_count: number;
  report?: Record<string, unknown> | null;
  created_at?: string;
  completed_at?: string;
}

export function listBatches() {
  return apiJson<BatchJobSummary[]>('/api/v1/batches');
}

export function getBatch(jobId: string) {
  return apiJson<BatchJobSummary>(`/api/v1/batches/${jobId}`);
}

export function createBatch(profileId: string, csv: string, profileVersion = 1) {
  return apiJson<{ job_id: string; status: string; accepted: boolean }>('/api/v1/batches', {
    method: 'POST',
    body: JSON.stringify({ profile_id: profileId, csv, profile_version: profileVersion }),
  });
}

export interface DashboardMetrics {
  investigations?: {
    total: number;
    running: number;
    prepared: number;
    completed: number;
    failed: number;
    uploads: number;
    samples: number;
    sandbox_tests: number;
    sandbox_validated: number;
    review_required: number;
    repair_rejected: number;
  };
  analyzed: number;
  ready: number;
  repairable: number;
  review_required: number;
  unresolved: number;
  open_cases: number;
  running_batches: number;
  top_findings: Record<string, number>;
  account_entries?: number;
  account_reconciled?: number;
  missing_account_event?: number;
  account_mismatches?: number;
  unmatched_entries?: number;
  duplicate_entries?: number;
  reconciliation_rate?: number;
}

export function getDashboard() {
  return apiJson<DashboardMetrics>('/api/v1/dashboard');
}

// ---------------------------------------------------------------- profiles (full)

export interface MappingField {
  source: string;
  target: string;
  required?: string;
  transforms?: string[];
  default?: string | null;
}

export interface ProfileDetail extends Profile {
  description?: string;
  output_format?: string;
  retention_policy?: string;
  address_policy?: string;
  ai_policy?: string;
  allowed_messages?: string[];
  version_number?: number;
  created_at?: string;
  updated_at?: string;
  published_at?: string | null;
  mapping?: {
    mapping_version: string;
    source_format: string;
    record_selector?: string | null;
    fields: MappingField[];
  };
  rules?: { rule_id: string; severity?: string; field?: string; description?: string }[];
}

export function getProfile(id: string) {
  return apiJson<ProfileDetail>(`/api/v1/integration-profiles/${id}`);
}

export function getProfileVersions(id: string) {
  return apiJson<{ version_number: number; name: string; input_format: string; mapping_version: string; ruleset_version: string; published_at: string }[]>(
    `/api/v1/integration-profiles/${id}/versions`,
  );
}

export function validateProfile(id: string) {
  return apiJson<{ valid: boolean; errors?: { code: string; message: string }[] }>(
    `/api/v1/integration-profiles/${id}/validate`,
    { method: 'POST' },
  );
}

export function testProfile(id: string, payload: string) {
  return apiJson<Record<string, unknown>>(`/api/v1/integration-profiles/${id}/test`, {
    method: 'POST',
    body: JSON.stringify({ payload }),
  });
}

// ---------------------------------------------------------------- audit

export interface AuditEvent {
  id: string;
  timestamp?: string | null;
  actor?: string | null;
  event: string;
  resource?: string | null;
  case_id?: string | null;
  profile_version?: string | null;
  result?: string | null;
}

export function listAuditEvents(params: { limit?: number; case_id?: string } = {}) {
  const q = new URLSearchParams();
  if (params.limit) q.set('limit', String(params.limit));
  if (params.case_id) q.set('case_id', params.case_id);
  return apiJson<AuditEvent[]>(`/api/v1/audit?${q.toString()}`);
}

// ---------------------------------------------------------------- api clients

export interface ApiClientSummary {
  client_id: string;
  organization_id: string;
  allowed_profiles: string[];
  status: string;
  created_at?: string | null;
  last_used_at?: string | null;
}

export function listApiClients() {
  return apiJson<ApiClientSummary[]>('/api/v1/clients');
}

export function createApiClient(organizationId: string, allowedProfiles: string[] = []) {
  return apiJson<{ client_id: string; secret: string; organization_id: string }>('/api/v1/clients', {
    method: 'POST',
    body: JSON.stringify({ organization_id: organizationId, allowed_profiles: allowedProfiles }),
  });
}

// ---------------------------------------------------------------- lifecycles (list)

export function analyzeProfile(profileId: string, payload: string, opts: { repair?: boolean; idempotencyKey?: string } = {}) {
  return apiJson<Record<string, unknown>>(`/api/v1/integrations/${profileId}/analyze`, {
    method: 'POST',
    body: JSON.stringify({ payload, repair: opts.repair ?? true, idempotency_key: opts.idempotencyKey }),
  });
}

// ---------------------------------------------------------------- Matching / reconciliation

export interface MatchRecord {
  record_id: string;
  record_type: string;
  organization_id: string;
  profile_id?: string | null;
  source_system?: string | null;
  message_type?: string | null;
  instruction_id?: string | null;
  end_to_end_id?: string | null;
  transaction_id?: string | null;
  amount?: number | string | null;
  currency?: string | null;
  booking_date?: string | null;
  value_date?: string | null;
  debtor_name?: string | null;
  creditor_name?: string | null;
  debtor_account?: string | null;
  creditor_account?: string | null;
  debtor_agent?: string | null;
  creditor_agent?: string | null;
  remittance_reference?: string | null;
  external_reference?: string | null;
  country?: string | null;
  source_hash?: string | null;
  metadata?: Record<string, unknown>;
}

export interface FieldMatchResult {
  field: string;
  comparison_type: string;
  original_a?: unknown;
  original_b?: unknown;
  normalized_a?: unknown;
  normalized_b?: unknown;
  similarity: number;
  weight: number;
  critical: boolean;
  status: string;
  explanation_code?: string | null;
}

export interface CriticalConflict {
  code: string;
  field: string;
  detail: string;
}

export interface MatchDecision {
  record_a_id: string;
  record_b_id: string;
  classification: string;
  match_score: number;
  critical_conflicts: CriticalConflict[];
  field_results: FieldMatchResult[];
  explanation_codes: string[];
  policy_version?: string | null;
  engine_version?: string | null;
}

export interface CandidateMatch {
  candidate_id: string;
  match_score: number;
  classification: string;
  top_evidence: FieldMatchResult[];
  critical_conflicts: CriticalConflict[];
}

export interface MatchCandidate {
  candidate_id: string;
  source_record_id: string;
  candidate_record_id: string;
  match_score: number;
  classification: string;
  critical_conflicts: CriticalConflict[];
  field_results?: FieldMatchResult[];
  status: string;
  operator?: string | null;
  note?: string | null;
}

export interface ReconciliationRun {
  run_id: string;
  run_type: string;
  status: string;
  policy_version?: string | null;
  total: number;
  matched: number;
  possible_match: number;
  review_required: number;
  unmatched: number;
  duplicate_candidate: number;
  failed: number;
  report?: Record<string, unknown> | null;
  created_at?: string | null;
  completed_at?: string | null;
  candidates?: MatchCandidate[];
}

export function createMatchRecord(record: MatchRecord) {
  return apiJson<{ record_id: string }>('/api/v1/matching/records', { method: 'POST', body: JSON.stringify({ record }) });
}

export function listMatchRecords() {
  return apiJson<MatchRecord[]>('/api/v1/matching/records');
}

export function evaluateMatch(body: { record_a?: MatchRecord; record_b?: MatchRecord; record_a_id?: string; record_b_id?: string; policy_id?: string }) {
  return apiJson<MatchDecision>('/api/v1/matching/evaluate', { method: 'POST', body: JSON.stringify(body) });
}

export function searchCandidates(source: MatchRecord, policy_id?: string, max_candidates = 20) {
  return apiJson<CandidateMatch[]>('/api/v1/matching/candidates', {
    method: 'POST',
    body: JSON.stringify({ source, policy_id, max_candidates }),
  });
}

export function createReconciliation(body: { source_records: MatchRecord[]; candidate_records: MatchRecord[]; policy_id?: string }) {
  return apiJson<{ run_id: string; status: string }>('/api/v1/matching/reconciliations', { method: 'POST', body: JSON.stringify(body) });
}

export function listReconciliations() {
  return apiJson<ReconciliationRun[]>('/api/v1/matching/reconciliations');
}

export function getReconciliation(runId: string) {
  return apiJson<ReconciliationRun>(`/api/v1/matching/reconciliations/${runId}`);
}

export function getReconciliationReport(runId: string) {
  return fetch(`${API_BASE}/api/v1/matching/reconciliations/${runId}/report`, { headers: authHeaders() })
    .then((res) => {
      if (res.status === 401) {
        redirectToLogin();
        throw new ApiError('Your session has expired. Please sign in again.', 401);
      }
      return res.ok ? res.text() : Promise.reject(new Error(`Report failed (${res.status})`));
    });
}

export function decideCandidate(candidateId: string, action: string, note?: string, operator?: string) {
  return apiJson<{ candidate_id: string; status: string; action: string }>(`/api/v1/matching/candidates/${candidateId}/decide`, {
    method: 'POST',
    body: JSON.stringify({ action, note, operator }),
  });
}

// ---------------------------------------------------------------- ISO / lifecycle

export interface IsoAnalysisResult {
  case_id: string;
  message_family?: string | null;
  message_definition?: string | null;
  message_version?: string | null;
  namespace?: string | null;
  message_id?: string | null;
  adapter_version?: string | null;
  schema_validation: boolean;
  schema_version?: string | null;
  original_validation_status: string;
  schema_issues?: { code: string; severity: string; path?: string | null; message: string }[];
  rule_findings?: Record<string, unknown>[];
  address_analyses?: { party?: string | null; readiness?: string | null; evidence_level?: string | null; country_code?: string | null; town_name?: string | null }[];
  address_readiness?: string | null;
  address_provider_coverage?: string | null;
  repair_status?: string | null;
  canonical_model_version?: string | null;
  engine_version?: string | null;
  input_hash?: string | null;
  lifecycle_id?: string | null;
  correlation_status?: string | null;
  correlation_evidence?: string[];
  correlation_conflicts?: string[];
  lifecycle_events?: Record<string, unknown>[];
  raw_status?: string | null;
  normalized_status?: string | null;
  account_report_type?: string | null;
  account_report_ids?: string[];
  account_entry_count?: number;
  account_reconciliation?: Record<string, unknown>[];
  warnings?: string[];
}

export interface IsoMessage {
  id: string;
  message_id?: string | null;
  message_family: string;
  message_definition: string;
  message_version: string;
  namespace: string;
  schema_validation: boolean;
  status: string;
  raw_status?: string | null;
  normalized_status?: string | null;
  created_at?: string | null;
}

export interface Lifecycle {
  lifecycle_id: string;
  organization_id: string;
  primary_reference?: string | null;
  end_to_end_id?: string | null;
  instruction_id?: string | null;
  transaction_id?: string | null;
  original_message_id?: string | null;
  amount_minor?: number | null;
  currency?: string | null;
  current_status: string;
  created_at?: string | null;
  updated_at?: string | null;
  events?: LifecycleEvent[];
  correlations?: Correlation[];
}

export interface LifecycleEvent {
  id: string;
  event_type: string;
  message_family?: string | null;
  message_definition?: string | null;
  message_version?: string | null;
  message_id?: string | null;
  timestamp?: string | null;
  status: string;
  raw_status_code?: string | null;
  reasons?: Record<string, unknown>[];
  correlation_evidence?: string[];
}

export interface Correlation {
  id: string;
  source_message_id?: string | null;
  candidate_message_id?: string | null;
  correlation_status: string;
  evidence: string[];
  conflicts: string[];
  operator?: string | null;
  note?: string | null;
}

export function analyzeIso(xml: string) {
  return apiJson<IsoAnalysisResult>('/api/v1/iso/analyze', { method: 'POST', body: JSON.stringify({ xml }) });
}

export function listIsoMessages(params: { family?: string; definition?: string; version?: string; status?: string } = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v) q.set(k, v); });
  return apiJson<IsoMessage[]>(`/api/v1/iso/messages?${q.toString()}`);
}

export function getIsoMessage(id: string) {
  return apiJson<IsoMessage>(`/api/v1/iso/messages/${id}`);
}

export function listLifecycles() {
  return apiJson<Lifecycle[]>('/api/v1/lifecycles');
}

export function getLifecycle(id: string) {
  return apiJson<Lifecycle>(`/api/v1/lifecycles/${id}`);
}

export function decideCorrelation(lifecycleId: string, correlationId: string, action: string, note?: string, operator?: string) {
  return apiJson<{ correlation_id: string; status: string; action: string }>(
    `/api/v1/lifecycles/${lifecycleId}/correlations/${correlationId}/decide`,
    { method: 'POST', body: JSON.stringify({ action, note, operator }) },
  );
}

// ---------------------------------------------------------------- Account reporting (camt)

export interface AccountBalance {
  balance_type: string;
  amount_minor: number;
  currency: string;
  credit_debit: string;
}

export interface AccountEntry {
  id: string;
  report_id: string;
  entry_reference?: string | null;
  account_servicer_reference?: string | null;
  transaction_id?: string | null;
  instruction_id?: string | null;
  end_to_end_id?: string | null;
  uetr?: string | null;
  amount_minor?: number | null;
  currency?: string | null;
  credit_debit?: string | null;
  booking_date?: string | null;
  value_date?: string | null;
  status?: string | null;
  bank_tx_code?: string | null;
  bank_tx_family?: string | null;
  bank_tx_sub_family?: string | null;
  remittance_reference?: string | null;
  reconciliation_status?: string | null;
  match_score?: number | null;
  lifecycle_id?: string | null;
  evidence?: string[];
  conflicts?: string[];
  created_at?: string | null;
}

export interface AccountReport {
  id: string;
  message_id?: string | null;
  message_definition: string;
  message_version: string;
  report_type: string;
  account_iban?: string | null;
  account_currency?: string | null;
  statement_id?: string | null;
  notification_id?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  entry_count: number;
  created_at?: string | null;
  balances?: AccountBalance[];
  entries?: AccountEntry[];
  reconciliation_summary?: Record<string, number>;
}

export interface AccountReconciliation {
  id: string;
  account_entry_id: string;
  lifecycle_id?: string | null;
  classification: string;
  match_score: number;
  evidence: string[];
  conflicts: string[];
  status: string;
  operator?: string | null;
  note?: string | null;
  created_at?: string | null;
}

export function listAccountReports(params: { report_type?: string; account?: string } = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v) q.set(k, v); });
  return apiJson<AccountReport[]>(`/api/v1/account-reports?${q.toString()}`);
}

export function getAccountReport(id: string) {
  return apiJson<AccountReport>(`/api/v1/account-reports/${id}`);
}

export function listAccountEntries(params: { report_id?: string; credit_debit?: string; reconciliation_status?: string } = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v) q.set(k, v); });
  return apiJson<AccountEntry[]>(`/api/v1/account-entries?${q.toString()}`);
}

export function getAccountEntry(id: string) {
  return apiJson<AccountEntry>(`/api/v1/account-entries/${id}`);
}

export function listAccountReconciliations() {
  return apiJson<AccountReconciliation[]>('/api/v1/account-reconciliations');
}

export function decideAccountReconciliation(id: string, action: string, note?: string, operator?: string) {
  return apiJson<{ reconciliation_id: string; status: string; action: string }>(
    `/api/v1/account-reconciliations/${id}/decide`,
    { method: 'POST', body: JSON.stringify({ action, note, operator }) },
  );
}

export function runAccountReconciliation(windowHours = 48) {
  return apiJson<{ missing_account_events: string[]; count: number }>('/api/v1/account-reconciliation/run', {
    method: 'POST',
    body: JSON.stringify({ window_hours: windowHours }),
  });
}

async function safeJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export function getInfo() {
  return safeJson<PlatformInfo>('/api/v1/info');
}

export function getHealth() {
  return safeJson<HealthResult>('/health');
}

export function getReadiness() {
  return safeJson<ReadinessResult>('/ready');
}

export interface AnalyzeResponse {
  case_id: string;
  message_type: string | null;
  message_version: string | null;
  original_validation_status: string;
  schema_issues: { code: string; severity: string; path: string | null; message: string }[];
  rule_findings: { rule_id: string; severity: string; message: string; target: string }[];
  address_analyses: {
    party: string | null;
    readiness: string | null;
    evidence_level: string | null;
    country_code: string | null;
    town_name: string | null;
  }[];
  address_readiness: string | null;
  repair_status: string | null;
  candidate_diff: { path: string; before: string | null; after: string | null; source: string; status: string }[];
  candidate_validation_status: string | null;
  candidate_xml: string | null;
  ruleset_version: string | null;
  address_provider: string | null;
  input_hash: string | null;
  output_hash: string | null;
  warnings: string[];
}

export async function analyzePayment(
  xml: string,
  opts: { repair?: boolean; persist?: boolean; includeCandidateXml?: boolean } = {},
): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/api/v1/payments/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({
      xml,
      repair: opts.repair ?? true,
      persist: opts.persist ?? false,
      include_candidate_xml: opts.includeCandidateXml ?? false,
    }),
  });
  const body = await res.json();
  if (!res.ok) {
    throw new Error(body?.error?.message ?? `Request failed (${res.status})`);
  }
  return body as AnalyzeResponse;
}

export interface SupportingRecordEntry {
  ref: string;
  party: string;
  field: string;
  value: string;
  note?: string;
}

export interface SupportingRecord {
  record_id: string;
  label: string;
  source: string;
  synthetic: boolean;
  entries: SupportingRecordEntry[];
  gaps: string[];
  contradictions: string[];
}

export interface ProposedChange {
  target: string;
  value: string;
  evidence_ref: string;
}

export interface ValidatedChange extends ProposedChange {
  party?: string;
  field?: string;
  path?: string;
  before?: string | null;
  after?: string | null;
  noop?: boolean;
  reason?: string;
}

export interface RejectedChange {
  target: string;
  value: string;
  evidence_ref?: string;
  reason: string;
}

export interface RepairTest {
  sandbox_id: string;
  original_hash: string;
  sandbox_hash: string;
  applied_changes: ValidatedChange[];
  before_findings: InvestigationFinding[];
  after_findings: InvestigationFinding[];
  remaining_issues: InvestigationFinding[];
  unresolved_findings?: { rule_id: string; target: string }[];
  xsd_valid: boolean;
  review_status: string;
  revalidated_by?: string | null;
  ruleset_version?: string | null;
  tested_at?: string | null;
  disclaimer?: string | null;
}

export interface Repair {
  status?: string | null;
  proposal?: {
    status?: string;
    error?: string | null;
    changes?: ProposedChange[];
    server_validation?: { allowed: ValidatedChange[]; rejected: RejectedChange[] } | null;
    missing_evidence?: string[];
    recommended_next_step?: string | null;
  } | null;
  validated_changes?: ValidatedChange[];
  rejected_changes?: RejectedChange[];
  test?: RepairTest | null;
}

// ---------------------------------------------------------------- Investigations (Phase 1)

export interface DemoCase {
  key: string;
  name: string;
  message_version: string;
  description: string;
  origin: string;
}

export interface InvestigationSummary {
  investigation_id: string;
  demo_case_key: string;
  message_version: string;
  status: string;
  agent_status?: string | null;
  validation_status?: string | null;
  rule_count: number;
  ruleset_version?: string | null;
  engine_version?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  error?: string | null;
}

export interface InvestigationFinding {
  rule_id: string;
  ruleset_version?: string;
  severity: string;
  target?: string | null;
  message?: string | null;
  evidence?: string[];
  suggested_action?: string | null;
}

export interface AgentResult {
  explanation?: string | null;
  cited_rules?: string[];
  missing_evidence?: string[];
  missing_evidence_present?: boolean;
  missing_evidence_provenance?: string;
  recommended_next_step?: string | null;
  output_text?: string | null;
  agent_rule_mentions?: string[];
  engine_rule_ids?: string[];
  agreement_rules?: string[];
  answer_separation_reliable?: boolean;
  reasoning_inline_excerpt?: string | null;
  raw?: Record<string, unknown>;
}

export interface ServerDerivedGap {
  gap: string;
  provenance: string;
  rule_id: string;
  party: string;
}

export interface MergedEvidenceGap {
  gap: string;
  provenance: string[];
}

export interface EvidenceGaps {
  supporting_record: string[];
  server_derived: ServerDerivedGap[];
  agent_reported: string[];
  agent_reported_status: 'PROVIDED' | 'NOT_SUPPLIED';
  conflicts: string[];
  merged: MergedEvidenceGap[];
}

export interface InvestigationDetail extends InvestigationSummary {
  source?: string;
  input_label?: string;
  case_origin?: string;
  input_hash: string;
  evidence_hash?: string | null;
  profile_version?: string | null;
  evolus_execution_id?: string | null;
  evolus_trace_id?: string | null;
  deterministic_findings?: {
    message_version?: string | null;
    original_validation_status?: string | null;
    schema_validation?: boolean;
    schema_issues?: { code: string; severity: string; path?: string | null; message: string }[];
    rule_findings?: InvestigationFinding[];
    address_readiness?: string | null;
    engine_version?: string | null;
    ruleset_version?: string | null;
  } | null;
  agent_result?: AgentResult | null;
  answer_text?: string | null;
  supporting_record?: SupportingRecord | null;
  evidence_gaps?: EvidenceGaps | null;
  repair?: Repair | null;
  synthetic_input?: string | null;
  disclaimer?: string;
}

export function listDemoCases() {
  return apiJson<DemoCase[]>('/api/v1/investigations/demo-cases');
}

export function listInvestigations() {
  return apiJson<InvestigationSummary[]>('/api/v1/investigations?limit=50');
}

export function getInvestigation(investigationId: string) {
  return apiJson<InvestigationDetail>(`/api/v1/investigations/${encodeURIComponent(investigationId)}`);
}

export function startInvestigation(demoCaseKey: string, startWorkflow = true) {
  return apiJson<InvestigationDetail>('/api/v1/investigations', {
    method: 'POST',
    body: JSON.stringify({ demo_case_key: demoCaseKey, start_workflow: startWorkflow }),
  });
}

export function testRepair(investigationId: string) {
  return apiJson<InvestigationDetail>(
    `/api/v1/investigations/${encodeURIComponent(investigationId)}/repair/test`,
    { method: 'POST' },
  );
}

export function uploadInvestigation(
  xml: string,
  evidence: Record<string, unknown> | null,
  startWorkflow = true,
) {
  return apiJson<InvestigationDetail>('/api/v1/investigations/upload', {
    method: 'POST',
    body: JSON.stringify({ xml, evidence, start_workflow: startWorkflow }),
  });
}

// ---------------------------------------------------------------- Batch Exception Desk (Phase 3A)

export interface ExceptionBatchItemInput {
  xml: string;
  evidence: Record<string, unknown> | null;
  filename?: string | null;
}

export interface ExceptionBatchItem {
  item_id: string;
  item_index: number;
  display_filename?: string | null;
  status: string;
  error?: string | null;
  input_hash: string;
  evidence_hash?: string | null;
  investigation_id?: string | null;
  evolus_execution_id?: string | null;
  investigation_status?: string | null;
  evidence_refs?: string[];
  original_findings?: InvestigationFinding[];
  repair_status?: string | null;
  proposed_changes?: ValidatedChange[];
  rejected_changes?: RejectedChange[];
  sandbox?: {
    sandbox_id?: string | null;
    original_hash?: string | null;
    sandbox_hash?: string | null;
    review_status?: string | null;
    xsd_valid?: boolean | null;
    before_findings?: InvestigationFinding[] | null;
    after_findings?: InvestigationFinding[] | null;
    applied_changes?: ValidatedChange[] | null;
    unresolved_findings?: { rule_id: string; target: string }[] | null;
    tested_at?: string | null;
  } | null;
  remaining_findings?: InvestigationFinding[] | null;
  unresolved_findings?: { rule_id: string; target: string }[] | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ExceptionBatchSummary {
  batch_id: string;
  status: string;
  total_items: number;
  counts: Record<string, number>;
  completed: number;
  failed: number;
  rejected: number;
  pending: number;
  created_at?: string | null;
  updated_at?: string | null;
  completed_at?: string | null;
}

export interface ExceptionBatchDetail extends ExceptionBatchSummary {
  items: ExceptionBatchItem[];
  disclaimer?: string;
}

export function createExceptionBatch(items: ExceptionBatchItemInput[], idempotencyKey?: string) {
  return apiJson<ExceptionBatchDetail>('/api/v1/exception-batches', {
    method: 'POST',
    body: JSON.stringify({ items, idempotency_key: idempotencyKey }),
  });
}

export function listExceptionBatches() {
  return apiJson<ExceptionBatchSummary[]>('/api/v1/exception-batches?limit=50');
}

export function getExceptionBatch(batchId: string) {
  return apiJson<ExceptionBatchDetail>(`/api/v1/exception-batches/${encodeURIComponent(batchId)}`);
}

export function testExceptionItemRepair(batchId: string, itemId: string) {
  return apiJson<ExceptionBatchDetail>(
    `/api/v1/exception-batches/${encodeURIComponent(batchId)}/items/${encodeURIComponent(itemId)}/repair/test`,
    { method: 'POST' },
  );
}

export function exportExceptionBatch(batchId: string) {
  return apiJson<Record<string, unknown>>(
    `/api/v1/exception-batches/${encodeURIComponent(batchId)}/export`,
  );
}
