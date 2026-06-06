import type { ClaimOut } from "./api";

export type TextSpan = { offset: number; length: number };

type ClaimAnchor = Pick<
  ClaimOut,
  | "id"
  | "subject"
  | "predicate"
  | "object"
  | "target"
  | "claim_text"
  | "evidence_text"
  | "status"
>;

/** Locate the evidence quote (or subject name) inside chapter text. */
export function findClaimEvidenceSpan(
  chapterText: string,
  claim: Pick<ClaimOut, "evidence_text" | "subject" | "target" | "object">,
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

  const object = claim.object?.trim();
  if (object && object.length >= 2) {
    return findSubstringSpan(chapterText, object);
  }

  return null;
}

type ContinuityAnchorIssue = {
  current_claim_id?: number | null;
  message?: string;
  anchor_text?: string | null;
  text_offset?: number;
  anchor_length?: number;
};

export function inferContinuityIssueClaim(
  issue: ContinuityAnchorIssue,
  claims: ClaimAnchor[],
): ClaimAnchor | undefined {
  if (issue.current_claim_id != null) {
    const byId = claims.find((claim) => claim.id === issue.current_claim_id);
    if (byId) return byId;
  }

  const message = issue.message ?? "";
  const now = normalizeForMatch(extractNowValue(message));
  const messageNorm = normalizeForMatch(message);

  let best: { claim: ClaimAnchor; score: number } | null = null;
  for (const claim of claims) {
    if (claim.status === "rejected" || claim.status === "deprecated") continue;

    let score = 0;
    const predicate = normalizeForMatch(claim.predicate);
    const object = normalizeForMatch(claim.object);
    const target = normalizeForMatch(claim.target ?? "");
    const subject = normalizeForMatch(claim.subject);

    if (now) {
      if (predicate && predicate === now) score += 90;
      else if (
        predicate &&
        (predicate.includes(now) || now.includes(predicate))
      ) {
        score += 45;
      }

      if (object === now || target === now) score += 90;
      else if (
        (object && (object.includes(now) || now.includes(object))) ||
        (target && (target.includes(now) || now.includes(target)))
      ) {
        score += 45;
      }
    }

    if (subject && messageNorm.includes(subject)) score += 20;
    if (object && messageNorm.includes(object)) score += 20;
    if (target && messageNorm.includes(target)) score += 20;
    if (claim.evidence_text?.trim()) score += 10;

    if (!best || score > best.score) {
      best = { claim, score };
    }
  }

  return best && best.score >= 50 ? best.claim : undefined;
}

/** Highlight target for a continuity issue (avoids subject-only match at chapter start). */
export function findContinuityAnchorSpan(
  chapterText: string,
  issue: ContinuityAnchorIssue,
  claim?: Partial<ClaimAnchor> | null,
): TextSpan | null {
  const preferredOffset = issue.text_offset ?? 0;
  const anchor = issue.anchor_text?.trim();

  if (anchor) {
    const hit = findSubstringSpan(chapterText, anchor, preferredOffset);
    if (hit) return hit;
    if (anchor.length > 24) {
      const partial = findSubstringSpan(
        chapterText,
        anchor.slice(0, 48).trim(),
        preferredOffset,
      );
      if (partial) return partial;
    }
  }

  const off = issue.text_offset ?? 0;
  const len =
    issue.anchor_length ?? (anchor ? Math.min(anchor.length, 200) : 0);
  if (
    len > 0 &&
    off >= 0 &&
    off < chapterText.length &&
    spanMatchesAnchor(chapterText, off, len, anchor)
  ) {
    return {
      offset: off,
      length: Math.max(1, Math.min(len, chapterText.length - off)),
    };
  }

  const evidence = claim?.evidence_text?.trim();
  if (evidence) {
    const fromEvidence = findSubstringSpan(
      chapterText,
      evidence,
      preferredOffset,
    );
    if (fromEvidence) return fromEvidence;
    if (evidence.length > 24) {
      const partial = findSubstringSpan(
        chapterText,
        evidence.slice(0, 72).trim(),
        preferredOffset,
      );
      if (partial) return partial;
    }
  }

  const claimText = claim?.claim_text?.trim();
  if (claimText) {
    const fromClaimText = findSubstringSpan(
      chapterText,
      claimText,
      preferredOffset,
    );
    if (fromClaimText) return fromClaimText;
    if (claimText.length > 24) {
      const partial = findSubstringSpan(
        chapterText,
        claimText.slice(0, 72).trim(),
        preferredOffset,
      );
      if (partial) return partial;
    }
  }

  const object = (claim?.target ?? claim?.object)?.trim();
  if (object && object.length >= 3) {
    const objectSentence = findSentenceContaining(
      chapterText,
      object,
      preferredOffset,
    );
    if (objectSentence) return objectSentence;
  }

  return null;
}

function extractNowValue(message: string): string {
  return message.match(/\bnow '([^']+)'/)?.[1] ?? "";
}

function normalizeForMatch(value: string | null | undefined): string {
  return (value ?? "").trim().toLowerCase().replace(/\s+/g, " ");
}

function spanMatchesAnchor(
  text: string,
  offset: number,
  length: number,
  anchor?: string,
): boolean {
  if (!anchor) {
    return offset > 0;
  }
  const sliceLen = Math.min(length, anchor.length, text.length - offset);
  if (sliceLen < 1) return false;
  const at = text.slice(offset, offset + sliceLen).toLowerCase();
  const expected = anchor.slice(0, sliceLen).toLowerCase();
  return at === expected;
}

function findSubstringSpan(
  text: string,
  needle: string,
  preferredOffset = 0,
): TextSpan | null {
  if (!needle) return null;
  const matches = findSubstringMatches(text, needle);
  if (matches.length === 0) return null;
  if (matches.length === 1) return matches[0]!;

  let best = matches[0]!;
  let bestDist = Math.abs(best.offset - preferredOffset);
  for (const match of matches) {
    const dist = Math.abs(match.offset - preferredOffset);
    if (dist < bestDist) {
      best = match;
      bestDist = dist;
    }
  }
  return best;
}

function findSubstringMatches(text: string, needle: string): TextSpan[] {
  const exact = findExactSubstringMatches(text, needle);
  if (exact.length > 0) return exact;

  const pattern = needle
    .trim()
    .split(/\s+/)
    .map(escapeRegExp)
    .join("\\s+");
  if (!pattern) return [];

  const matches: TextSpan[] = [];
  const regex = new RegExp(pattern, "gi");
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) != null) {
    matches.push({ offset: match.index, length: match[0].length });
    if (match.index === regex.lastIndex) regex.lastIndex += 1;
  }
  return matches;
}

function findExactSubstringMatches(text: string, needle: string): TextSpan[] {
  const needleLower = needle.toLowerCase();
  const textLower = text.toLowerCase();
  const matches: TextSpan[] = [];
  let searchFrom = 0;
  while (searchFrom < text.length) {
    const idx = textLower.indexOf(needleLower, searchFrom);
    if (idx < 0) break;
    matches.push({ offset: idx, length: needle.length });
    searchFrom = idx + 1;
  }
  return matches;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function findSentenceContaining(
  text: string,
  needle: string,
  preferredOffset = 0,
): TextSpan | null {
  const hit = findSubstringSpan(text, needle, preferredOffset);
  if (!hit) return null;

  const sentenceStart = Math.max(
    text.lastIndexOf(".", hit.offset - 1),
    text.lastIndexOf("!", hit.offset - 1),
    text.lastIndexOf("?", hit.offset - 1),
    text.lastIndexOf("\n", hit.offset - 1),
  );
  const after = text.slice(hit.offset + hit.length);
  const endings = [".", "!", "?", "\n"]
    .map((end) => after.indexOf(end))
    .filter((idx) => idx >= 0);
  const sentenceEnd =
    endings.length > 0
      ? hit.offset + hit.length + Math.min(...endings) + 1
      : Math.min(text.length, hit.offset + hit.length + 160);

  const start = Math.max(0, sentenceStart + 1);
  return {
    offset: start,
    length: Math.max(1, Math.min(sentenceEnd - start, 240)),
  };
}
