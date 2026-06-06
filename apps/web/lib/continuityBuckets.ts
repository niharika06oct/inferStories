import type { ValidationIssueOut } from "./api";

export type ContinuityResolutionStatus = "open" | "fixed" | "rejected";

export function continuityResolutionStatus(
  issue: ValidationIssueOut,
): ContinuityResolutionStatus {
  const s = issue.resolution_status ?? "open";
  if (s === "fixed" || s === "rejected") return s;
  return "open";
}

export function isOpenContinuityIssue(issue: ValidationIssueOut): boolean {
  return continuityResolutionStatus(issue) === "open";
}

export function isResolvedContinuityIssue(issue: ValidationIssueOut): boolean {
  return continuityResolutionStatus(issue) !== "open";
}

export function partitionContinuityIssues(issues: ValidationIssueOut[]): {
  open: ValidationIssueOut[];
  resolved: ValidationIssueOut[];
} {
  const open: ValidationIssueOut[] = [];
  const resolved: ValidationIssueOut[] = [];
  for (const issue of issues) {
    if (isOpenContinuityIssue(issue)) {
      open.push(issue);
    } else {
      resolved.push(issue);
    }
  }
  return { open, resolved };
}

export function continuityBucketCounts(issues: ValidationIssueOut[]): {
  open: number;
  resolved: number;
} {
  const { open, resolved } = partitionContinuityIssues(issues);
  return { open: open.length, resolved: resolved.length };
}
