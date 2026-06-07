"""FASTUS Stage 3 - phrase candidate extraction."""

from app.nlp.chapter_parse import is_spacy_available, parse_chunk
from app.nlp.phrase_candidates import extract_phrase_candidates, extract_phrase_candidates_from_text


def test_family_phrase_my_father():
    phrases = extract_phrase_candidates_from_text("Charlie was my father.", 0)
    family = [p for p in phrases if p.phrase_type == "family_phrase"]
    assert family
    assert any("father" in p.phrase_text.lower() for p in family)
    assert family[0].family_relation == "father"
    assert family[0].negated is False


def test_family_phrase_negated_in_denial_sentence():
    phrases = extract_phrase_candidates_from_text(
        "Charlie was not my father.", 0, pov_character="Isabella Swan"
    )
    family = [p for p in phrases if p.phrase_type == "family_phrase"]
    assert family
    assert all(p.negated for p in family)


def test_verb_phrase_with_negation():
    phrases = extract_phrase_candidates_from_text(
        "I did not trust him at all.", 0, pov_character="Isabella Swan"
    )
    verb = [p for p in phrases if p.phrase_type == "verb_phrase"]
    assert verb
    assert any(p.negated for p in verb)
    assert any("trust" in p.head_token.lower() for p in verb)


def test_place_prep_phrase_forks():
    phrases = extract_phrase_candidates_from_text(
        "Bella walked in Forks.", 0
    )
    place = [p for p in phrases if p.phrase_type in ("place_phrase", "prep_phrase")]
    assert any("Forks" in p.phrase_text for p in place)


def test_fastus_debug_includes_stage3_on_extract():
    from app.extraction.extract import extract_claims_from_text

    result = extract_claims_from_text(
        "Charlie was not my father. I did not trust Edward.",
        pov_character="Isabella Swan",
    )
    assert result.chunks[0].fastus_phrase_candidate_count >= 1
    stages = {e.stage for e in result.fastus_events}
    assert "3" in stages
    assert any(e.event == "phrase_candidates" for e in result.fastus_events)


def test_spacy_noun_phrase_when_available():
    if not is_spacy_available():
        return
    parsed = parse_chunk("Edward met Bella in Phoenix.", 0)
    phrases = extract_phrase_candidates(parsed)
    nouns = [p for p in phrases if p.phrase_type == "noun_phrase"]
    assert nouns


def test_state_phrase_uncomfortable_with_edward():
    phrases = extract_phrase_candidates_from_text(
        "Bella was uncomfortable with Edward.", 0, pov_character="Bella"
    )
    state = [p for p in phrases if p.phrase_type == "state_phrase"]
    assert state
    assert any(p.head_token == "uncomfortable" for p in state)
    assert any("Edward" in p.phrase_text for p in state)
    assert all(not p.negated for p in state)


def test_state_phrase_negated_jealous():
    phrases = extract_phrase_candidates_from_text(
        "She was not jealous of Rosalie.", 0, pov_character="Bella"
    )
    state = [p for p in phrases if p.phrase_type == "state_phrase"]
    assert state
    assert any(p.head_token == "jealous" and p.negated for p in state)


def test_extended_family_phrase_stepfather():
    phrases = extract_phrase_candidates_from_text(
        "Charlie was my stepfather.", 0, pov_character="Isabella Swan"
    )
    family = [p for p in phrases if p.phrase_type == "family_phrase"]
    assert any(p.family_relation == "stepfather" for p in family)


def test_extended_family_phrase_father_in_law():
    phrases = extract_phrase_candidates_from_text(
        "He was my father-in-law.", 0, pov_character="Bella"
    )
    family = [p for p in phrases if p.phrase_type == "family_phrase"]
    assert any(p.family_relation == "father-in-law" for p in family)
