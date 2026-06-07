"""Locate claim evidence in chapter text for continuity scroll targets."""

from __future__ import annotations

from app.models import Claim


def continuity_anchor_in_scene(
    scene_text: str, claim: Claim
) -> tuple[int, str, int]:
    """
    Return (text_offset, anchor_text, anchor_length) for highlighting.

    Prefer the claim's evidence quote; never fall back to subject name alone
    (that often matches the first line of the chapter).
    """
    text = scene_text or ""
    if not text.strip():
        return 0, "", 0

    evidence = (claim.evidence_text or "").strip()
    anchor = evidence
    if not anchor:
        anchor = (claim.claim_text or "").strip()[:240]

    if not anchor:
        obj = (claim.claim_object or "").strip()
        if len(obj) >= 3:
            anchor = obj
        else:
            return 0, "", 0

    anchor_stored = anchor[:500]
    idx = text.lower().find(anchor_stored.lower())
    if idx < 0 and len(anchor_stored) > 48:
        short = anchor_stored[:48].strip()
        idx = text.lower().find(short.lower())
        if idx >= 0:
            anchor_stored = short

    if idx < 0:
        obj = (claim.claim_object or "").strip()
        if len(obj) >= 3 and obj.lower() not in anchor_stored.lower():
            oidx = text.lower().find(obj.lower())
            if oidx >= 0:
                idx = oidx
                anchor_stored = obj

    if idx < 0:
        # Store anchor for client-side search only; offset 0 would mis-highlight chapter start.
        return 0, anchor_stored, 0

    length = min(len(anchor_stored), 200, max(1, len(text) - idx))
    return idx, anchor_stored, length


def evidence_offset_in_scene(scene_text: str, claim: Claim) -> int:
    """Character offset in scene_text; 0 if anchor not found."""
    offset, _, _ = continuity_anchor_in_scene(scene_text, claim)
    return offset


def claim_anchored_in_scene(scene_text: str, claim: Claim) -> bool:
    """
    True when the claim's evidence or claim_text still appears in the chapter.

    Stricter than continuity_anchor_in_scene: does not fall back to object-name
    alone, so a removed sentence does not leave a stale loves/trusts row alive.
    """
    text = (scene_text or "").strip()
    if not text:
        return False
    lowered = text.lower()
    for field in (claim.evidence_text, claim.claim_text):
        quote = (field or "").strip()
        if not quote:
            continue
        anchor = quote[:500]
        if lowered.find(anchor.lower()) >= 0:
            return True
        if len(anchor) > 48:
            short = anchor[:48].strip()
            if lowered.find(short.lower()) >= 0:
                return True
    return False
