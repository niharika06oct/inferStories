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
GenerationOrigin = Literal["structural", "family", "llm", "heuristic"]
GENERATION_ORIGINS: tuple[str, ...] = ("structural", "family", "llm", "heuristic")


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
    confidence: float = Field(ge=0.0, le=1.0)
    canon_level: CanonLevel = "active"
    evidence: str = Field(min_length=1, max_length=500)
    chunk_index: int = Field(default=0, ge=0)
    generation_origin: GenerationOrigin = Field(
        default="structural",
        description="Pipeline step that produced this claim (structural, family, llm, heuristic).",
    )


class ChunkExtractionDebug(BaseModel):
    chunk_index: int
    word_count: int
    openai_attempted: bool = False
    openai_ok: bool = False
    fallback_used: bool = False
    structural_claims: int = 0
    llm_claims: int = 0
    entities: list[str] = Field(default_factory=list)


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
