"""Family and social relationship extraction from prose (POV-aware)."""

from __future__ import annotations

import re

from app.extraction.pov import resolve_narrator_subject
from app.extraction.schema import ExtractedClaim

# Discovered cast anchors from full chapter (canonical_name -> aliases)
CastMap = dict[str, str]


def discover_cast_from_text(text: str) -> CastMap:
    """Map role keys (mom, dad, phil) to canonical character names in this passage."""
    cast: dict[str, str] = {}
    if re.search(r"Renée|Renee", text, re.I):
        cast["mom"] = "Renée" if "Renée" in text else "Renee"
    if re.search(r"\bCharlie\b", text):
        cast["dad"] = "Charlie"
    if re.search(r"\bPhil\b", text):
        cast["phil"] = "Phil"
    if re.search(r"Billy Black", text, re.I):
        cast["billy"] = "Billy Black"
    return cast


def _resolve_family_target(role_key: str, cast: CastMap, fallback: str) -> str:
    return cast.get(role_key, fallback)


def family_extract_chunk(
    text: str,
    chunk_index: int,
    *,
    pov_character: str | None = None,
    cast: CastMap | None = None,
) -> list[ExtractedClaim]:
    # Resolve first-person narrator to the POV character. When POV is unknown we
    # must NOT invent a "Narrator" entity — first-person family claims are skipped.
    narrator = resolve_narrator_subject("I", pov_character)
    cast = cast or discover_cast_from_text(text)
    found: list[ExtractedClaim] = []

    def add(
        subject: str,
        target: str,
        predicate: str,
        claim: str,
        evidence: str,
        confidence: float,
    ) -> None:
        found.append(
            ExtractedClaim(
                subject=subject,
                claim_type="relationship_state",
                predicate=predicate,
                target=target,
                claim=claim,
                confidence=confidence,
                canon_level="active",
                evidence=evidence[:200],
                chunk_index=chunk_index,
                generation_origin="family",
            )
        )

    for m in re.finditer(
        r"\bmy\s+(mother|mom|mum)\b",
        text,
        re.I,
    ):
        if narrator is None:
            continue
        mom = _resolve_family_target("mom", cast, "Mom")
        subj = narrator
        add(
            subj,
            mom,
            "daughter_of",
            f"{subj} is the daughter of {mom}.",
            m.group(0),
            0.78,
        )
        add(
            mom,
            subj,
            "mother_of",
            f"{mom} is the mother of {subj}.",
            m.group(0),
            0.78,
        )

    for m in re.finditer(
        r"\bmy\s+(?:father|dad|pa)(?:\s*,\s*([A-Z][a-z]+))?",
        text,
        re.I,
    ):
        if narrator is None:
            continue
        dad = (m.group(1) or "").strip() or _resolve_family_target("dad", cast, "Dad")
        subj = narrator
        add(subj, dad, "daughter_of", f"{subj} is the daughter of {dad}.", m.group(0), 0.78)
        add(dad, subj, "father_of", f"{dad} is the father of {subj}.", m.group(0), 0.78)

    for m in re.finditer(
        r"\b(?:she|Renée|Renee|my mother)\s+had\s+Phil\b",
        text,
        re.I,
    ):
        mom = _resolve_family_target("mom", cast, "Renée")
        phil = _resolve_family_target("phil", cast, "Phil")
        add(
            mom,
            phil,
            "partner_of",
            f"{mom} is with Phil.",
            m.group(0),
            0.7,
        )

    billy = _resolve_family_target("billy", cast, "Billy Black")
    if (
        re.search(r"\bCharlie\b", text)
        and re.search(r"Billy Black", text, re.I)
        and re.search(r"remember\s+Billy|fishing with us|Billy Black", text, re.I)
    ):
        add(
            "Charlie",
            billy,
            "knows",
            "Charlie knows Billy Black.",
            "Billy Black",
            0.72,
        )

    for m in re.finditer(
        r"\b(?:already\s+)?bought\s+it\s+for\s+you\b",
        text,
        re.I,
    ):
        if narrator is None:
            continue
        subj = narrator
        # Speaker is Charlie in this chapter beat.
        add(
            "Charlie",
            subj,
            "bought_gift_for",
            f"Charlie bought a truck for {subj}.",
            m.group(0),
            0.75,
        )
        add(
            "Charlie",
            subj,
            "cares_for",
            f"Charlie wants {subj} to be happy in Forks.",
            m.group(0),
            0.68,
        )

    for m in re.finditer(
        r"\b(?:He|Charlie)\s+is\s+Police Chief Swan\b",
        text,
        re.I,
    ):
        found.append(
            ExtractedClaim(
                subject="Charlie",
                claim_type="character_trait",
                predicate="is",
                target="Police Chief Swan",
                claim="Charlie is Police Chief Swan in Forks.",
                confidence=0.85,
                canon_level="active",
                evidence=m.group(0)[:200],
                chunk_index=chunk_index,
                generation_origin="family",
            )
        )

    billy = _resolve_family_target("billy", cast, "Billy Black")
    if re.search(r"\bin\s+a\s+wheelchair\b", text, re.I):
        found.append(
            ExtractedClaim(
                subject=billy,
                claim_type="character_state",
                predicate="is",
                target="in a wheelchair",
                claim=f"{billy} is in a wheelchair.",
                confidence=0.8,
                canon_level="active",
                evidence="in a wheelchair",
                chunk_index=chunk_index,
                generation_origin="family",
            )
        )
    if re.search(r"\bcannot\s+drive\s+anymore\b", text, re.I):
        found.append(
            ExtractedClaim(
                subject=billy,
                claim_type="character_state",
                predicate="cannot",
                target="drive",
                claim=f"{billy} cannot drive anymore.",
                confidence=0.78,
                canon_level="active",
                evidence="cannot drive anymore",
                chunk_index=chunk_index,
                generation_origin="family",
            )
        )

    for m in re.finditer(
        r"\bawkward\b.{0,40}\bCharlie\b|\bCharlie\b.{0,40}\bawkward\b",
        text,
        re.I | re.DOTALL,
    ):
        if narrator is None:
            continue
        subj = narrator
        add(
            subj,
            "Charlie",
            "awkward_with",
            f"{subj} and Charlie have an awkward relationship.",
            m.group(0)[:120],
            0.65,
        )

    for m in re.finditer(
        r"\b(?:pleased|genuinely pleased)\b.{0,50}\b(?:coming to live with him|I was coming)\b",
        text,
        re.I | re.DOTALL,
    ):
        if narrator is None:
            continue
        subj = narrator
        add(
            "Charlie",
            subj,
            "cares_for",
            f"Charlie is pleased {subj} is coming to live with him.",
            m.group(0)[:120],
            0.7,
        )

    for m in re.finditer(
        r"\bexiled myself\b.{0,30}\bForks\b|\bto\s+Forks\s+that\s+I\s+now\s+exiled\b",
        text,
        re.I | re.DOTALL,
    ):
        if narrator is None:
            continue
        subj = narrator
        found.append(
            ExtractedClaim(
                subject=subj,
                claim_type="timeline_fact",
                predicate="moving_to",
                target="Forks",
                claim=f"{subj} is moving to Forks.",
                confidence=0.8,
                canon_level="active",
                evidence=m.group(0)[:200],
                chunk_index=chunk_index,
                generation_origin="family",
            )
        )

    return found
