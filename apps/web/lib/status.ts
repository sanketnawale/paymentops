// Banking status → visual tone system. Single source of truth for status colors.
// Never scatter arbitrary status colors across components.

export type Tone = 'ok' | 'warn' | 'danger' | 'info' | 'muted';

const TONE_BY_STATUS: Record<string, Tone> = {
  // Success / positive terminal
  READY: 'ok',
  RECONCILED: 'ok',
  MATCHED: 'ok',
  PUBLISHED: 'ok',
  APPROVED: 'ok',
  COMPLETED: 'ok',
  ACCEPTED: 'ok',
  ACTIVE: 'ok',
  VALIDATED: 'ok',
  VALID: 'ok',

  // Attention / intermediate
  REPAIRABLE: 'warn',
  POSSIBLE_MATCH: 'warn',
  POSSIBLE_CORRELATION: 'warn',
  POSSIBLE_RECONCILIATION: 'warn',
  REVIEW_REQUIRED: 'warn',
  TESTING: 'info',
  PARTIAL: 'warn',
  PENDING: 'warn',
  DUPLICATE_CANDIDATE: 'warn',
  DUPLICATE_ACCOUNT_ENTRY: 'warn',
  MISSING_ACCOUNT_EVENT: 'warn',
  REPAIR_PROPOSED: 'warn',
  PENDING_REVIEW: 'warn',

  // Negative
  UNRESOLVED: 'danger',
  UNMATCHED: 'danger',
  UNMATCHED_ACCOUNT_ENTRY: 'danger',
  MISMATCH: 'danger',
  AMOUNT_MISMATCH: 'danger',
  CURRENCY_MISMATCH: 'danger',
  ACCOUNT_MISMATCH: 'danger',
  REFERENCE_MISMATCH: 'danger',
  FAILED: 'danger',
  REJECTED: 'danger',
  CONFLICT: 'danger',
  INVALID: 'danger',
  AMBIGUOUS: 'danger',
  SUSPENDED: 'danger',

  // Neutral / in-progress
  DRAFT: 'muted',
  ARCHIVED: 'muted',
  NEW: 'muted',
  QUEUED: 'muted',
  ANALYZED: 'info',
  CLOSED: 'muted',
  UNKNOWN: 'muted',
  RUNNING: 'info',
  PROCESSING: 'info',
  PARTIALLY_ACCEPTED: 'info',
  CORRELATED: 'ok',
  STATUS_RECEIVED: 'info',
  INITIATED: 'info',
  INTERBANK_TRANSFER: 'info',
  FI_TRANSFER: 'info',
  ACCOUNT_NOTIFICATION: 'info',
  ACCOUNT_STATEMENT_ENTRY: 'info',
  DEBIT_RECORDED: 'info',
  CREDIT_RECORDED: 'info',
  ACCOUNT_EVENT_CONFIRMED: 'ok',
  ACCOUNT_EVENT_UNRESOLVED: 'danger',
};

export function toneForStatus(status: string | null | undefined): Tone {
  if (!status) return 'muted';
  return TONE_BY_STATUS[status.toUpperCase()] ?? 'muted';
}

export function badgeClass(status: string | null | undefined): string {
  return `badge badge-${toneForStatus(status)}`;
}

export function labelize(value: string | null | undefined): string {
  if (!value) return '—';
  return value
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatMinor(amountMinor: number | null | undefined, currency?: string | null): string {
  if (amountMinor === null || amountMinor === undefined) return '—';
  const major = amountMinor / 100;
  return `${major.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${currency ? ` ${currency}` : ''}`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString();
}
