"""FASTUS Stage 5 — semantic patterns (RelationCandidate → ClaimDraft)."""

from app.extraction.semantic_patterns import (
    build_claim_sentence,
    infer_claim_type,
    normalize_predicate,
    relation_to_claim_draft,
    relations_to_claim_drafts,
)
from app.nlp.entity_candidates import extract_entity_candidates_from_text
from app.nlp.relation_candidates import extract_relation_candidates_from_text


def _drafts_for(text: str, *, pov: str = "Isabella Swan"):
    entities = extract_entity_candidates_from_text(text, pov_character=pov)
    relations = extract_relation_candidates_from_text(text, pov_character=pov)
    return relations_to_claim_drafts(relations, entities)


def test_negated_trust_maps_to_relationship_state():
    text = "Charlie smiled at me. I did not trust him at all."
    drafts = _drafts_for(text)
    trust = [d for d in drafts if d.predicate == "trusts"]
    assert trust
    assert trust[0].claim_type == "relationship_state"
    assert trust[0].polarity is False
    assert "does not trust" in trust[0].claim.lower()
    assert trust[0].subject == "Isabella Swan"
    assert trust[0].target == "Charlie"


def test_negated_father_of_claim_text_and_polarity():
    drafts = _drafts_for("Charlie was not my father.")
    father = [d for d in drafts if d.predicate == "father_of"]
    assert father
    assert father[0].claim_type == "relationship_state"
    assert father[0].polarity is False
    assert "is not the father of" in father[0].claim.lower()
    assert father[0].predicate == "father_of"


def test_state_adjective_maps_to_character_state():
    drafts = _drafts_for("Bella was uncomfortable with Edward.", pov="Bella")
    state = [d for d in drafts if d.predicate == "uncomfortable"]
    assert state
    assert state[0].claim_type == "character_state"
    assert "uncomfortable with Edward" in state[0].claim


def test_normalize_predicate_trust_variants():
    assert normalize_predicate("trusted") == "trusts"
    assert normalize_predicate("trust") == "trusts"
    assert normalize_predicate("father_of") == "father_of"


def test_build_claim_sentence_positive_family():
    claim = build_claim_sentence(
        subject="Charlie",
        predicate="father_of",
        target="Isabella Swan",
        polarity=True,
    )
    assert claim == "Charlie is the father of Isabella Swan."


def test_infer_claim_type_character_pair():
    assert (
        infer_claim_type(
            subject_type="character",
            object_type="character",
            predicate="trusts",
            evidence_text="Edward did not trust Bella.",
        )
        == "relationship_state"
    )


def test_relation_to_claim_draft_preserves_entity_ids():
    entities = extract_entity_candidates_from_text("Edward did not trust Bella.")
    relations = extract_relation_candidates_from_text(
        "Edward did not trust Bella.",
        pov_character="Isabella Swan",
    )
    draft = relation_to_claim_draft(relations[0], entities)
    assert draft is not None
    assert draft.subject == "Edward"
    assert draft.target in ("Bella", "Bella Swan")
    assert draft.status in ("suggested", "needs_review", "approved")


def test_fastus_debug_includes_stage5_on_extract():
    from app.extraction.extract import extract_claims_from_text

    result = extract_claims_from_text(
        "Charlie was not my father. Edward did not trust Bella.",
        pov_character="Isabella Swan",
    )
    assert result.chunks[0].fastus_claim_draft_count >= 1
    stages = {e.stage for e in result.fastus_events}
    assert "5" in stages
    assert any(e.event == "claim_drafts" for e in result.fastus_events)
