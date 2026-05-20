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
    is_major_plotline: bool = False
    claim_type: Optional[str] = None
    claim_text: Optional[str] = None
    confidence: Optional[float] = None
    canon_level: Optional[str] = None
    evidence_text: Optional[str] = None


class ClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject: str
    predicate: str
    object: str
    is_major_plotline: bool
    claim_type: Optional[str] = None
    claim_text: Optional[str] = None
    target: Optional[str] = None
    confidence: float = 1.0
    canon_level: str = "active"
    status: str = "approved"
    evidence_text: Optional[str] = None
    source: str = "manual"
    chunk_index: Optional[int] = None


class ClaimStatusUpdate(BaseModel):
    status: Literal["approved", "rejected", "needs_review", "suggested", "deprecated"]
    claim_text: Optional[str] = None
    subject: Optional[str] = None
    target: Optional[str] = None


class SceneExtractionOut(BaseModel):
    source: str
    chunk_count: int
    word_count: int
    claim_count: int
    approved_count: int
    needs_review_count: int
    suggested_count: int


class SceneCreate(BaseModel):
    scene_number: int = Field(ge=1)
    text: str = Field(min_length=1)
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
    created_at: datetime


class SceneSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    story_id: int
    scene_number: int
    text: str
    created_at: datetime
    claim_count: int


class SceneDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    story_id: int
    scene_number: int
    text: str
    created_at: datetime
    claims: list[ClaimOut]


class SceneUpdate(BaseModel):
    scene_number: int = Field(ge=1)
    text: str = Field(min_length=1)
    claims: list[ClaimIn] = Field(default_factory=list)


class SceneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    story_id: int
    scene_number: int
    text: str
    issues: list[SceneIssueOut] = Field(default_factory=list)
    extraction: Optional[SceneExtractionOut] = None
