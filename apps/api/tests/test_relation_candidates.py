"""FASTUS Stage 4 — relation candidates + coreference."""

from app.nlp.coreference import build_coref_context, resolve_surface
from app.nlp.relation_candidates import (
    extract_relation_candidates_from_text,
    reject_reason_for_relation,
)
from app.nlp.entity_candidates import extract_entity_candidates_from_text


def test_family_identity_negated_charlie_not_father():
    rels = extract_relation_candidates_from_text(
        "Charlie was not my father.",
        pov_character="Isabella Swan",
    )
    father = [r for r in rels if r.predicate_normalized == "father_of"]
    assert father, "expected father_of relation"
    assert father[0].subject_surface == "Charlie"
    assert father[0].object_surface == "Isabella Swan"
    assert father[0].polarity is False


def test_family_identity_positive_charlie_is_father():
    rels = extract_relation_candidates_from_text(
        "Charlie was my father.",
        pov_character="Isabella Swan",
    )
    father = [r for r in rels if r.predicate_normalized == "father_of"]
    assert father
    assert father[0].polarity is True


def test_pronoun_object_resolves_with_prior_entity():
    text = "Charlie smiled at me. I did not trust him at all."
    rels = extract_relation_candidates_from_text(
        text,
        pov_character="Isabella Swan",
    )
    trust = [r for r in rels if r.predicate_normalized == "trusts"]
    assert trust, "expected resolved trust relation"
    assert trust[0].subject_surface == "Isabella Swan"
    assert trust[0].object_surface == "Charlie"
    assert trust[0].polarity is False


def test_unresolved_pronoun_object_is_rejected():
    rels = extract_relation_candidates_from_text(
        "I did not trust him at all.",
        pov_character="Isabella Swan",
    )
    assert not any(r.predicate_normalized == "trusts" for r in rels)


def test_state_relation_uncomfortable_with_edward():
    rels = extract_relation_candidates_from_text(
        "Bella was uncomfortable with Edward.",
        pov_character="Bella",
    )
    state = [r for r in rels if r.predicate_normalized == "uncomfortable"]
    assert state
    assert state[0].subject_surface in ("Bella", "Bella Swan")
    assert "Edward" in state[0].object_surface


def test_named_svo_negated_trust():
    rels = extract_relation_candidates_from_text(
        "Edward did not trust Bella.",
        pov_character="Isabella Swan",
    )
    trust = [r for r in rels if r.predicate_normalized == "trusts"]
    assert trust
    assert trust[0].subject_surface == "Edward"
    assert trust[0].object_surface in ("Bella", "Bella Swan")
    assert trust[0].polarity is False


def test_reject_auxiliary_subject_fragment():
    assert reject_reason_for_relation(
        subject_surface="did",
        object_surface="Bella",
        predicate_normalized="trusts",
    )


def test_coref_pov_resolves_i():
    entities = extract_entity_candidates_from_text("Bella walked.", pov_character="Bella")
    ctx = build_coref_context(entities, pov_character="Bella")
    res = resolve_surface("I", ctx, role="subject")
    assert res.resolved_surface == "Bella"
    assert res.method == "pov"


def test_fastus_debug_includes_stage4_on_extract():
    from app.extraction.extract import extract_claims_from_text

    result = extract_claims_from_text(
        "Charlie was not my father. Edward did not trust Bella.",
        pov_character="Isabella Swan",
    )
    assert result.chunks[0].fastus_relation_candidate_count >= 1
    stages = {e.stage for e in result.fastus_events}
    assert "4" in stages
    assert any(e.event == "relation_candidates" for e in result.fastus_events)
