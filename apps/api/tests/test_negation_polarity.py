"""Stage 0 FASTUS safety fixes: negation polarity + fragment rejection.

Covers the Twilight Chapter 13 regressions:
- "Charlie was not my father." must not become a positive father_of claim.
- "I did not trust him at all." must not become a fragment claim.
- A later negation of an earlier asserted fact is a hard contradiction.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.claim_identity import compute_entity_source_hash
from app.database import Base
from app.extraction.claim_filter import should_reject_extracted_claim
from app.extraction.family import family_extract_chunk
from app.extraction.schema import ExtractedClaim
from app.extraction.structural import has_identity_negation, structural_extract_chunk
from app.models import Claim, Scene, Story
from app.validation import validate_scene_claims


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


# --- Negation detection -------------------------------------------------


def test_has_identity_negation():
    assert has_identity_negation("Charlie was not my father.")
    assert has_identity_negation("My mother was not Renée.")
    assert has_identity_negation("They weren't real.")
    assert not has_identity_negation("Charlie was my father.")
    assert not has_identity_negation("I loved Phoenix.")


def test_family_negated_father_has_false_polarity():
    text = "Charlie was not my father. He was a stranger."
    claims = family_extract_chunk(text, 0, pov_character="Isabella Swan")
    father = [c for c in claims if c.predicate == "father_of"]
    assert father, "expected a father_of claim"
    assert all(c.polarity is False for c in father)


def test_family_negated_mother_has_false_polarity():
    text = "My mother was not Renée, and she had never missed me."
    claims = family_extract_chunk(text, 0, pov_character="Isabella Swan")
    mother = [c for c in claims if c.predicate == "mother_of"]
    assert mother, "expected a mother_of claim"
    assert all(c.polarity is False for c in mother)


def test_family_positive_father_keeps_true_polarity():
    text = "Charlie was my father."
    claims = family_extract_chunk(text, 0, pov_character="Isabella Swan")
    father = [c for c in claims if c.predicate == "father_of"]
    assert father
    assert all(c.polarity is True for c in father)


def test_structural_negated_emotion_named_subject():
    text = "Edward did not trust Bella."
    claims = structural_extract_chunk(text, 0, pov_character="Isabella Swan")
    trust = [c for c in claims if c.predicate == "trusts"]
    assert trust, "expected a trust claim"
    assert all(c.polarity is False for c in trust)


# --- Fragment rejection -------------------------------------------------


def test_reject_pronoun_object_fragment():
    # "I did not trust him at all" -> object head is a pronoun -> cannot resolve yet.
    claim = ExtractedClaim(
        subject="Isabella Swan",
        claim_type="relationship_state",
        predicate="trusts",
        target="him at all",
        claim="Isabella Swan not trusts him at all.",
        polarity=False,
        confidence=0.6,
        evidence="did not trust him at all",
    )
    assert should_reject_extracted_claim(claim)


def test_reject_auxiliary_subject_fragment():
    claim = ExtractedClaim(
        subject="did",
        claim_type="relationship_state",
        predicate="trusts",
        target="Bella",
        claim="did trusts Bella.",
        confidence=0.6,
        evidence="did not trust",
    )
    assert should_reject_extracted_claim(claim)


def test_structural_first_person_pronoun_object_is_filtered_out():
    # Full structural pass on the Chapter 13 line should not yield a "him" fragment.
    from app.extraction.claim_filter import filter_extracted_claims

    text = "I did not trust him at all."
    claims = filter_extracted_claims(
        structural_extract_chunk(text, 0, pov_character="Isabella Swan"),
        pov_character="Isabella Swan",
    )
    assert not any(c.target.split()[0].lower() == "him" for c in claims)


# --- Polarity in identity hash -----------------------------------------


def test_polarity_changes_source_hash():
    pos = compute_entity_source_hash(1, "father_of", 2, "relationship_state")
    neg = compute_entity_source_hash(
        1, "father_of", 2, "relationship_state", polarity=False
    )
    assert pos != neg
    # Positive default stays stable (back-compat with existing rows/hashes).
    assert pos == compute_entity_source_hash(
        1, "father_of", 2, "relationship_state", polarity=True
    )


# --- Polarity-aware continuity -----------------------------------------


def test_polarity_flip_is_hard_contradiction():
    db = _session()
    try:
        story = Story(title="t", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()

        s1 = Scene(story_id=story.id, scene_number=1, text="Charlie is my father.")
        db.add(s1)
        db.flush()
        db.add(
            Claim(
                story_id=story.id,
                scene_id=s1.id,
                subject="Charlie",
                predicate="father_of",
                claim_object="Isabella Swan",
                polarity=True,
                claim_type="relationship_state",
                status="approved",
                is_major_plotline=True,
            )
        )

        s2 = Scene(story_id=story.id, scene_number=2, text="Charlie was not my father.")
        db.add(s2)
        db.flush()
        c_new = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Charlie",
            predicate="father_of",
            claim_object="Isabella Swan",
            polarity=False,
            claim_type="relationship_state",
            status="approved",
            is_major_plotline=True,
        )
        db.add(c_new)
        db.flush()

        issues = validate_scene_claims(db, s2, [c_new])
        assert len(issues) == 1
        assert issues[0].severity == "high"
        assert issues[0].judge_classification == "hard_contradiction"
    finally:
        db.close()


def test_same_polarity_is_not_contradiction():
    db = _session()
    try:
        story = Story(title="t", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()

        s1 = Scene(story_id=story.id, scene_number=1, text="Charlie is my father.")
        db.add(s1)
        db.flush()
        db.add(
            Claim(
                story_id=story.id,
                scene_id=s1.id,
                subject="Charlie",
                predicate="father_of",
                claim_object="Isabella Swan",
                polarity=True,
                claim_type="relationship_state",
                status="approved",
            )
        )

        s2 = Scene(story_id=story.id, scene_number=2, text="Charlie is my father.")
        db.add(s2)
        db.flush()
        c_new = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Charlie",
            predicate="father_of",
            claim_object="Isabella Swan",
            polarity=True,
            claim_type="relationship_state",
            status="approved",
        )
        db.add(c_new)
        db.flush()

        issues = validate_scene_claims(db, s2, [c_new])
        assert issues == []
    finally:
        db.close()
