from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    scenes: Mapped[list["Scene"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    story: Mapped["Story"] = relationship(back_populates="scenes")
    claims: Mapped[list["Claim"]] = relationship(
        back_populates="scene", cascade="all, delete-orphan"
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
    is_major_plotline: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    scene: Mapped["Scene"] = relationship(back_populates="claims")


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    scene: Mapped["Scene"] = relationship(back_populates="issues")
