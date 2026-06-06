/** Align with API `status_for_confidence` thresholds in extract.py */

export const CONFIDENCE_AUTO_APPROVE = 0.9;
export const CONFIDENCE_NEEDS_REVIEW = 0.65;

export type ConfidenceTier = "high" | "medium" | "low";

export function confidenceTier(confidence: number): ConfidenceTier {
  if (confidence >= CONFIDENCE_AUTO_APPROVE) return "high";
  if (confidence >= CONFIDENCE_NEEDS_REVIEW) return "medium";
  return "low";
}

export function confidenceTierIcon(tier: ConfidenceTier): string {
  if (tier === "high") return "✓";
  if (tier === "medium") return "○";
  return "⚠";
}

export function formatConfidenceLabel(confidence: number): string {
  const tier = confidenceTier(confidence);
  const pct = Math.round(confidence * 100);
  return `${confidenceTierIcon(tier)} ${pct}%`;
}
