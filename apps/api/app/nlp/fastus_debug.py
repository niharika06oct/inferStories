"""FASTUS pipeline debug helpers — structured events + optional server logging.

Stages 0–9 emit lifecycle events (BEGIN / COMPLETE / SKIP) during extraction,
merge, and validation. The web "Extraction details" panel surfaces structured
events; the API console shows the same when FASTUS_DEBUG is enabled.

Set FASTUS_DEBUG=1 in apps/api/.env for verbose console logging (logger INFO).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Literal

from app.extraction.schema import FastusDebugEventOut

logger = logging.getLogger(__name__)
_fastus_logging_configured = False

Lifecycle = Literal["begin", "complete", "skip", "warn"]

# Cap events per chunk / scene to keep API payloads small.
_MAX_CHUNK_EVENTS = 40
_MAX_SCENE_EVENTS = 120

STAGE_LABELS: dict[str, str] = {
    "0": "polarity + fragment safety",
    "1": "token parse",
    "2": "entity candidates",
    "3": "phrase candidates",
    "4": "relation candidates",
    "5": "semantic patterns → claim drafts",
    "6": "LLM refinement",
    "7": "polarity-aware merge + stale prune",
    "8": "continuity validation",
    "9": "issue enrichment (evidence + fix)",
    "meta": "pipeline",
}


def fastus_logging_enabled() -> bool:
    return os.getenv("FASTUS_DEBUG", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def configure_fastus_logging() -> bool:
    """
    Attach a stderr handler so FASTUS INFO lines appear under uvicorn.

    Python's default root logger is WARNING; without this, logger.info calls
    are dropped even when FASTUS_DEBUG=1.
    """
    global _fastus_logging_configured
    if _fastus_logging_configured or not fastus_logging_enabled():
        return fastus_logging_enabled()
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(message)s"),
    )
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    _fastus_logging_configured = True
    return True


def _format_detail(detail: dict[str, Any] | None) -> str:
    if not detail:
        return ""
    return " ".join(f"{k}={v}" for k, v in detail.items())


def log_stage_console(
    stage: str,
    lifecycle: Lifecycle,
    message: str,
    *,
    detail: dict[str, Any] | None = None,
) -> None:
    """Write a stage lifecycle line to the API console when FASTUS_DEBUG=1."""
    if not configure_fastus_logging():
        return
    label = STAGE_LABELS.get(stage, stage)
    suffix = _format_detail(detail)
    logger.info(
        "[FASTUS] Stage %s %s — %s (%s)%s",
        stage,
        lifecycle.upper(),
        message,
        label,
        f" {suffix}" if suffix else "",
    )


def log_stage(
    events: list[FastusDebugEventOut] | None,
    *,
    stage: str,
    lifecycle: Lifecycle,
    message: str,
    detail: dict[str, Any] | None = None,
    max_events: int = _MAX_CHUNK_EVENTS,
) -> None:
    """Append a lifecycle event to the API payload and mirror to the console."""
    log_stage_console(stage, lifecycle, message, detail=detail)
    if events is None:
        return
    if len(events) >= max_events:
        return
    row = FastusDebugEventOut(
        stage=stage,
        event=f"stage_{lifecycle}",
        message=message,
        detail={k: str(v) for k, v in (detail or {}).items()},
    )
    events.append(row)


def log_stage_dict(
    events: list[dict[str, str]] | None,
    *,
    stage: str,
    lifecycle: Lifecycle,
    message: str,
    detail: dict[str, str] | None = None,
) -> None:
    """Lifecycle log for merge/validation stats dict events (+ console)."""
    log_stage_console(stage, lifecycle, message, detail=detail)
    if events is None:
        return
    events.append(
        {
            "stage": stage,
            "event": f"stage_{lifecycle}",
            "message": message,
            "detail": detail or {},
        }
    )


def lifecycle_dict_to_out(events: list[dict[str, str]]) -> list[FastusDebugEventOut]:
    return [
        FastusDebugEventOut(
            stage=e["stage"],
            event=e["event"],
            message=e["message"],
            detail=e.get("detail") or {},
        )
        for e in events
    ]


def _log_event(event: FastusDebugEventOut) -> None:
    if not configure_fastus_logging():
        return
    detail = _format_detail(event.detail)
    logger.info(
        "[FASTUS] Stage %s %s — %s%s",
        event.stage,
        event.event,
        event.message,
        f" {detail}" if detail else "",
    )


def emit(
    events: list[FastusDebugEventOut],
    *,
    stage: str,
    event: str,
    message: str,
    detail: dict[str, Any] | None = None,
    max_events: int = _MAX_CHUNK_EVENTS,
) -> None:
    """Append a granular debug event and optionally log it."""
    if len(events) >= max_events:
        return
    row = FastusDebugEventOut(
        stage=stage,
        event=event,
        message=message,
        detail={k: str(v) for k, v in (detail or {}).items()},
    )
    events.append(row)
    _log_event(row)
