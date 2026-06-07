"""FASTUS Stage 9 — enriched validation issues (evidence + explanation + fix)."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.continuity_judge import ContinuityCandidate
from app.database import Base
from app.models import Claim, Scene, Story
from app.validation import validate_scene_claims
from app.validation_issue_detail import (
    build_evidence_comparison,
    build_explanation,
    build_suggested_fix,
    format_claim_fact,
)


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, _):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_polarity_flip_issue_includes_evidence_and_suggested_fix():
    db = _session()
    try:
        story = Story(title="t", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()

        s1 = Scene(
            story_id=story.id,
            scene_number=1,
            text="Charlie is my father.",
        )
        db.add(s1)
        db.flush()
        db.add(
            Claim(
                story_id=story.id,
                scene_id=s1.id,
                subject="Charlie",
                predicate="father_of",
                claim_object="Bella",
                polarity=True,
                claim_text="Charlie is my father.",
                evidence_text="Charlie is my father.",
                status="approved",
            )
        )

        s2 = Scene(
            story_id=story.id,
            scene_number=2,
            text="Charlie was not my father.",
        )
        db.add(s2)
        db.flush()
        c_new = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Charlie",
            predicate="father_of",
            claim_object="Bella",
            polarity=False,
            claim_text="Charlie was not my father.",
            evidence_text="Charlie was not my father.",
            status="approved",
        )
        db.add(c_new)
        db.flush()

        issues = validate_scene_claims(db, s2, [c_new])
        assert len(issues) == 1
        issue = issues[0]
        assert issue.conflict_kind == "polarity_flip"
        assert issue.conflicting_evidence_text == "Charlie is my father."
        assert issue.current_evidence_text == "Charlie was not my father."
        assert "Earlier:" in (issue.evidence_comparison or "")
        assert issue.explanation
        assert "asserted and negated" in issue.explanation
        assert issue.suggested_fix
        assert "deprecate" in issue.suggested_fix.lower()
    finally:
        db.close()


def test_predicate_opposition_issue_detail():
    db = _session()
    try:
        story = Story(title="t", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()

        s1 = Scene(story_id=story.id, scene_number=1, text="She trusted him.")
        db.add(s1)
        db.flush()
        db.add(
            Claim(
                story_id=story.id,
                scene_id=s1.id,
                subject="Bella",
                predicate="trusts",
                claim_object="Edward",
                evidence_text="She trusted him.",
                status="approved",
            )
        )

        s2 = Scene(story_id=story.id, scene_number=2, text="She distrusted him.")
        db.add(s2)
        db.flush()
        c_new = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Bella",
            predicate="distrusts",
            claim_object="Edward",
            evidence_text="She distrusted him.",
            status="suggested",
        )
        db.add(c_new)
        db.flush()

        issues = validate_scene_claims(db, s2, [c_new])
        assert len(issues) == 1
        issue = issues[0]
        assert issue.conflict_kind == "predicate_opposition"
        assert issue.conflicting_evidence_text == "She trusted him."
        assert issue.current_evidence_text == "She distrusted him."
        assert issue.suggested_fix
        assert "bridging" in issue.suggested_fix.lower()
    finally:
        db.close()


def test_format_claim_fact_marks_negation():
    claim = Claim(
        story_id=1,
        scene_id=1,
        subject="Charlie",
        predicate="father_of",
        claim_object="Bella",
        polarity=False,
    )
    assert format_claim_fact(claim).startswith("NOT (")


def test_build_evidence_comparison_both_quotes():
    old = Claim(
        story_id=1,
        scene_id=1,
        subject="A",
        predicate="trusts",
        claim_object="B",
        evidence_text="old quote",
    )
    new = Claim(
        story_id=1,
        scene_id=2,
        subject="A",
        predicate="trusts",
        claim_object="B",
        evidence_text="new quote",
        polarity=False,
    )
    comparison = build_evidence_comparison(old, new)
    assert 'Earlier: "old quote"' in comparison
    assert 'Now: "new quote"' in comparison


def test_build_suggested_fix_templates():
    from app.continuity_judge import ContinuityJudgment

    old = Claim(
        story_id=1,
        scene_id=1,
        subject="A",
        predicate="trusts",
        claim_object="B",
    )
    new = Claim(
        story_id=1,
        scene_id=2,
        subject="A",
        predicate="trusts",
        claim_object="Nobody",
    )
    scene = Scene(story_id=1, scene_number=2, text="x")
    candidate = ContinuityCandidate(
        scene=scene,
        new_claim=new,
        old_claim=old,
        severity="high",
        message="msg",
        rule_classification="hard_contradiction",
        rule_reason="exclusive",
        conflict_kind="exclusive_object",
    )
    judgment = ContinuityJudgment(
        classification="hard_contradiction",
        confidence=1.0,
        reason="exclusive object",
        source="rules",
    )
    assert "Pick one value" in build_suggested_fix(candidate)
    assert "exclusive" in build_explanation(candidate, judgment).lower()
