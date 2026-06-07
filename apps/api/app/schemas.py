from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class StoryCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None


class StoryUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None


class StoryDescriptionOut(BaseModel):
    description: str
    source: str  # openai | heuristic


class StoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    created_at: datetime


class StoryListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    created_at: datetime
    scene_count: int


class ClaimIn(BaseModel):
    subject: str
    predicate: str
    object: str
    polarity: bool = True
    is_major_plotline: bool = False
    claim_type: Optional[str] = None
    claim_text: Optional[str] = None
    confidence: Optional[float] = None
    canon_level: Optional[str] = None
    evidence_text: Optional[str] = None


class EntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    story_id: int
    canonical_name: str
    entity_type: str
    type_confidence: float = 0.0
    graph_eligible: bool = False
    aliases: list[str] = Field(default_factory=list)
    description: Optional[str] = None
    created_at: datetime


class ClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject: str
    predicate: str
    object: str
    polarity: bool = True
    subject_entity_id: Optional[int] = None
    object_entity_id: Optional[int] = None
    is_major_plotline: bool
    claim_type: Optional[str] = None
    claim_text: Optional[str] = None
    target: Optional[str] = None
    confidence: float = 1.0
    canon_level: str = "active"
    status: str = "approved"
    evidence_text: Optional[str] = None
    source: str = "manual"
    generation_origin: str = "unknown"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    extracted_at: Optional[datetime] = None
    chunk_index: Optional[int] = None
    claim_version: int = 1
    superseded_by_claim_id: Optional[int] = None
    source_hash: Optional[str] = None
    valid_from_scene: Optional[int] = None
    valid_until_scene: Optional[int] = None
    confidence_history: Optional[str] = None


class GraphSupportingClaimOut(BaseModel):
    claim_id: int
    predicate: str
    claim_text: Optional[str] = None
    confidence: float
    scene_number: int


class RelationshipGraphNodeOut(BaseModel):
    id: str
    entity_id: int
    label: str
    type: str
    importance_score: float
    mention_count: int
    relationship_degree: int = 0


class RelationshipGraphEdgeOut(BaseModel):
    id: str
    source: str
    target: str
    source_entity_id: int
    target_entity_id: int
    predicate: str
    primary_relationship: str
    sub_relationships: list[str] = Field(default_factory=list)
    strength: float
    confidence: float
    claim_count: int
    status: str = "active"  # active | preview
    supporting_claims: list[GraphSupportingClaimOut] = Field(default_factory=list)


class RelationshipGraphMetaOut(BaseModel):
    canon_statuses: list[str]
    relationship_predicate_count: int
    approved_relationship_claim_count: int = 0
    pending_preview_claim_count: int = 0
    include_preview: bool = False


class RelationshipGraphOut(BaseModel):
    story_id: int
    nodes: list[RelationshipGraphNodeOut]
    edges: list[RelationshipGraphEdgeOut]
    meta: RelationshipGraphMetaOut


class ClaimStatusUpdate(BaseModel):
    status: Literal["approved", "rejected", "needs_review", "suggested", "deprecated"]
    claim_text: Optional[str] = None
    subject: Optional[str] = None
    target: Optional[str] = None


class FastusDebugEventOut(BaseModel):
    stage: str
    event: str
    message: str
    detail: dict[str, str] = Field(default_factory=dict)


class ChunkExtractionDebugOut(BaseModel):
    chunk_index: int
    word_count: int
    openai_attempted: bool
    openai_ok: bool
    fallback_used: bool
    structural_claims: int
    llm_claims: int
    entities: list[str] = Field(default_factory=list)
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
    fastus_events: list[FastusDebugEventOut] = Field(default_factory=list)


class SceneExtractionOut(BaseModel):
    source: str
    chunk_count: int
    word_count: int
    claim_count: int
    approved_count: int
    needs_review_count: int
    suggested_count: int
    error: Optional[str] = None
    duration_ms: int = 0
    openai_attempted: bool = False
    fallback_used: bool = False
    large_chapter_warning: bool = False
    structural_entity_count: int = 0
    suppressed_structural_count: int = 0
    generation_counts: dict[str, int] = Field(default_factory=dict)
    chunks: list[ChunkExtractionDebugOut] = Field(default_factory=list)
    fastus_spacy_available: bool = False
    fastus_stage0_negated_claims: int = 0
    fastus_stage0_rejected_fragments: int = 0
    fastus_events: list[FastusDebugEventOut] = Field(default_factory=list)


class SceneCreate(BaseModel):
    scene_number: int = Field(ge=1)
    text: str = Field(min_length=1)
    pov_character: str | None = Field(default=None, max_length=128)
    claims: list[ClaimIn] = Field(default_factory=list)


class SceneIssueOut(BaseModel):
    """Issues embedded on a scene response (same scene as parent)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    severity: str
    message: str
    conflicting_claim_id: Optional[int] = None
    created_at: datetime


class ValidationIssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    story_id: int
    scene_id: int
    scene_number: int
    severity: str
    message: str
    conflicting_claim_id: Optional[int] = None
    conflicting_scene_number: Optional[int] = None
    current_claim_id: Optional[int] = None
    text_offset: int = 0
    anchor_text: Optional[str] = None
    anchor_length: int = 0
    resolution_status: str = "open"
    judge_source: str = "rules"
    judge_classification: str = "hard_contradiction"
    judge_confidence: float = 1.0
    judge_reason: Optional[str] = None
    conflict_kind: Optional[str] = None
    conflicting_evidence_text: Optional[str] = None
    current_evidence_text: Optional[str] = None
    evidence_comparison: Optional[str] = None
    explanation: Optional[str] = None
    suggested_fix: Optional[str] = None
    created_at: datetime


class ValidationIssueStatusUpdate(BaseModel):
    resolution_status: Literal["open", "fixed", "rejected"]


class SceneSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    story_id: int
    scene_number: int
    text: str
    pov_character: str | None = None
    created_at: datetime
    claim_count: int


class SceneDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    story_id: int
    scene_number: int
    text: str
    pov_character: str | None = None
    created_at: datetime
    claims: list[ClaimOut]


class SceneUpdate(BaseModel):
    scene_number: int = Field(ge=1)
    text: str = Field(min_length=1)
    pov_character: str | None = Field(default=None, max_length=128)
    claims: list[ClaimIn] = Field(default_factory=list)
    # When false, only persist chapter text/number (for editor autosave).
    run_extraction: bool = True


class SceneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    story_id: int
    scene_number: int
    text: str
    issues: list[SceneIssueOut] = Field(default_factory=list)
    extraction: Optional[SceneExtractionOut] = None
