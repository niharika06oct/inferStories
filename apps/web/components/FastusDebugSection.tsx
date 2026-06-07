"use client";

import type { FastusDebugEventOut, SceneExtractionOut } from "../lib/api";

type FastusDebugSectionProps = {
  extraction: SceneExtractionOut;
};

function lifecycleLabel(event: string): string | null {
  if (event === "stage_begin") return "BEGIN";
  if (event === "stage_complete") return "COMPLETE";
  if (event === "stage_skip") return "SKIP";
  if (event === "stage_warn") return "WARN";
  return null;
}

function EventList({ events, title }: { events: FastusDebugEventOut[]; title: string }) {
  if (!events.length) return null;
  const lifecycle = events.filter((ev) => lifecycleLabel(ev.event));
  const other = events.filter((ev) => !lifecycleLabel(ev.event));
  return (
    <div>
      <p className="mb-1 font-medium text-foreground">{title}</p>
      {lifecycle.length > 0 ? (
        <ul className="mb-2 space-y-1 rounded-md border border-amber-500/35 bg-amber-500/10 px-2 py-2 font-mono text-[10px] leading-relaxed">
          {lifecycle.map((ev, idx) => {
            const tag = lifecycleLabel(ev.event);
            return (
              <li key={`lc-${ev.stage}-${idx}`}>
                <span className="text-amber-200/90">Stage {ev.stage}</span>{" "}
                <span className="font-semibold text-foreground">{tag}</span>:{" "}
                {ev.message}
              </li>
            );
          })}
        </ul>
      ) : null}
      {other.length > 0 ? (
        <ul className="max-h-48 space-y-1 overflow-y-auto rounded-md border border-border/40 bg-background/40 px-2 py-2 font-mono text-[10px] leading-relaxed">
          {other.map((ev, idx) => (
            <li key={`${ev.stage}-${ev.event}-${idx}`}>
              <span className="text-amber-200/90">S{ev.stage}</span>{" "}
              <span className="text-sky-200/80">{ev.event}</span>: {ev.message}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function FastusDebugSection({ extraction }: FastusDebugSectionProps) {
  const hasFastus =
    (extraction.fastus_events?.length ?? 0) > 0 ||
    extraction.fastus_spacy_available != null ||
    (extraction.fastus_stage0_negated_claims ?? 0) > 0 ||
    (extraction.fastus_stage0_rejected_fragments ?? 0) > 0;

  if (!hasFastus) return null;

  return (
    <div className="space-y-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-2 py-2">
      <p className="font-medium text-amber-100/90">FASTUS pipeline (stages 0–9)</p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
        <dt>spaCy</dt>
        <dd>{extraction.fastus_spacy_available ? "available" : "fallback tokenizer"}</dd>
        <dt>Stage 0 negated</dt>
        <dd>{extraction.fastus_stage0_negated_claims ?? 0} claim(s)</dd>
        <dt>Stage 0 rejected</dt>
        <dd>{extraction.fastus_stage0_rejected_fragments ?? 0} fragment(s)</dd>
      </dl>

      {extraction.chunks?.map((chunk) =>
        (chunk.fastus_token_count ?? 0) > 0 ||
        (chunk.fastus_entity_candidate_count ?? 0) > 0 ||
        (chunk.fastus_phrase_candidate_count ?? 0) > 0 ||
        (chunk.fastus_relation_candidate_count ?? 0) > 0 ||
        (chunk.fastus_claim_draft_count ?? 0) > 0 ||
        (chunk.fastus_llm_refined_count ?? 0) > 0 ? (
          <p key={chunk.chunk_index} className="text-[10px]">
            Chunk {chunk.chunk_index + 1}: {chunk.fastus_token_count ?? 0} tokens ·{" "}
            {chunk.fastus_sentence_count ?? 0} sentences · deps=
            {chunk.fastus_has_dependencies ? "yes" : "no"} ·{" "}
            {chunk.fastus_entity_candidate_count ?? 0} entity ·{" "}
            {chunk.fastus_phrase_candidate_count ?? 0} phrase ·{" "}
            {chunk.fastus_relation_candidate_count ?? 0} relation ·{" "}
            {chunk.fastus_claim_draft_count ?? 0} draft ·{" "}
            {chunk.fastus_llm_refined_count ?? 0} LLM refined
            {chunk.fastus_llm_cache_hit ? " (cached)" : ""}
          </p>
        ) : null,
      )}

      <EventList events={extraction.fastus_events ?? []} title="Scene events" />

      {extraction.chunks?.map((chunk) =>
        chunk.fastus_events?.length ? (
          <EventList
            key={`chunk-ev-${chunk.chunk_index}`}
            events={chunk.fastus_events}
            title={`Chunk ${chunk.chunk_index + 1} events`}
          />
        ) : null,
      )}
    </div>
  );
}
