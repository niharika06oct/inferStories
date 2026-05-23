import type { WritingIssue } from "./grammarCheck";
import { writingIssueFingerprint } from "./writingIssueFingerprint";

const PREFIX = "inferstories:writing-dismissed:";

function key(storyId: number, sceneId: number | null): string {
  const scene = sceneId != null ? String(sceneId) : "draft";
  return `${PREFIX}${storyId}:${scene}`;
}

export function loadDismissedWritingFingerprints(
  storyId: number,
  sceneId: number | null,
): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(key(storyId, sceneId));
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((x): x is string => typeof x === "string"));
  } catch {
    return new Set();
  }
}

export function saveDismissedWritingFingerprints(
  storyId: number,
  sceneId: number | null,
  fingerprints: Set<string>,
): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(
    key(storyId, sceneId),
    JSON.stringify([...fingerprints]),
  );
}

export function rememberDismissedWritingIssue(
  storyId: number,
  sceneId: number | null,
  fingerprint: string,
): void {
  const set = loadDismissedWritingFingerprints(storyId, sceneId);
  set.add(fingerprint);
  saveDismissedWritingFingerprints(storyId, sceneId, set);
}

export function filterDismissedWritingIssues(
  issues: WritingIssue[],
  dismissed: Set<string>,
): WritingIssue[] {
  return issues.filter((i) => !dismissed.has(writingIssueFingerprint(i)));
}
