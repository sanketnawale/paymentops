import { describe, expect, it } from 'vitest';
import { canTestSandbox, isNoRepairNeeded } from './repairView';

describe('investigation repair view', () => {
  it('flags a clean, completed message as needing no repair', () => {
    expect(isNoRepairNeeded({ status: 'COMPLETED', findingsCount: 0, proposedCount: 0 })).toBe(true);
  });

  it('does not flag a message whose engine still has findings', () => {
    // Unresolved findings with no proposal must remain distinguishable from a clean case.
    expect(isNoRepairNeeded({ status: 'COMPLETED', findingsCount: 2, proposedCount: 0 })).toBe(false);
  });

  it('does not flag a message with a proposed change', () => {
    expect(isNoRepairNeeded({ status: 'COMPLETED', findingsCount: 2, proposedCount: 1 })).toBe(false);
  });

  it('does not flag an incomplete run', () => {
    expect(isNoRepairNeeded({ status: 'RUNNING', findingsCount: 0, proposedCount: 0 })).toBe(false);
  });

  it('only allows sandbox testing for a proposal with a change', () => {
    expect(canTestSandbox('PROPOSED', 2)).toBe(true);
    expect(canTestSandbox('PROPOSED', 0)).toBe(false);
    expect(canTestSandbox('PROPOSAL_UNPARSEABLE', 0)).toBe(false);
    expect(canTestSandbox(null, 0)).toBe(false);
    expect(canTestSandbox(undefined)).toBe(false);
  });
});
