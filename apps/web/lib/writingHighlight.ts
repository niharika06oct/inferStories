import type { TextSpan } from "./claimEvidenceSpan";
import type { WritingIssue } from "./grammarCheck";

export type HighlightSegment = {
  text: string;
  /** Grammar/spelling underline */
  issue: boolean;
  /** Focused story-memory claim */
  claimFocus: boolean;
};

type SpanRange = { start: number; end: number };

function overlaps(range: SpanRange, start: number, end: number): boolean {
  return range.start < end && range.end > start;
}

/** Split chapter text for grammar underlines and optional focused claim highlight. */
export function buildEditorHighlightSegments(
  text: string,
  issues: WritingIssue[],
  claimFocus: TextSpan | null = null,
): HighlightSegment[] {
  if (!text) return [];

  const grammarRanges: SpanRange[] = issues.map((issue) => ({
    start: Math.max(0, issue.offset),
    end: Math.min(text.length, issue.offset + issue.length),
  }));

  const claimRange =
    claimFocus && claimFocus.length > 0
      ? {
          start: Math.max(0, claimFocus.offset),
          end: Math.min(text.length, claimFocus.offset + claimFocus.length),
        }
      : null;

  if (grammarRanges.length === 0 && !claimRange) {
    return [{ text, issue: false, claimFocus: false }];
  }

  const boundaries = new Set<number>([0, text.length]);
  for (const r of grammarRanges) {
    boundaries.add(r.start);
    boundaries.add(r.end);
  }
  if (claimRange) {
    boundaries.add(claimRange.start);
    boundaries.add(claimRange.end);
  }

  const points = [...boundaries].sort((a, b) => a - b);
  const segments: HighlightSegment[] = [];

  for (let i = 0; i < points.length - 1; i += 1) {
    const start = points[i]!;
    const end = points[i + 1]!;
    if (end <= start) continue;
    const grammar = grammarRanges.some((r) => overlaps(r, start, end));
    const claim = claimRange ? overlaps(claimRange, start, end) : false;
    segments.push({
      text: text.slice(start, end),
      issue: grammar,
      claimFocus: claim,
    });
  }

  return segments;
}

/** @deprecated Use buildEditorHighlightSegments */
export function buildHighlightSegments(
  text: string,
  issues: WritingIssue[],
): HighlightSegment[] {
  return buildEditorHighlightSegments(text, issues, null);
}
