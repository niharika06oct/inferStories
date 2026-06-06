"""Semantic judgment layer for candidate continuity conflicts.

Rule validation should generate *candidates*. This module decides whether a
candidate should actually be shown to the writer, optionally asking an LLM for
ambiguous emotional/relationship cases.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.models import Claim, Scene

ContinuityClassification = Literal[
    "hard_contradiction",
    "soft_tension",
    "compatible_progression",
    "not_issue",
]

JudgeSource = Literal["rules", "ai", "fallback"]


@dataclass(frozen=True)
class ContinuityCandidate:
    scene: Scene
    new_claim: Claim
    old_claim: Claim
    severity: str
    message: str
    rule_classification: ContinuityClassification
    rule_reason: str
    conflict_kind: Literal["exclusive_object", "predicate_opposition"]


class ContinuityJudgment(BaseModel):
    classification: ContinuityClassification
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(default="", max_length=500)
    source: JudgeSource = "rules"


def should_show_judgment(judgment: ContinuityJudgment) -> bool:
    """Only writer-visible contradiction/tension classes become issues."""
    return judgment.classification in {"hard_contradiction", "soft_tension"}


def judge_continuity_candidate(
    candidate: ContinuityCandidate,
) -> ContinuityJudgment:
    """
    Return a continuity judgment for a candidate.

    Defaults to deterministic rule judgment. AI is opt-in via env and only used
    for relationship/emotional predicate opposition, where rules are most likely
    to confuse progression with contradiction.
    """
    rule = ContinuityJudgment(
        classification=candidate.rule_classification,
        confidence=1.0 if candidate.rule_classification == "hard_contradiction" else 0.75,
        reason=candidate.rule_reason,
        source="rules",
    )

    if not _ai_enabled() or candidate.conflict_kind != "predicate_opposition":
        return rule

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return rule

    try:
        return _ai_judge_continuity_candidate(candidate, rule, api_key=api_key)
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValidationError, ValueError):
        return rule.model_copy(
            update={
                "source": "fallback",
                "reason": f"{rule.reason} AI judge failed; using rule judgment.",
            }
        )


def _ai_enabled() -> bool:
    return os.getenv("CONTINUITY_AI_JUDGE_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _ai_judge_continuity_candidate(
    candidate: ContinuityCandidate,
    rule: ContinuityJudgment,
    *,
    api_key: str,
) -> ContinuityJudgment:
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("CONTINUITY_AI_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    payload = _candidate_payload(candidate)
    prompt = (
        "You are a continuity editor for fiction. Judge whether two extracted "
        "story-memory claims are a real continuity issue. Do not invent facts. "
        "Use the evidence snippets as the source of truth. Emotional progression "
        "or mild discomfort is usually NOT a contradiction.\n\n"
        "Return strict JSON with keys: classification, confidence, reason.\n"
        "classification must be one of: hard_contradiction, soft_tension, "
        "compatible_progression, not_issue.\n\n"
        f"Candidate:\n{json.dumps(payload, ensure_ascii=False)}"
    )

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You classify fiction continuity candidates. "
                            "Prefer suppressing false positives unless the two "
                            "claims are genuinely incompatible."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.0,
                "max_tokens": 300,
            },
        )
        response.raise_for_status()

    content = (
        response.json()
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    raw = json.loads(content)
    judgment = ContinuityJudgment.model_validate(raw)
    return judgment.model_copy(
        update={
            "source": "ai",
            "confidence": min(judgment.confidence, 1.0),
            "reason": judgment.reason.strip() or rule.reason,
        }
    )


def _candidate_payload(candidate: ContinuityCandidate) -> dict[str, object]:
    old = candidate.old_claim
    new = candidate.new_claim
    return {
        "scene_number": candidate.scene.scene_number,
        "rule_classification": candidate.rule_classification,
        "rule_reason": candidate.rule_reason,
        "old_claim": {
            "scene_id": old.scene_id,
            "subject": old.subject,
            "predicate": old.predicate,
            "object": old.claim_object,
            "claim_text": old.claim_text,
            "evidence_text": old.evidence_text,
        },
        "new_claim": {
            "scene_id": new.scene_id,
            "subject": new.subject,
            "predicate": new.predicate,
            "object": new.claim_object,
            "claim_text": new.claim_text,
            "evidence_text": new.evidence_text,
        },
    }
