/** Matches API `generation_origin` on claims. */
export type ClaimGenerationOrigin =
  | "structural"
  | "family"
  | "llm"
  | "heuristic"
  | "manual"
  | "unknown";

const LABELS: Record<ClaimGenerationOrigin, string> = {
  structural: "Rules · pattern",
  family: "Rules · family",
  llm: "AI (LLM)",
  heuristic: "Fallback",
  manual: "Manual",
  unknown: "Unknown",
};

export function labelForGenerationOrigin(origin: string | undefined): string {
  if (!origin) return LABELS.unknown;
  return LABELS[origin as ClaimGenerationOrigin] ?? origin;
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
