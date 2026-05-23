"""POV-aware subject resolution for first-person chapters."""

from app.extraction.extract import extract_claims_from_text
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


def test_extract_claims_passes_pov():
    text = "I loved Niharika in the garden."
    result = extract_claims_from_text(text, pov_character="Elena")
    assert any(c.subject == "Elena" for c in result.claims)
