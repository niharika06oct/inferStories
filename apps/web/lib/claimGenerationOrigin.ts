/** Matches API `generation_origin` on claims. */
export type ClaimGenerationOrigin =
  | "structural"
  | "family"
  | "llm"
  | "llm_recall"
  | "fastus"
  | "heuristic"
  | "manual"
  | "unknown";

const LABELS: Record<string, string> = {
  structural: "Rules · pattern",
  family: "Rules · family",
  llm: "AI (LLM refine)",
  llm_recall: "AI · recall",
  fastus: "FASTUS grounded",
  heuristic: "Fallback",
  manual: "Manual",
  unknown: "Unknown",
};

export function labelForGenerationOrigin(origin: string | undefined): string {
  if (!origin) return LABELS.unknown;
  if (origin.includes("+")) {
    return origin
      .split("+")
      .map((part) => LABELS[part.trim()] ?? part.trim())
      .join(" + ");
  }
  return LABELS[origin] ?? origin;
}

export function formatClaimTimestamp(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
