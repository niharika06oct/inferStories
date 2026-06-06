from app.extraction.layer_dedupe import suppress_redundant_structural_claims
from app.extraction.schema import ExtractedClaim


def _claim(**kwargs) -> ExtractedClaim:
    base = dict(
        subject="Bella",
        claim_type="relationship_state",
        predicate="detests",
        target="Forks",
        claim="Bella detests Forks.",
        confidence=0.64,
        canon_level="active",
        evidence="I detested Forks.",
        chunk_index=0,
        generation_origin="structural",
    )
    base.update(kwargs)
    return ExtractedClaim(**base)


def test_suppresses_structural_when_llm_covers_same_fact():
    structural = _claim(generation_origin="structural", confidence=0.64)
    llm = _claim(
        generation_origin="llm",
        predicate="detests",
        target="Forks",
        confidence=0.9,
        evidence="I detested Forks.",
        claim="Bella detests Forks and feels exiled.",
    )
    out, n = suppress_redundant_structural_claims(
        [structural, llm], llm_active=True
    )
    assert n == 1
    assert len(out) == 1
    assert out[0].generation_origin == "llm"


def test_keeps_family_when_llm_active():
    family = _claim(
        generation_origin="family",
        predicate="daughter_of",
        target="Charlie",
        evidence="Charlie is my father.",
    )
    llm = _claim(generation_origin="llm", predicate="loves", target="Phoenix")
    out, n = suppress_redundant_structural_claims(
        [family, llm], llm_active=True
    )
    assert n == 0
    assert len(out) == 2


def test_no_suppression_without_llm_active():
    structural = _claim()
    llm = _claim(generation_origin="llm")
    out, n = suppress_redundant_structural_claims(
        [structural, llm], llm_active=False
    )
    assert n == 0
    assert len(out) == 2
