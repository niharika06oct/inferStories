"""Pydantic models for LLM extraction output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CLAIM_TYPES = (
    "character_trait",
    "character_goal",
    "character_state",
    "character_preference",
    "place_preference",
    "relationship_state",
    "relationship_change",
    "event",
    "world_rule",
    "power_rule",
    "timeline_fact",
    "plotline_fact",
)

CanonLevel = Literal["core", "active", "soft"]

# How the claim was produced before DB persist (distinct from Claim.source manual/extracted).
GenerationOrigin = Literal[
    "structural",
    "family",
    "llm",
    "llm_recall",
    "fastus",
    "heuristic",
]
GENERATION_ORIGINS: tuple[str, ...] = (
    "structural",
    "family",
    "llm",
    "llm_recall",
    "fastus",
    "heuristic",
)

Importance = Literal["low", "medium", "high"]
ReviewStatus = Literal["suggested", "needs_review", "approved"]


class ExtractedClaim(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    claim_type: str = Field(min_length=1, max_length=64)
    predicate: str = Field(
        default="",
        max_length=64,
        description="Semantic relation verb (e.g. distrusts), not claim_type slug",
    )
    target: str = Field(default="", max_length=255)
    claim: str = Field(min_length=1)
    polarity: bool = Field(
        default=True,
        description="False when the source text negates the fact (e.g. 'was not my father').",
    )
    confidence: float = Field(ge=0.0, le=1.0)
    canon_level: CanonLevel = "active"
    evidence: str = Field(min_length=1, max_length=500)
    chunk_index: int = Field(default=0, ge=0)
    generation_origin: GenerationOrigin = Field(
        default="structural",
        description="Pipeline step that produced this claim.",
    )
    secondary_origins: list[str] = Field(
        default_factory=list,
        description="Additional sources after source-aware dedupe (e.g. fastus+llm_recall).",
    )
    anchored: bool | None = Field(
        default=None,
        description="True when evidence quote appears in chunk text.",
    )
    importance: Importance = "medium"
    review_status: ReviewStatus | None = Field(
        default=None,
        description="Override confidence-based status after anchoring.",
    )


class FastusDebugEventOut(BaseModel):
    stage: str
    event: str
    message: str
    detail: dict[str, str] = Field(default_factory=dict)


class ChunkExtractionDebug(BaseModel):
    chunk_index: int
    word_count: int
    openai_attempted: bool = False
    openai_ok: bool = False
    fallback_used: bool = False
    structural_claims: int = 0
    llm_claims: int = 0
    entities: list[str] = Field(default_factory=list)
    # FASTUS stages 1–2 (shadow path — not yet primary extractor)
    fastus_token_count: int = 0
    fastus_sentence_count: int = 0
    fastus_has_dependencies: bool = False
    fastus_entity_candidate_count: int = 0
    fastus_phrase_candidate_count: int = 0
    fastus_relation_candidate_count: int = 0
    fastus_claim_draft_count: int = 0
    fastus_llm_refined_count: int = 0
    fastus_llm_rejected_count: int = 0
    fastus_llm_cache_hit: bool = False
    llm_recall_count: int = 0
    fastus_extracted_count: int = 0
    regex_claim_count: int = 0
    after_dedupe_count: int = 0
    anchored_count: int = 0
    unanchored_count: int = 0
    fastus_events: list[FastusDebugEventOut] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    claims: list[ExtractedClaim] = Field(default_factory=list)
    suppressed_structural_count: int = 0
    source: str  # openai | heuristic | hybrid
    chunk_count: int = 1
    word_count: int = 0
    error: str | None = None
    duration_ms: int = 0
    openai_attempted: bool = False
    fallback_used: bool = False
    large_chapter_warning: bool = False
    structural_entity_count: int = 0
    chunks: list[ChunkExtractionDebug] = Field(default_factory=list)
    # FASTUS summary across stages 0–2
    fastus_spacy_available: bool = False
    fastus_stage0_negated_claims: int = 0
    fastus_stage0_rejected_fragments: int = 0
    fastus_events: list[FastusDebugEventOut] = Field(default_factory=list)
    llm_recall_total: int = 0
    fastus_draft_total: int = 0
    regex_claim_total: int = 0
    after_dedupe_total: int = 0
    anchored_total: int = 0
    unanchored_total: int = 0
    needs_review_pipeline_total: int = 0
