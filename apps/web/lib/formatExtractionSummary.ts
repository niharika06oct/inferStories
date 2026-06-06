import type { SceneExtractionOut } from "./api";
import { labelForGenerationOrigin } from "./claimGenerationOrigin";

export function formatGenerationBreakdown(
  counts: Record<string, number> | undefined,
): string | null {
  if (!counts || Object.keys(counts).length === 0) return null;
  const parts = Object.entries(counts)
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([key, n]) => `${n} ${labelForGenerationOrigin(key).toLowerCase()}`);
  return parts.join(" · ");
}

export function extractionEngineLabel(extraction: SceneExtractionOut): string {
  if (extraction.error) return "failed";
  if (extraction.source === "openai") return "AI + rules";
  if (extraction.source === "hybrid") return "AI + rules (partial fallback)";
  if (extraction.openai_attempted && !extraction.fallback_used) return "AI";
  return "rules only (no AI key or LLM skipped)";
}
