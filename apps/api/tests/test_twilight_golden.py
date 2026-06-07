"""
Twilight excerpt — current behavior vs desired north-star behavior.

Run:
  pytest tests/test_twilight_golden.py -v
  pytest tests/test_twilight_golden.py -v -m desired_behavior  # xfail goals
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.extraction.extract import extract_claims_from_text

FIXTURE = Path(__file__).parent / "fixtures" / "twilight_excerpt.txt"
POV = "Bella"


def _load() -> str:
    p = FIXTURE
    if not p.is_file():
        p = Path(__file__).parent / "fixtures" / "twilight_chapter1_opening.txt"
    return p.read_text(encoding="utf-8")


def _extract(text: str):
    return extract_claims_from_text(text, pov_character=POV)


def _has_evidence(claims, fragment: str) -> bool:
    frag = fragment.lower()
    return any(frag in (c.evidence or "").lower() for c in claims)


def _has_claim_matching(claims, *, evidence: str, predicate: str | None = None) -> bool:
    ev = evidence.lower()
    for c in claims:
        if ev not in (c.evidence or "").lower():
            continue
        if predicate and c.predicate.replace("_", " ") != predicate.replace("_", " "):
            if c.predicate != predicate:
                continue
        return True
    return False


@pytest.fixture
def chapter() -> str:
    return _load()


@pytest.fixture
def claims(chapter: str):
    import os

    old = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = ""
    try:
        from app.extraction import extract as extract_mod

        def _no_llm(*_a, **_k):
            return [], False, False, False, 0, False, 0

        import pytest as pt

        mp = pt.MonkeyPatch()
        mp.setattr(extract_mod, "_llm_extract_chunk", _no_llm)
        result = _extract(chapter)
        mp.undo()
        return result.claims
    finally:
        if old is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = old


# --- Current behavior (must pass) ---


class TestTwilightCurrentBehavior:
    def test_detested_or_distaste_forks(self, claims):
        assert _has_evidence(claims, "detested forks") or _has_evidence(
            claims, "distaste for forks"
        )

    def test_loves_phoenix(self, claims):
        assert _has_evidence(claims, "loved phoenix")

    def test_loves_sun(self, claims):
        assert any("loved the sun" in (c.evidence or "").lower() for c in claims)

    def test_love_you_mom(self, claims):
        assert _has_evidence(claims, "love you") and any(
            "mom" in (c.target or "").lower() for c in claims
        )

    def test_no_junk_said_to_me(self, claims):
        assert not _has_evidence(claims, "my mom said to me")

    def test_no_junk_stared_at_her_wide(self, claims):
        assert not _has_evidence(claims, "stared at her wide")

    def test_family_daughter_of_mother(self, claims):
        assert any(
            c.predicate == "daughter_of" and "mom" in (c.target or "").lower()
            or c.predicate == "daughter_of"
            and "renée" in (c.target or "").lower()
            for c in claims
        )

    def test_family_father_charlie(self, claims):
        assert any(
            c.predicate in ("daughter_of", "father_of")
            and "charlie" in ((c.target or "") + (c.subject or "")).lower()
            for c in claims
        )

    def test_charlie_knows_billy(self, claims):
        assert any(
            c.predicate == "knows"
            and "billy" in ((c.target or "") + (c.subject or "")).lower()
            for c in claims
        )


# --- Desired north star (xfail until LLM + richer rules close the gap) ---


@pytest.mark.desired_behavior
class TestTwilightDesiredBehavior:
    @pytest.mark.xfail(reason="north star: full claim coverage", strict=False)
    def test_all_desired_claims_present(self, claims):
        desired_evidence = [
            "loved phoenix",
            "detest",
            "loved the sun",
            "exiled",
            "daughter_of",
            "father_of",
            "mother_of",
            "bought",
            "wheelchair",
            "cannot drive",
            "police chief",
            "awkward",
            "pleased",
        ]
        missing = [d for d in desired_evidence if not _has_evidence(claims, d)]
        assert not missing, f"missing evidence hints: {missing}"

    @pytest.mark.xfail(reason="north star: graph edge set", strict=False)
    def test_desired_graph_edge_predicates(self, claims):
        preds = {c.predicate for c in claims if c.claim_type == "relationship_state"}
        for needed in (
            "mother_of",
            "father_of",
            "daughter_of",
            "knows",
            "partner_of",
            "bought_gift_for",
        ):
            assert needed in preds
