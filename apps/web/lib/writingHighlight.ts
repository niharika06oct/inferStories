import type { WritingIssue } from "./grammarCheck";

export type HighlightSegment = {
  text: string;
  issue: boolean;
};

/** Merge overlapping issue ranges and split text into plain vs highlighted segments. */
export function buildHighlightSegments(
  text: string,
  issues: WritingIssue[],
): HighlightSegment[] {
  if (!text) return [];
  if (!issues.length) return [{ text, issue: false }];

  const ranges: { start: number; end: number }[] = [];
  for (const issue of issues) {
    const start = Math.max(0, issue.offset);
    const end = Math.min(text.length, issue.offset + issue.length);
    if (end > start) ranges.push({ start, end });
  }
  ranges.sort((a, b) => a.start - b.start);

  const merged: { start: number; end: number }[] = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r.start <= last.end) {
      last.end = Math.max(last.end, r.end);
    } else {
      merged.push({ ...r });
    }
  }

  const segments: HighlightSegment[] = [];
  let cursor = 0;
  for (const { start, end } of merged) {
    if (start > cursor) {
      segments.push({ text: text.slice(cursor, start), issue: false });
    }
    segments.push({ text: text.slice(start, end), issue: true });
    cursor = end;
  }
  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), issue: false });
  }
  return segments;
}
