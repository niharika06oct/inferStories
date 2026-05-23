import type { WritingIssue } from "./grammarCheck";

export function applyTextReplacement(
  text: string,
  offset: number,
  length: number,
  replacement: string,
): string {
  const start = Math.max(0, Math.min(offset, text.length));
  const end = Math.max(start, Math.min(start + length, text.length));
  return text.slice(0, start) + replacement + text.slice(end);
}

/** Remove applied issue and shift later issues after the text length change. */
export function issuesAfterApply(
  issues: WritingIssue[],
  applied: WritingIssue,
  replacement: string,
): WritingIssue[] {
  const start = applied.offset;
  const end = applied.offset + applied.length;
  const delta = replacement.length - applied.length;

  return issues
    .filter((issue) => {
      if (
        issue.offset === applied.offset &&
        issue.length === applied.length &&
        issue.shortMessage === applied.shortMessage
      ) {
        return false;
      }
      const issueEnd = issue.offset + issue.length;
      if (issue.offset < end && issueEnd > start) return false;
      return true;
    })
    .map((issue) => {
      if (issue.offset >= end) {
        return { ...issue, offset: issue.offset + delta };
      }
      return issue;
    });
}

export function issueKey(issue: WritingIssue): string {
  return `${issue.offset}:${issue.length}:${issue.shortMessage}`;
}

/** Issue whose span contains `offset` (smallest span wins on overlap). */
export function findIssueAtOffset(
  issues: WritingIssue[],
  offset: number,
): WritingIssue | null {
  const matches = issues.filter(
    (issue) =>
      offset >= issue.offset && offset < issue.offset + issue.length,
  );
  if (matches.length === 0) return null;
  return matches.sort((a, b) => a.length - b.length)[0] ?? null;
}
