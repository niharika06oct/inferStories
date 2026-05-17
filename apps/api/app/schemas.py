from datetime import datetime
from typing import Optional

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


class SceneCreate(BaseModel):
    scene_number: int = Field(ge=1)
    text: str = Field(min_length=1)
    claims: list[ClaimIn]


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


class ClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject: str
    predicate: str
    object: str
    is_major_plotline: bool


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
    claims: list[ClaimIn]


class SceneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    story_id: int
    scene_number: int
    text: str
    issues: list[SceneIssueOut] = Field(default_factory=list)
