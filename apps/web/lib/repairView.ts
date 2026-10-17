// Pure view helpers for the investigation repair panel. Kept outside the page component so the
// "clean case" and "sandbox testable" decisions are unit-tested without the Next.js runtime.

export function isNoRepairNeeded(input: {
  status?: string | null;
  findingsCount: number;
  proposedCount: number;
}): boolean {
  // A clean message: the run completed, the engine raised no findings, and the investigator
  // proposed no changes. A message with findings but no proposal is NOT "no repair needed".
  return input.status === 'COMPLETED' && input.findingsCount === 0 && input.proposedCount === 0;
}

export function canTestSandbox(
  proposalStatus?: string | null,
  proposedCount = 0,
): boolean {
  // Sandbox testing requires a parsed proposal that actually contains a server-validated change.
  return proposalStatus === 'PROPOSED' && proposedCount > 0;
}
