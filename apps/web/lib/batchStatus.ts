import type { ExceptionBatchItem } from './api';
import { labelize } from './status';

// Pure status-mapping helpers for the Batch Exception Desk. Kept outside the page component so
// they can be unit-tested without the Next.js runtime.

export const ACTIVE_BATCH_STATUSES = new Set(['PENDING', 'STARTING', 'RUNNING']);

export function isClean(item: ExceptionBatchItem): boolean {
  return (
    item.status === 'COMPLETED' &&
    item.investigation_status === 'COMPLETED' &&
    (item.original_findings ?? []).length === 0
  );
}

// A message is "evaluated" only when deterministic validation actually ran for it. Rejected
// uploads and items with no linked investigation were never evaluated, so their (absent) findings
// must never be presented as a passing "0 · none". Falls back to the linked-investigation check
// for payloads captured before the explicit `validation_performed` flag existed.
export function isEvaluated(item: ExceptionBatchItem): boolean {
  if (typeof item.validation_performed === 'boolean') return item.validation_performed;
  return item.investigation_id != null && item.investigation_status != null;
}

export function canTest(item: ExceptionBatchItem): boolean {
  return (
    item.investigation_status === 'COMPLETED' &&
    (item.proposed_changes ?? []).length > 0 &&
    (item.sandbox?.applied_changes ?? []).length === 0
  );
}

export function itemOutcomeLabel(item: ExceptionBatchItem): { text: string; tone: string } {
  if (item.status === 'REJECTED') return { text: 'Rejected at upload', tone: 'REJECTED' };
  if (item.status === 'FAILED') return { text: 'Failed', tone: 'FAILED' };
  if (isClean(item)) return { text: 'No repair needed', tone: 'COMPLETED' };
  if (item.sandbox?.review_status)
    return { text: `Sandbox: ${labelize(item.sandbox.review_status)}`, tone: item.sandbox.review_status };
  if ((item.unresolved_findings ?? []).length > 0)
    return { text: 'Incomplete evidence — unresolved', tone: 'REVIEW_REQUIRED' };
  if (ACTIVE_BATCH_STATUSES.has(item.status)) return { text: 'In progress', tone: item.status };
  return { text: labelize(item.status), tone: item.status };
}
