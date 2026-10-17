import { describe, expect, it } from 'vitest';
import type { ExceptionBatchItem } from './api';
import { canTest, isClean, isEvaluated, itemOutcomeLabel } from './batchStatus';

function makeItem(overrides: Partial<ExceptionBatchItem>): ExceptionBatchItem {
  return {
    item_id: 'bit-test',
    item_index: 0,
    status: 'PENDING',
    input_hash: 'deadbeef',
    ...overrides,
  };
}

describe('batch item status mapping', () => {
  it('treats a rejected upload as not evaluated (never "0 · none")', () => {
    const rejected = makeItem({
      status: 'REJECTED',
      investigation_id: null,
      investigation_status: null,
      validation_performed: false,
      error: 'rejected (MalformedXmlError): XML could not be parsed',
    });
    expect(isEvaluated(rejected)).toBe(false);
    expect(isClean(rejected)).toBe(false);
    expect(itemOutcomeLabel(rejected).text).toBe('Rejected at upload');
  });

  it('treats a clean, evaluated message as evaluated with zero findings', () => {
    const clean = makeItem({
      status: 'COMPLETED',
      investigation_id: 'inv-clean',
      investigation_status: 'COMPLETED',
      validation_performed: true,
      original_findings: [],
    });
    expect(isEvaluated(clean)).toBe(true);
    expect(isClean(clean)).toBe(true);
    expect(itemOutcomeLabel(clean).text).toBe('No repair needed');
  });

  it('falls back to the linked investigation when validation_performed is absent', () => {
    expect(
      isEvaluated(
        makeItem({ investigation_id: 'inv-1', investigation_status: 'COMPLETED' }),
      ),
    ).toBe(true);
    expect(isEvaluated(makeItem({ investigation_id: null, investigation_status: null }))).toBe(
      false,
    );
  });

  it('maps sandbox and unresolved outcomes distinctly', () => {
    const reviewRequired = makeItem({
      status: 'COMPLETED',
      investigation_id: 'inv-2',
      investigation_status: 'COMPLETED',
      validation_performed: true,
      original_findings: [{ rule_id: 'ADR-001', severity: 'WARNING' }],
      sandbox: { review_status: 'REVIEW_REQUIRED' },
    });
    expect(itemOutcomeLabel(reviewRequired).text).toBe('Sandbox: Review Required');

    const validated = makeItem({
      status: 'COMPLETED',
      investigation_id: 'inv-3',
      investigation_status: 'COMPLETED',
      validation_performed: true,
      original_findings: [{ rule_id: 'ADR-001', severity: 'WARNING' }],
      sandbox: { review_status: 'VALIDATED' },
    });
    expect(itemOutcomeLabel(validated).text).toBe('Sandbox: Validated');
  });

  it('only offers a sandbox test for a completed item with proposals', () => {
    const testable = makeItem({
      status: 'COMPLETED',
      investigation_status: 'COMPLETED',
      proposed_changes: [{ target: 'Dbtr/PstlAdr/TwnNm', value: 'Milano', evidence_ref: 'SR-1' }],
      sandbox: null,
    });
    expect(canTest(testable)).toBe(true);

    const alreadyTested = makeItem({
      status: 'COMPLETED',
      investigation_status: 'COMPLETED',
      proposed_changes: [{ target: 'Dbtr/PstlAdr/TwnNm', value: 'Milano', evidence_ref: 'SR-1' }],
      sandbox: { applied_changes: [{ target: 'Dbtr/PstlAdr/TwnNm', value: 'Milano', evidence_ref: 'SR-1' }] },
    });
    expect(canTest(alreadyTested)).toBe(false);
  });
});
