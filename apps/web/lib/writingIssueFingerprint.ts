import type { WritingIssue } from "./grammarCheck";

/** Stable id for dismiss/apply persistence (survives offset changes on re-check). */
export function writingIssueFingerprint(issue: WritingIssue): string {
  const rule = issue.ruleId ?? "";
  const text = issue.matchedText.trim().toLowerCase();
  const msg = issue.shortMessage.trim().toLowerCase();
  return `${rule}|${text}|${msg}`;
}
