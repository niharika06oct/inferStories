"""Pydantic models for LLM extraction output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CLAIM_TYPES = (
    "character_trait",
    "character_goal",
    "character_state",
    "relationship_state",
    "relationship_change",
    "event",
    "world_rule",
    "power_rule",
    "timeline_fact",
    "plotline_fact",
)

CanonLevel = Literal["core", "active", "soft"]


class ExtractedClaim(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    claim_type: str = Field(min_length=1, max_length=64)
    target: str = Field(default="", max_length=255)
    claim: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    canon_level: CanonLevel = "active"
    evidence: str = Field(min_length=1, max_length=500)
    chunk_index: int = Field(default=0, ge=0)


class ExtractionResult(BaseModel):
    claims: list[ExtractedClaim] = Field(default_factory=list)
    source: str  # openai | heuristic
    chunk_count: int = 1
    word_count: int = 0
