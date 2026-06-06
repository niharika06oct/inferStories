"""POV-aware subject resolution for first-person chapters."""

from app.extraction.extract import extract_claims_from_text
from app.extraction.family import family_extract_chunk
from app.extraction.pov import resolve_narrator_subject
from app.extraction.structural import structural_extract_chunk


def test_resolve_narrator_subject_with_pov():
    assert resolve_narrator_subject("I", "Marcus") == "Marcus"
    assert resolve_narrator_subject("way I", "Marcus") == "Marcus"
    assert resolve_narrator_subject("Asha", "Marcus") == "Asha"


def test_resolve_narrator_subject_without_pov_skips_i():
    assert resolve_narrator_subject("I", None) is None
    assert resolve_narrator_subject("way I", None) is None


def test_structural_first_person_loved_with_pov():
    text = "In a way I loved Niharika at dawn."
    claims = structural_extract_chunk(text, 0, pov_character="Marcus")
    assert len(claims) >= 1
    assert any(c.subject == "Marcus" and "Niharika" in c.target for c in claims)
    assert not any("way" in c.subject.lower() for c in claims)


def test_structural_claim_carries_generation_origin():
    claims = structural_extract_chunk(
        "I loved Phoenix.", 0, pov_character="Bella"
    )
    assert claims
    assert all(c.generation_origin == "structural" for c in claims)


def test_structural_love_captures_full_object_phrase():
    text = "I love getting full access to her."
    claims = structural_extract_chunk(text, 0, pov_character="Abhilash")
    love = [c for c in claims if c.predicate == "loves"]
    assert len(love) == 1
    assert "access" in love[0].target.lower()
    assert love[0].target.lower() != "getting full"
    assert "access" in love[0].claim.lower()
    assert "access" in love[0].evidence.lower()
    assert love[0].target.lower() != "getting full"


def test_extract_claims_passes_pov():
    text = "I loved Niharika in the garden."
    result = extract_claims_from_text(text, pov_character="Elena")
    assert any(c.subject == "Elena" for c in result.claims)


def test_family_without_pov_never_emits_narrator():
    text = "I hugged my mother and my father in the kitchen."
    claims = family_extract_chunk(text, 0, pov_character=None)
    # Without a POV character, first-person family claims are dropped, not
    # attributed to a fabricated "Narrator".
    assert not any(c.subject == "Narrator" or c.target == "Narrator" for c in claims)
    assert not any(c.subject == "Narrator" for c in claims)


def test_family_with_pov_uses_pov_name():
    text = "I hugged my mother in the kitchen."
    claims = family_extract_chunk(text, 0, pov_character="Bella")
    assert claims
    assert any(c.subject == "Bella" or c.target == "Bella" for c in claims)
    assert not any(c.subject == "Narrator" or c.target == "Narrator" for c in claims)


def test_extract_without_pov_drops_first_person_claims():
    text = "I loved Phoenix and I hugged my mother."
    result = extract_claims_from_text(text, pov_character=None)
    assert not any(
        c.subject in ("Narrator", "I", "me") or c.target in ("Narrator",)
        for c in result.claims
    )
