import { describe, expect, it } from 'vitest';
import { badgeClass, formatMinor, labelize, toneForStatus } from './status';

describe('status tone system', () => {
  it('maps positive terminal states to ok', () => {
    expect(toneForStatus('READY')).toBe('ok');
    expect(toneForStatus('RECONCILED')).toBe('ok');
    expect(toneForStatus('MATCHED')).toBe('ok');
    expect(toneForStatus('PUBLISHED')).toBe('ok');
  });

  it('maps attention states to warn', () => {
    expect(toneForStatus('REPAIRABLE')).toBe('warn');
    expect(toneForStatus('REVIEW_REQUIRED')).toBe('warn');
    expect(toneForStatus('POSSIBLE_MATCH')).toBe('warn');
    expect(toneForStatus('DUPLICATE_ACCOUNT_ENTRY')).toBe('warn');
  });

  it('maps negative states to danger', () => {
    expect(toneForStatus('UNRESOLVED')).toBe('danger');
    expect(toneForStatus('AMOUNT_MISMATCH')).toBe('danger');
    expect(toneForStatus('UNMATCHED_ACCOUNT_ENTRY')).toBe('danger');
    expect(toneForStatus('FAILED')).toBe('danger');
  });

  it('is case-insensitive and defaults unknown to muted', () => {
    expect(toneForStatus('ready')).toBe('ok');
    expect(toneForStatus('something-else')).toBe('muted');
    expect(toneForStatus(null)).toBe('muted');
    expect(toneForStatus(undefined)).toBe('muted');
  });

  it('builds a badge class from status', () => {
    expect(badgeClass('RECONCILED')).toBe('badge badge-ok');
    expect(badgeClass('AMOUNT_MISMATCH')).toBe('badge badge-danger');
  });
});

describe('formatting helpers', () => {
  it('formats minor units with currency', () => {
    expect(formatMinor(1250000, 'EUR')).toBe('12,500.00 EUR');
    expect(formatMinor(null, 'EUR')).toBe('—');
  });

  it('labelizes snake_case statuses', () => {
    expect(labelize('REVIEW_REQUIRED')).toBe('Review Required');
    expect(labelize('AMOUNT_MISMATCH')).toBe('Amount Mismatch');
    expect(labelize(null)).toBe('—');
  });
});
