"""Extract structured claims from chapter text (OpenAI or heuristic fallback)."""

from __future__ import annotations

import json
import os
import re

import httpx

from app.extraction.chunking import chunk_chapter_text, word_count
from app.extraction.schema import CLAIM_TYPES, ExtractedClaim, ExtractionResult

CONFIDENCE_AUTO_APPROVE = 0.90
CONFIDENCE_NEEDS_REVIEW = 0.65

_SYSTEM = (
    "You extract structured story memory from fiction prose. "
    "Return only valid JSON matching the schema. "
    "Extract concrete, verifiable claims supported by the text. "
    "Include a short evidence quote from the passage for each claim. "
    "Do not invent facts not implied by the text. "
    f"claim_type must be one of: {', '.join(CLAIM_TYPES)}."
)

_USER_TEMPLATE = """Extract story claims from this fiction passage.

Return JSON:
{{
  "claims": [
    {{
      "subject": "Character name",
      "claim_type": "relationship_state",
      "target": "Other character or entity",
      "claim": "Full sentence describing the fact.",
      "confidence": 0.0-1.0,
      "canon_level": "core|active|soft",
      "evidence": "Short quote from text",
      "chunk_index": {chunk_index}
    }}
  ]
}}

Passage (chunk {chunk_index} of {chunk_total}):
---
{text}
---
"""


def status_for_confidence(confidence: float) -> str:
    if confidence >= CONFIDENCE_AUTO_APPROVE:
        return "approved"
    if confidence >= CONFIDENCE_NEEDS_REVIEW:
        return "needs_review"
    return "suggested"


def _heuristic_extract_chunk(text: str, chunk_index: int) -> list[ExtractedClaim]:
    """Lightweight pattern extraction when no API key (dev/tests)."""
    found: list[ExtractedClaim] = []
    patterns: list[tuple[str, str, str, str, float]] = [
        (
            r"(\w+(?:\s+\w+)?)\s+(?:still\s+)?did not fully trust\s+(\w+(?:\s+\w+)?)",
            "relationship_state",
            "active",
            r"\1 does not fully trust \2.",
            0.88,
        ),
        (
            r"(\w+(?:\s+\w+)?)\s+(?:knew|believed)\s+(?:that\s+)?(\w+(?:\s+\w+)?)\s+would never hurt",
            "belief",
            "active",
            r"\1 believes \2 will not hurt her.",
            0.85,
        ),
        (
            r"(\w+(?:\s+\w+)?)\s+trusts\s+(\w+(?:\s+\w+)?)",
            "relationship_state",
            "active",
            r"\1 trusts \2.",
            0.9,
        ),
        (
            r"(\w+(?:\s+\w+)?)\s+(?:does not trust|distrusts)\s+(\w+(?:\s+\w+)?)",
            "relationship_state",
            "active",
            r"\1 distrusts \2.",
            0.88,
        ),
        (
            r"(\w+(?:\s+\w+)?)\s+cannot be killed",
            "world_rule",
            "core",
            r"\1 cannot be killed.",
            0.92,
        ),
    ]
    for pattern, claim_type, canon, claim_tpl, conf in patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            subj = m.group(1).strip()
            tgt = m.group(2).strip() if m.lastindex and m.lastindex >= 2 else ""
            claim_sentence = claim_tpl.replace(r"\1", subj).replace(r"\2", tgt)
            evidence = m.group(0).strip()[:200]
            if claim_type == "belief":
                ct = "character_state"
            else:
                ct = claim_type
            found.append(
                ExtractedClaim(
                    subject=subj,
                    claim_type=ct,
                    target=tgt,
                    claim=claim_sentence,
                    confidence=conf,
                    canon_level=canon,  # type: ignore[arg-type]
                    evidence=evidence,
                    chunk_index=chunk_index,
                )
            )
    return found


def _openai_extract_chunk(
    text: str, chunk_index: int, chunk_total: int
) -> list[ExtractedClaim]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _heuristic_extract_chunk(text, chunk_index)

    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    prompt = _USER_TEMPLATE.format(
        text=text[:12000],
        chunk_index=chunk_index,
        chunk_total=chunk_total,
    )

    try:
        with httpx.Client(timeout=90.0) as client:
            r = client.post(
                f"{base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "max_tokens": 4000,
                    "temperature": 0.2,
                },
            )
            r.raise_for_status()
            content = (
                r.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            data = json.loads(content)
            raw = data.get("claims", data if isinstance(data, list) else [])
            claims: list[ExtractedClaim] = []
            for item in raw:
                item = dict(item)
                item.setdefault("chunk_index", chunk_index)
                if item.get("claim_type") not in CLAIM_TYPES:
                    # Map close types
                    ct = item.get("claim_type", "character_state")
                    if ct == "belief":
                        item["claim_type"] = "character_state"
                    elif ct not in CLAIM_TYPES:
                        item["claim_type"] = "character_state"
                claims.append(ExtractedClaim.model_validate(item))
            return claims
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError):
        return _heuristic_extract_chunk(text, chunk_index)


def _dedupe_claims(claims: list[ExtractedClaim]) -> list[ExtractedClaim]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[ExtractedClaim] = []
    for c in claims:
        key = (
            c.subject.strip().lower(),
            c.claim_type.strip().lower(),
            (c.target or "").strip().lower(),
            c.claim.strip().lower()[:120],
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def extract_claims_from_text(text: str) -> ExtractionResult:
    chunks, warn = chunk_chapter_text(text)
    all_claims: list[ExtractedClaim] = []
    source = "openai" if os.getenv("OPENAI_API_KEY", "").strip() else "heuristic"
    total = len(chunks)

    for i, chunk in enumerate(chunks):
        if source == "openai":
            all_claims.extend(_openai_extract_chunk(chunk, i, total))
        else:
            all_claims.extend(_heuristic_extract_chunk(chunk, i))

    deduped = _dedupe_claims(all_claims)
    return ExtractionResult(
        claims=deduped,
        source=source,
        chunk_count=total,
        word_count=word_count(text),
    )
