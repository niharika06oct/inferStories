"use client";

import type { SceneExtractionOut } from "../lib/api";
import { FastusDebugSection } from "./FastusDebugSection";
import { formatGenerationBreakdown } from "../lib/formatExtractionSummary";

type ExtractionDebugPanelProps = {
  extraction: SceneExtractionOut;
};

export function ExtractionDebugPanel({ extraction }: ExtractionDebugPanelProps) {
  return (
    <details className="mt-3 rounded-lg border border-border/60 bg-muted/20 text-xs">
      <summary className="cursor-pointer select-none px-3 py-2 font-medium text-muted-foreground hover:text-foreground">
        Extraction details (debug)
      </summary>
      <div className="space-y-3 border-t border-border/50 px-3 py-3 text-muted-foreground">
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
          <dt>Duration</dt>
          <dd>{extraction.duration_ms ?? 0} ms</dd>
          <dt>Source</dt>
          <dd>{extraction.source}</dd>
          <dt>Words</dt>
          <dd>{extraction.word_count}</dd>
          <dt>Chunks</dt>
          <dd>{extraction.chunk_count}</dd>
          <dt>Claims saved</dt>
          <dd>{extraction.claim_count}</dd>
          <dt>OpenAI tried</dt>
          <dd>{extraction.openai_attempted ? "Yes" : "No"}</dd>
          <dt>Fallback used</dt>
          <dd>{extraction.fallback_used ? "Yes" : "No"}</dd>
          <dt>Entities (structural)</dt>
          <dd>{extraction.structural_entity_count ?? 0}</dd>
          {(extraction.suppressed_structural_count ?? 0) > 0 ? (
            <>
              <dt>Duplicates dropped</dt>
              <dd>{extraction.suppressed_structural_count} rule claim(s) (AI already covered)</dd>
            </>
          ) : null}
          {formatGenerationBreakdown(extraction.generation_counts) ? (
            <>
              <dt>By source</dt>
              <dd>{formatGenerationBreakdown(extraction.generation_counts)}</dd>
            </>
          ) : null}
          {(extraction.llm_recall_total ?? 0) > 0 ||
          (extraction.after_dedupe_total ?? 0) > 0 ? (
            <>
              <dt>LLM recall claims</dt>
              <dd>{extraction.llm_recall_total ?? 0}</dd>
              <dt>FASTUS drafts</dt>
              <dd>{extraction.fastus_draft_total ?? 0}</dd>
              <dt>Regex claims</dt>
              <dd>{extraction.regex_claim_total ?? 0}</dd>
              <dt>After dedupe</dt>
              <dd>{extraction.after_dedupe_total ?? 0}</dd>
              <dt>Anchored</dt>
              <dd>{extraction.anchored_total ?? 0}</dd>
              <dt>Needs review (pipeline)</dt>
              <dd>{extraction.needs_review_pipeline_total ?? 0}</dd>
              <dt>Rejected fragments</dt>
              <dd>
                {extraction.rejected_fragment_total ??
                  extraction.fastus_stage0_rejected_fragments ??
                  0}
              </dd>
            </>
          ) : null}
        </dl>

        {extraction.large_chapter_warning ? (
          <p className="text-amber-200/90">
            Large chapter — processed in multiple overlapping sections.
          </p>
        ) : null}

        {extraction.error ? (
          <p className="text-destructive">{extraction.error}</p>
        ) : null}

        <FastusDebugSection extraction={extraction} />

        {extraction.chunks && extraction.chunks.length > 0 ? (
          <ul className="space-y-2">
            {extraction.chunks.map((chunk) => (
              <li
                key={chunk.chunk_index}
                className="rounded-md border border-border/40 bg-background/40 px-2 py-2"
              >
                <p className="font-medium text-foreground">
                  Chunk {chunk.chunk_index + 1} · {chunk.word_count} words
                </p>
                <p>
                  Structural: {chunk.structural_claims} claim
                  {chunk.structural_claims === 1 ? "" : "s"}
                  {chunk.entities.length > 0
                    ? ` · entities: ${chunk.entities.join(", ")}`
                    : ""}
                </p>
                <p>
                  LLM layer: {chunk.llm_claims} claim
                  {chunk.llm_claims === 1 ? "" : "s"} · OpenAI{" "}
                  {chunk.openai_attempted
                    ? chunk.openai_ok
                      ? "ok"
                      : "failed"
                    : "skipped"}
                  {chunk.fallback_used ? " · fallback" : ""}
                </p>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </details>
  );
}
