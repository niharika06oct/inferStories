import type { WritingIssue } from "./grammarCheck";

/** Single contiguous edit between two text snapshots. */
export function findEditSpan(
  prevText: string,
  nextText: string,
): { start: number; prevEnd: number; nextEnd: number } {
  let start = 0;
  const minLen = Math.min(prevText.length, nextText.length);
  while (start < minLen && prevText[start] === nextText[start]) start += 1;

  let prevEnd = prevText.length;
  let nextEnd = nextText.length;
  while (
    prevEnd > start &&
    nextEnd > start &&
    prevText[prevEnd - 1] === nextText[nextEnd - 1]
  ) {
    prevEnd -= 1;
    nextEnd -= 1;
  }

  return { start, prevEnd, nextEnd };
}

function textAtIssue(text: string, issue: WritingIssue): string {
  return text.slice(issue.offset, issue.offset + issue.length);
}

/** Drop issue if flagged text no longer matches at its offset. */
export function validateWritingIssue(
  text: string,
  issue: WritingIssue,
): WritingIssue | null {
  const atOffset = textAtIssue(text, issue);
  if (!atOffset) return null;
  const expected = issue.matchedText || atOffset;
  if (atOffset !== expected) return null;
  return issue;
}

/**
 * After a manual edit, keep issues that still apply; remove only those
 * touched by the edit or whose flagged span no longer matches.
 */
export function reconcileWritingIssuesAfterEdit(
  prevText: string,
  nextText: string,
  issues: WritingIssue[],
): WritingIssue[] {
  if (prevText === nextText) return issues;
  if (!issues.length) return issues;

  const { start, prevEnd, nextEnd } = findEditSpan(prevText, nextText);
  const delta = nextEnd - start - (prevEnd - start);

  const next: WritingIssue[] = [];
  for (const issue of issues) {
    const issueEnd = issue.offset + issue.length;

    if (issueEnd <= start) {
      const valid = validateWritingIssue(nextText, issue);
      if (valid) next.push(valid);
      continue;
    }

    if (issue.offset >= prevEnd) {
      const shifted = { ...issue, offset: issue.offset + delta };
      const valid = validateWritingIssue(nextText, shifted);
      if (valid) next.push(valid);
      continue;
    }

    // Span overlaps the edited region — user changed that text; drop this issue.
  }

  return next;
}
