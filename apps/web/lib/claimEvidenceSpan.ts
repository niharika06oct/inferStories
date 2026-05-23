import type { ClaimOut } from "./api";

export type TextSpan = { offset: number; length: number };

/** Locate the evidence quote (or subject name) inside chapter text. */
export function findClaimEvidenceSpan(
  chapterText: string,
  claim: Pick<ClaimOut, "evidence_text" | "subject" | "target">,
): TextSpan | null {
  const evidence = claim.evidence_text?.trim();
  if (evidence) {
    const fromEvidence = findSubstringSpan(chapterText, evidence);
    if (fromEvidence) return fromEvidence;
    if (evidence.length > 48) {
      const short = evidence.slice(0, 48).trim();
      const partial = findSubstringSpan(chapterText, short);
      if (partial) return partial;
    }
  }

  const subject = claim.subject?.trim();
  if (subject.length >= 2) {
    const subjSpan = findSubstringSpan(chapterText, subject);
    if (subjSpan) return subjSpan;
  }

  const target = claim.target?.trim();
  if (target && target.length >= 2) {
    return findSubstringSpan(chapterText, target);
  }

  return null;
}

function findSubstringSpan(text: string, needle: string): TextSpan | null {
  if (!needle) return null;
  let idx = text.indexOf(needle);
  if (idx < 0) {
    idx = text.toLowerCase().indexOf(needle.toLowerCase());
  }
  if (idx < 0) return null;
  return { offset: idx, length: needle.length };
}
