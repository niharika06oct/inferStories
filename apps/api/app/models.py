from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_user_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    scenes: Mapped[list["Scene"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )
    entities: Mapped[list["Entity"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    story_id: Mapped[int] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(
        String(32), default="character", nullable=False
    )
    type_confidence: Mapped[float] = mapped_column(default=0.0, nullable=False)
    graph_eligible: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    aliases: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    story: Mapped["Story"] = relationship(back_populates="entities")


class Scene(Base):
    __tablename__ = "scenes"
    __table_args__ = (
        UniqueConstraint("story_id", "scene_number", name="uq_scene_story_scene_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    story_id: Mapped[int] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    scene_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    pov_character: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    story: Mapped["Story"] = relationship(back_populates="scenes")
    claims: Mapped[list["Claim"]] = relationship(
        back_populates="scene",
        cascade="all, delete-orphan",
        foreign_keys="Claim.scene_id",
    )
    issues: Mapped[list["ValidationIssue"]] = relationship(
        back_populates="scene", cascade="all, delete-orphan"
    )


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    story_id: Mapped[int] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    scene_id: Mapped[int] = mapped_column(
        ForeignKey("scenes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    predicate: Mapped[str] = mapped_column(String(255), nullable=False)
    # Column name "object" in SQL; avoid shadowing Python builtin `object`.
    claim_object: Mapped[str] = mapped_column("object", String(255), nullable=False)
    # False encodes a negated fact ("Charlie was not my father" -> father_of, polarity False).
    polarity: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    subject_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    object_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    is_major_plotline: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    claim_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    claim_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(default=1.0, nullable=False)
    canon_level: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default="approved", nullable=False
    )
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    generation_origin: Mapped[str] = mapped_column(
        String(20), default="unknown", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    claim_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    superseded_by_claim_id: Mapped[int | None] = mapped_column(
        ForeignKey("claims.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_hash: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    # FASTUS Stage 7: optional temporal validity for state transitions within a story.
    valid_from_scene: Mapped[int | None] = mapped_column(
        ForeignKey("scenes.id", ondelete="SET NULL"),
        nullable=True,
    )
    valid_until_scene: Mapped[int | None] = mapped_column(
        ForeignKey("scenes.id", ondelete="SET NULL"),
        nullable=True,
    )
    confidence_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    scene: Mapped["Scene"] = relationship(
        back_populates="claims",
        foreign_keys=[scene_id],
    )


class ValidationIssue(Base):
    __tablename__ = "validation_issues"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    story_id: Mapped[int] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    scene_id: Mapped[int] = mapped_column(
        ForeignKey("scenes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # high/medium/low
    message: Mapped[str] = mapped_column(Text, nullable=False)
    conflicting_claim_id: Mapped[int | None] = mapped_column(
        ForeignKey("claims.id"), nullable=True
    )
    current_claim_id: Mapped[int | None] = mapped_column(
        ForeignKey("claims.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    text_offset: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    anchor_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    anchor_length: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # open = needs attention; fixed = addressed; rejected = dismissed as non-issue
    resolution_status: Mapped[str] = mapped_column(
        String(20), default="open", nullable=False
    )
    judge_source: Mapped[str] = mapped_column(
        String(20), default="rules", nullable=False
    )
    judge_classification: Mapped[str] = mapped_column(
        String(32), default="hard_contradiction", nullable=False
    )
    judge_confidence: Mapped[float] = mapped_column(default=1.0, nullable=False)
    judge_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflict_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    conflicting_evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_comparison: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    scene: Mapped["Scene"] = relationship(back_populates="issues")
    conflicting_claim: Mapped["Claim | None"] = relationship(
        foreign_keys=[conflicting_claim_id],
    )
    current_claim: Mapped["Claim | None"] = relationship(
        foreign_keys=[current_claim_id],
    )
