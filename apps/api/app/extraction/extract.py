"""Extract structured claims from chapter text (layered: structural → OpenAI → heuristic)."""

from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.extraction.chunking import chunk_chapter_text, word_count
from app.extraction.errors import ExtractionAPIError
from app.extraction.schema import (
    CLAIM_TYPES,
    ChunkExtractionDebug,
    ExtractedClaim,
    ExtractionResult,
    FastusDebugEventOut,
)
from app.nlp.chapter_parse import is_spacy_available, parse_chunk
from app.nlp.entity_candidates import extract_entity_candidates
from app.nlp.phrase_candidates import extract_phrase_candidates
from app.nlp.relation_candidates import extract_relation_candidates
from app.extraction.semantic_patterns import (
    ClaimDraft,
    claim_draft_to_extracted,
    relations_to_claim_drafts,
)
from app.extraction.llm_refine import drafts_to_extracted_passthrough, refine_claim_drafts
from app.extraction.llm_recall import (
    RecallResult,
    llm_first_enabled,
    llm_refine_enabled,
    recall_claims_from_chunk,
)
from app.extraction.evidence_anchor import (
    apply_evidence_anchoring,
    filter_unanchored_if_strict,
)
from app.extraction.source_dedupe import merge_source_claims
from app.location_compatibility import refine_extracted_location_claim
from app.nlp.fastus_debug import emit, log_stage
from app.extraction.llm_refine import _legacy_extract_enabled
from app.extraction.pov import normalize_claims_for_pov
from app.extraction.claim_filter import filter_extracted_claims
from app.extraction.family import discover_cast_from_text, family_extract_chunk
from app.extraction.layer_dedupe import (
    filter_redundant_llm_claims,
    suppress_redundant_structural_claims,
    _predicate_family,
    _structural_redundant_with_llm,
)
from app.extraction.structural import detect_entities, structural_extract_chunk

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
      "predicate": "Semantic verb e.g. distrusts, trusts, loves (not the claim_type slug)",
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
{pov_note}
"""


def status_for_confidence(confidence: float) -> str:
    if confidence >= CONFIDENCE_AUTO_APPROVE:
        return "approved"
    if confidence >= CONFIDENCE_NEEDS_REVIEW:
        return "needs_review"
    return "suggested"


def resolve_extracted_status(claim: ExtractedClaim) -> str:
    """Prefer pipeline review_status (anchoring) over raw confidence tiers."""
    if claim.review_status:
        return claim.review_status
    return status_for_confidence(claim.confidence)


def _heuristic_extract_chunk(text: str, chunk_index: int) -> list[ExtractedClaim]:
    """Lightweight pattern extraction when no API key (dev/tests)."""
    found: list[ExtractedClaim] = []
    patterns: list[tuple[str, str, str, str, str, float]] = [
        (
            r"(\w+(?:\s+\w+)?)\s+(?:still\s+)?did not fully trust\s+(\w+(?:\s+\w+)?)",
            "relationship_state",
            "distrusts",
            "active",
            r"\1 does not fully trust \2.",
            0.88,
        ),
        (
            r"(\w+(?:\s+\w+)?)\s+(?:knew|believed)\s+(?:that\s+)?(\w+(?:\s+\w+)?)\s+would never hurt",
            "character_state",
            "believes",
            "active",
            r"\1 believes \2 will not hurt her.",
            0.85,
        ),
        (
            r"(\w+(?:\s+\w+)?)\s+trusts\s+(\w+(?:\s+\w+)?)",
            "relationship_state",
            "trusts",
            "active",
            r"\1 trusts \2.",
            0.9,
        ),
        (
            r"(\w+(?:\s+\w+)?)\s+(?:does not trust|distrusts)\s+(\w+(?:\s+\w+)?)",
            "relationship_state",
            "distrusts",
            "active",
            r"\1 distrusts \2.",
            0.88,
        ),
        (
            r"(\w+(?:\s+\w+)?)\s+cannot be killed",
            "world_rule",
            "cannot_be_killed",
            "core",
            r"\1 cannot be killed.",
            0.92,
        ),
    ]
    for pattern, claim_type, predicate, canon, claim_tpl, conf in patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            subj = m.group(1).strip()
            tgt = m.group(2).strip() if m.lastindex and m.lastindex >= 2 else ""
            claim_sentence = claim_tpl.replace(r"\1", subj).replace(r"\2", tgt)
            evidence = m.group(0).strip()[:200]
            found.append(
                ExtractedClaim(
                    subject=subj,
                    claim_type=claim_type,
                    predicate=predicate,
                    target=tgt,
                    claim=claim_sentence,
                    confidence=conf,
                    canon_level=canon,  # type: ignore[arg-type]
                    evidence=evidence,
                    chunk_index=chunk_index,
                    generation_origin="heuristic",
                )
            )
    return found


def _pov_note(pov_character: str | None) -> str:
    pov = pov_character.strip() if pov_character else ""
    if not pov:
        return ""
    return (
        f"\nNarrator POV: {pov}. "
        "Treat unquoted first-person I/me/myself in this passage as referring to this character "
        f"({pov}) in claim subjects."
    )


def _openai_extract_chunk(
    text: str,
    chunk_index: int,
    chunk_total: int,
    *,
    pov_character: str | None = None,
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
        pov_note=_pov_note(pov_character),
    )

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
                ct = item.get("claim_type", "character_state")
                if ct == "belief":
                    item["claim_type"] = "character_state"
                elif ct not in CLAIM_TYPES:
                    item["claim_type"] = "character_state"
            claims.append(
                ExtractedClaim.model_validate(item).model_copy(
                    update={"generation_origin": "llm"}
                )
            )
        return claims


def _llm_extract_chunk(
    text: str,
    chunk_index: int,
    chunk_total: int,
    *,
    has_key: bool,
    pov_character: str | None = None,
    claim_drafts: list[ClaimDraft] | None = None,
) -> tuple[list[ExtractedClaim], bool, bool, bool, int, bool, int]:
    """
    FASTUS Stage 6: refine claim drafts via LLM (or passthrough).

    Returns claims, openai_attempted, openai_ok, fallback_used,
    rejected_count, cache_hit, refined_count.
    """
    drafts = claim_drafts or []

    def _legacy_full_extract() -> list[ExtractedClaim]:
        if not has_key:
            return _heuristic_extract_chunk(text, chunk_index)
        return _openai_extract_chunk(
            text, chunk_index, chunk_total, pov_character=pov_character
        )

    if not has_key:
        if drafts:
            claims = drafts_to_extracted_passthrough(drafts)
        else:
            claims = _heuristic_extract_chunk(text, chunk_index)
        claims = normalize_claims_for_pov(claims, pov_character)
        return (
            claims,
            False,
            False,
            False,
            0,
            False,
            len(claims),
        )

    try:
        result = refine_claim_drafts(
            drafts,
            text,
            chunk_index,
            chunk_total,
            pov_character=pov_character,
            legacy_extract_fn=_legacy_full_extract,
        )
        claims = normalize_claims_for_pov(result.claims, pov_character)
        openai_ok = result.attempted and result.ok and not result.fallback_used
        return (
            claims,
            result.attempted,
            openai_ok,
            result.fallback_used,
            result.rejected_count,
            result.cache_hit,
            len(claims),
        )
    except ExtractionAPIError:
        raise


def _dedupe_claims(claims: list[ExtractedClaim]) -> list[ExtractedClaim]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[ExtractedClaim] = []
    for c in claims:
        key = (
            c.subject.strip().lower(),
            c.claim_type.strip().lower(),
            (c.predicate or "").strip().lower(),
            (c.target or "").strip().lower(),
            c.claim.strip().lower()[:120],
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def extract_claims_from_text(
    text: str, *, pov_character: str | None = None
) -> ExtractionResult:
    started = time.perf_counter()
    chunks, warn = chunk_chapter_text(text)
    all_claims: list[ExtractedClaim] = []
    has_key = bool(os.getenv("OPENAI_API_KEY", "").strip())
    total = len(chunks)
    api_error: str | None = None
    any_openai = False
    any_fallback = False
    any_fastus_llm = False
    chunk_debug: list[ChunkExtractionDebug] = []
    all_entities: set[str] = set()
    scene_fastus_events: list[FastusDebugEventOut] = []
    stage0_negated = 0
    spacy_ok = is_spacy_available()

    emit(
        scene_fastus_events,
        stage="meta",
        event="pipeline",
        message="FASTUS shadow pipeline active (stages 0–9 instrumented)",
        detail={"spacy_available": spacy_ok},
        max_events=120,
    )

    for stage_num in ("1", "2", "3", "4", "5", "6"):
        log_stage(
            scene_fastus_events,
            stage=stage_num,
            lifecycle="begin",
            message=f"Entering stage {stage_num}",
            max_events=120,
        )

    cast = discover_cast_from_text(text)
    total_tokens = 0
    total_entity_candidates = 0
    total_phrase_candidates = 0
    total_relation_candidates = 0
    total_claim_drafts = 0
    total_llm_output = 0
    chunks_with_drafts = 0
    chunks_without_drafts = 0
    any_openai_refine = False
    any_passthrough = False
    use_llm_first = llm_first_enabled() and has_key
    total_llm_recall = 0
    total_fastus_extracted = 0
    total_regex_claims = 0
    total_after_dedupe = 0
    total_anchored = 0
    total_unanchored = 0
    total_needs_review_pipeline = 0

    if use_llm_first:
        log_stage(
            scene_fastus_events,
            stage="6a",
            lifecycle="begin",
            message="LLM recall for major story claims (FASTUS_LLM_FIRST=1)",
            max_events=120,
        )

    for i, chunk in enumerate(chunks):
        chunk_fastus_events: list[FastusDebugEventOut] = []

        # --- FASTUS Stage 1: token parse (shadow; does not replace regex extractor yet) ---
        parsed = parse_chunk(chunk, i)
        emit(
            chunk_fastus_events,
            stage="1",
            event="parse",
            message=(
                f"Parsed chunk {i}: {len(parsed.tokens)} tokens, "
                f"{len(parsed.sentences)} sentences"
            ),
            detail={
                "has_dependencies": parsed.has_dependencies,
                "chunk_index": i,
            },
        )

        # --- FASTUS Stage 2: entity candidates (shadow) ---
        entity_candidates = extract_entity_candidates(parsed, pov_character=pov_character)
        emit(
            chunk_fastus_events,
            stage="2",
            event="entity_candidates",
            message=f"Found {len(entity_candidates)} entity candidate(s)",
            detail={"chunk_index": i},
        )
        for ec in entity_candidates[:12]:
            emit(
                chunk_fastus_events,
                stage="2",
                event="entity_candidate",
                message=(
                    f"{ec.surface_text} → {ec.entity_type_guess} "
                    f"({ec.source}, conf={ec.confidence:.2f})"
                ),
                detail={
                    "offset": f"{ec.start_char}-{ec.end_char}",
                    "spacy_label": ec.spacy_label or "",
                    "registry_id": ec.registry_entity_id or "",
                },
            )

        # --- FASTUS Stage 3: phrase candidates (shadow) ---
        phrase_candidates = extract_phrase_candidates(
            parsed, pov_character=pov_character
        )
        emit(
            chunk_fastus_events,
            stage="3",
            event="phrase_candidates",
            message=f"Found {len(phrase_candidates)} phrase candidate(s)",
            detail={"chunk_index": i},
        )
        for pc in phrase_candidates[:12]:
            emit(
                chunk_fastus_events,
                stage="3",
                event="phrase_candidate",
                message=(
                    f"{pc.phrase_type}: \"{pc.phrase_text}\" "
                    f"(head={pc.head_token}, negated={pc.negated})"
                ),
                detail={
                    "offset": f"{pc.start_char}-{pc.end_char}",
                    "family_relation": pc.family_relation or "",
                },
            )

        # --- FASTUS Stage 4: relation candidates (shadow) ---
        relation_candidates = extract_relation_candidates(
            parsed,
            entity_candidates,
            phrase_candidates,
            pov_character=pov_character,
            cast=cast,
        )
        emit(
            chunk_fastus_events,
            stage="4",
            event="relation_candidates",
            message=f"Found {len(relation_candidates)} relation candidate(s)",
            detail={"chunk_index": i},
        )
        for rc in relation_candidates[:12]:
            pol = "true" if rc.polarity else "false"
            emit(
                chunk_fastus_events,
                stage="4",
                event="relation_candidate",
                message=(
                    f"{rc.subject_surface} {rc.predicate_normalized} "
                    f"{rc.object_surface} (polarity={pol}, origin={rc.extraction_origin})"
                ),
                detail={
                    "offset": f"{rc.start_char}-{rc.end_char}",
                    "confidence": f"{rc.confidence:.2f}",
                    "evidence": rc.evidence_text[:80],
                },
            )

        # --- FASTUS Stage 5: semantic patterns → claim drafts (shadow) ---
        claim_drafts = relations_to_claim_drafts(
            relation_candidates,
            entity_candidates,
        )
        total_tokens += len(parsed.tokens)
        total_entity_candidates += len(entity_candidates)
        total_phrase_candidates += len(phrase_candidates)
        total_relation_candidates += len(relation_candidates)
        total_claim_drafts += len(claim_drafts)
        if claim_drafts:
            chunks_with_drafts += 1
        else:
            chunks_without_drafts += 1

        emit(
            chunk_fastus_events,
            stage="5",
            event="claim_drafts",
            message=f"Mapped {len(claim_drafts)} claim draft(s) from relations",
            detail={"chunk_index": i},
        )
        for cd in claim_drafts[:12]:
            pol = "true" if cd.polarity else "false"
            emit(
                chunk_fastus_events,
                stage="5",
                event="claim_draft",
                message=(
                    f"[{cd.claim_type}] {cd.claim} "
                    f"(status={cd.status}, polarity={pol})"
                ),
                detail={
                    "predicate": cd.predicate,
                    "confidence": f"{cd.confidence:.2f}",
                    "offset": f"{cd.start_char}-{cd.end_char}",
                },
            )

        entities = detect_entities(chunk)
        all_entities.update(entities)

        known_entity_names = sorted(
            {*(cast or []), *(entities or []), *(ec.surface_text for ec in entity_candidates[:24])}
        )

        llm_recall_count = 0
        fastus_extracted_count = 0
        regex_claim_count = 0
        after_dedupe_count = 0
        chunk_anchored = 0
        chunk_unanchored = 0
        recall_cache_hit = False

        structural: list[ExtractedClaim] = []
        family: list[ExtractedClaim] = []
        llm_claims: list[ExtractedClaim] = []
        openai_attempted = False
        openai_ok = False
        fallback_used = False
        llm_rejected = 0
        llm_cache_hit = False
        llm_refined_count = 0

        if use_llm_first:
            with ThreadPoolExecutor(max_workers=2) as pool:
                recall_future = pool.submit(
                    recall_claims_from_chunk,
                    chunk,
                    i,
                    total,
                    pov_character=pov_character,
                    known_entities=known_entity_names,
                )
                rules_future = pool.submit(
                    lambda: (
                        structural_extract_chunk(
                            chunk, i, pov_character=pov_character
                        ),
                        family_extract_chunk(
                            chunk, i, pov_character=pov_character, cast=cast
                        ),
                    )
                )
                try:
                    recall_result = recall_future.result()
                except ExtractionAPIError as exc:
                    api_error = str(exc)
                    recall_result = RecallResult(claims=[], attempted=True, ok=False)
                structural, family = rules_future.result()

            if recall_result.attempted:
                any_openai = True
                openai_attempted = True
            if recall_result.ok:
                openai_ok = True
            recall_cache_hit = recall_result.cache_hit
            llm_recall_count = len(recall_result.claims)
            total_llm_recall += llm_recall_count

            emit(
                chunk_fastus_events,
                stage="6a",
                event="llm_recall",
                message=f"LLM recall returned {llm_recall_count} claim(s)",
                detail={
                    "chunk_index": i,
                    "cache_hit": "true" if recall_cache_hit else "false",
                    "raw": recall_result.raw_count,
                },
            )
            for claim in recall_result.claims[:8]:
                emit(
                    chunk_fastus_events,
                    stage="6a",
                    event="llm_recall_claim",
                    message=f"[{claim.claim_type}] {claim.claim}",
                    detail={
                        "predicate": claim.predicate,
                        "polarity": "true" if claim.polarity else "false",
                        "importance": claim.importance,
                    },
                )

            fastus_extracted = [
                apply_evidence_anchoring(
                    claim_draft_to_extracted(d),
                    chunk,
                    importance="medium",
                )
                for d in claim_drafts
            ]
            fastus_extracted_count = len(fastus_extracted)
            total_fastus_extracted += fastus_extracted_count

            recall_anchored = [
                apply_evidence_anchoring(c, chunk, importance=c.importance)
                for c in recall_result.claims
            ]
            regex_anchored = [
                apply_evidence_anchoring(c, chunk) for c in structural + family
            ]
            regex_claim_count = len(regex_anchored)
            total_regex_claims += regex_claim_count

            unioned = merge_source_claims(
                regex_anchored + fastus_extracted + recall_anchored
            )
            unioned = [refine_extracted_location_claim(c) for c in unioned]
            unioned, strict_dropped = filter_unanchored_if_strict(unioned)
            after_dedupe_count = len(unioned)
            total_after_dedupe += after_dedupe_count
            chunk_anchored = sum(1 for c in unioned if c.anchored)
            chunk_unanchored = sum(1 for c in unioned if c.anchored is False)
            total_anchored += chunk_anchored
            total_unanchored += chunk_unanchored
            total_needs_review_pipeline += sum(
                1 for c in unioned if resolve_extracted_status(c) == "needs_review"
            )

            emit(
                chunk_fastus_events,
                stage="6a",
                event="union_dedupe",
                message=(
                    f"Union: recall={llm_recall_count} fastus={fastus_extracted_count} "
                    f"regex={regex_claim_count} → {after_dedupe_count} after dedupe"
                ),
                detail={
                    "anchored": chunk_anchored,
                    "unanchored": chunk_unanchored,
                    "strict_dropped": strict_dropped,
                },
            )

            llm_claims = []
            llm_refined_count = 0
            all_claims.extend(unioned)
        else:
            structural = structural_extract_chunk(chunk, i, pov_character=pov_character)
            family = family_extract_chunk(
                chunk, i, pov_character=pov_character, cast=cast
            )

            try:
                (
                    llm_claims,
                    openai_attempted,
                    openai_ok,
                    fallback_used,
                    llm_rejected,
                    llm_cache_hit,
                    llm_refined_count,
                ) = _llm_extract_chunk(
                    chunk,
                    i,
                    total,
                    has_key=has_key,
                    pov_character=pov_character,
                    claim_drafts=claim_drafts,
                )
            except ExtractionAPIError as exc:
                api_error = str(exc)
                llm_claims = normalize_claims_for_pov(
                    _heuristic_extract_chunk(chunk, i), pov_character
                )
                openai_attempted = has_key
                openai_ok = False
                fallback_used = True

            emit(
                chunk_fastus_events,
                stage="6",
                event="llm_refine",
                message=(
                    f"LLM refined {llm_refined_count} claim(s) from "
                    f"{len(claim_drafts)} draft(s)"
                    + (" (cache hit)" if llm_cache_hit else "")
                ),
                detail={
                    "chunk_index": i,
                    "rejected": llm_rejected,
                    "cache_hit": "true" if llm_cache_hit else "false",
                    "fallback": "true" if fallback_used else "false",
                },
            )
            for claim in llm_claims[:8]:
                emit(
                    chunk_fastus_events,
                    stage="6",
                    event="llm_refined_claim",
                    message=f"[{claim.claim_type}] {claim.claim}",
                    detail={
                        "predicate": claim.predicate,
                        "polarity": "true" if claim.polarity else "false",
                        "confidence": f"{claim.confidence:.2f}",
                    },
                )

            if not openai_ok and llm_claims:
                kept_structural: list[ExtractedClaim] = []
                boosted_llm: list[ExtractedClaim] = []
                for llm in llm_claims:
                    replaces = [
                        s
                        for s in structural
                        if _structural_redundant_with_llm(s, llm)
                    ]
                    if replaces and _predicate_family(llm.predicate) == "trust":
                        llm = llm.model_copy(
                            update={"confidence": max(llm.confidence, 0.9)}
                        )
                    boosted_llm.append(llm)
                for s in structural:
                    if not any(
                        _structural_redundant_with_llm(s, llm) for llm in boosted_llm
                    ):
                        kept_structural.append(s)
                llm_claims = boosted_llm
                structural = kept_structural
                any_fastus_llm = True
                llm_refined_count = len(llm_claims)
            elif openai_ok and llm_claims:
                llm_claims = filter_redundant_llm_claims(
                    llm_claims, structural + family
                )
                llm_refined_count = len(llm_claims)

            total_llm_output += len(llm_claims)
            if openai_ok:
                any_openai_refine = True
            elif llm_claims and claim_drafts:
                any_passthrough = True

            any_openai = any_openai or openai_attempted
            any_fallback = any_fallback or fallback_used
            all_claims.extend(structural)
            all_claims.extend(family)
            all_claims.extend(llm_claims)

        # --- FASTUS Stage 0: polarity on rule extractions ---
        for c in structural + family:
            if not c.polarity:
                stage0_negated += 1
                emit(
                    chunk_fastus_events,
                    stage="0",
                    event="polarity",
                    message=(
                        f"Negated claim from {c.generation_origin}: "
                        f"{c.subject} {c.predicate} {c.target}"
                    ),
                    detail={
                        "evidence": (c.evidence or "")[:120],
                        "polarity": "false",
                    },
                )

        chunk_debug.append(
            ChunkExtractionDebug(
                chunk_index=i,
                word_count=len(chunk.split()),
                openai_attempted=openai_attempted,
                openai_ok=openai_ok,
                fallback_used=fallback_used,
                structural_claims=len(structural),
                llm_claims=len(llm_claims),
                entities=entities,
                fastus_token_count=len(parsed.tokens),
                fastus_sentence_count=len(parsed.sentences),
                fastus_has_dependencies=parsed.has_dependencies,
                fastus_entity_candidate_count=len(entity_candidates),
                fastus_phrase_candidate_count=len(phrase_candidates),
                fastus_relation_candidate_count=len(relation_candidates),
                fastus_claim_draft_count=len(claim_drafts),
                fastus_llm_refined_count=llm_refined_count,
                fastus_llm_rejected_count=llm_rejected,
                fastus_llm_cache_hit=llm_cache_hit or recall_cache_hit,
                llm_recall_count=llm_recall_count,
                fastus_extracted_count=fastus_extracted_count,
                regex_claim_count=regex_claim_count,
                after_dedupe_count=after_dedupe_count,
                anchored_count=chunk_anchored,
                unanchored_count=chunk_unanchored,
                fastus_events=chunk_fastus_events,
            )
        )
        scene_fastus_events.extend(chunk_fastus_events)

    if use_llm_first:
        log_stage(
            scene_fastus_events,
            stage="6a",
            lifecycle="complete",
            message=(
                f"LLM recall {total_llm_recall} · FASTUS {total_fastus_extracted} · "
                f"regex {total_regex_claims} → {total_after_dedupe} after dedupe"
            ),
            detail={
                "anchored": total_anchored,
                "unanchored": total_unanchored,
                "needs_review": total_needs_review_pipeline,
            },
            max_events=120,
        )

    log_stage(
        scene_fastus_events,
        stage="1",
        lifecycle="complete",
        message=f"Parsed {total} chunk(s)",
        detail={
            "spacy_available": spacy_ok,
            "total_tokens": total_tokens,
        },
        max_events=120,
    )
    log_stage(
        scene_fastus_events,
        stage="2",
        lifecycle="complete",
        message=f"Collected {total_entity_candidates} entity candidate(s)",
        detail={"chunks": total},
        max_events=120,
    )
    log_stage(
        scene_fastus_events,
        stage="3",
        lifecycle="complete",
        message=f"Collected {total_phrase_candidates} phrase candidate(s)",
        max_events=120,
    )
    log_stage(
        scene_fastus_events,
        stage="4",
        lifecycle="complete",
        message=f"Collected {total_relation_candidates} relation candidate(s)",
        max_events=120,
    )
    if total_claim_drafts == 0:
        log_stage(
            scene_fastus_events,
            stage="5",
            lifecycle="skip",
            message="No claim drafts produced from relation candidates",
            detail={"chunks_without_relations": chunks_without_drafts},
            max_events=120,
        )
    else:
        log_stage(
            scene_fastus_events,
            stage="5",
            lifecycle="complete",
            message=f"Mapped {total_claim_drafts} claim draft(s)",
            detail={"chunks_with_drafts": chunks_with_drafts},
            max_events=120,
        )

    if use_llm_first and not llm_refine_enabled():
        log_stage(
            scene_fastus_events,
            stage="6",
            lifecycle="skip",
            message="Stage 6 refine skipped (FASTUS_LLM_FIRST + FASTUS_LLM_REFINE=0)",
            detail={"mode": "llm_recall_first"},
            max_events=120,
        )
    elif total_claim_drafts == 0:
        if use_llm_first:
            pass
        elif has_key and _legacy_extract_enabled():
            log_stage(
                scene_fastus_events,
                stage="6",
                lifecycle="complete",
                message="No drafts; FASTUS_LLM_LEGACY full-chunk extract used",
                detail={"openai_key": "set"},
                max_events=120,
            )
        else:
            log_stage(
                scene_fastus_events,
                stage="6",
                lifecycle="skip",
                message=(
                    "No claim drafts — LLM refine did not run "
                    "(set FASTUS_LLM_LEGACY=1 for legacy full-chunk extract)"
                ),
                detail={"openai_key": "set" if has_key else "missing"},
                max_events=120,
            )
    elif not has_key:
        log_stage(
            scene_fastus_events,
            stage="6",
            lifecycle="complete",
            message=f"Passthrough {total_llm_output} draft(s) without OpenAI key",
            detail={"mode": "passthrough"},
            max_events=120,
        )
    elif any_openai_refine:
        log_stage(
            scene_fastus_events,
            stage="6",
            lifecycle="complete",
            message=f"OpenAI refined {total_llm_output} claim(s) from {total_claim_drafts} draft(s)",
            detail={"mode": "refine"},
            max_events=120,
        )
    elif any_passthrough:
        log_stage(
            scene_fastus_events,
            stage="6",
            lifecycle="complete",
            message=f"Passthrough {total_llm_output} draft(s) (OpenAI unavailable or fallback)",
            detail={"mode": "passthrough"},
            max_events=120,
        )
    else:
        log_stage(
            scene_fastus_events,
            stage="6",
            lifecycle="warn",
            message="LLM layer produced no claims from drafts",
            detail={"drafts": total_claim_drafts},
            max_events=120,
        )

    log_stage(
        scene_fastus_events,
        stage="0",
        lifecycle="begin",
        message="Filtering fragments and applying polarity safety",
        max_events=120,
    )
    stage0_reject_events: list[FastusDebugEventOut] = []
    all_claims = [refine_extracted_location_claim(c) for c in all_claims]
    filtered = filter_extracted_claims(
        all_claims,
        pov_character=pov_character,
        reject_events=stage0_reject_events,
    )
    scene_fastus_events.extend(stage0_reject_events)
    stage0_rejected = len(stage0_reject_events)
    log_stage(
        scene_fastus_events,
        stage="0",
        lifecycle="complete",
        message=f"Kept {len(filtered)} claim(s) after filter",
        detail={
            "rejected_fragments": stage0_rejected,
            "negated_claims": stage0_negated,
        },
        max_events=120,
    )
    if stage0_rejected:
        emit(
            scene_fastus_events,
            stage="0",
            event="reject_summary",
            message=f"Stage 0 rejected {stage0_rejected} fragment claim(s)",
            detail={"count": stage0_rejected},
            max_events=120,
        )
    any_openai_ok = any(c.openai_ok for c in chunk_debug)
    filtered, suppressed_structural = suppress_redundant_structural_claims(
        filtered, llm_active=any_openai_ok or any_fastus_llm or use_llm_first
    )
    deduped = _dedupe_claims(filtered)
    if any_openai and any_fallback:
        source = "hybrid"
    elif any_openai_ok:
        source = "openai"
    else:
        source = "heuristic"

    return ExtractionResult(
        claims=deduped,
        suppressed_structural_count=suppressed_structural,
        source="openai" if use_llm_first and any_openai else source,
        chunk_count=total,
        word_count=word_count(text),
        error=api_error,
        duration_ms=int((time.perf_counter() - started) * 1000),
        openai_attempted=any_openai,
        fallback_used=any_fallback,
        large_chapter_warning=warn is not None,
        structural_entity_count=len(all_entities),
        chunks=chunk_debug,
        fastus_spacy_available=spacy_ok,
        fastus_stage0_negated_claims=stage0_negated,
        fastus_stage0_rejected_fragments=stage0_rejected,
        fastus_events=scene_fastus_events[:120],
        llm_recall_total=total_llm_recall,
        fastus_draft_total=total_fastus_extracted,
        regex_claim_total=total_regex_claims,
        after_dedupe_total=total_after_dedupe,
        anchored_total=total_anchored,
        unanchored_total=total_unanchored,
        needs_review_pipeline_total=total_needs_review_pipeline,
    )
