"""FASTUS stage lifecycle console logging."""

import logging

from app.nlp.fastus_debug import (
    STAGE_LABELS,
    configure_fastus_logging,
    fastus_logging_enabled,
    log_stage,
    log_stage_console,
)


def test_stage_labels_cover_zero_through_nine():
    for n in range(10):
        assert str(n) in STAGE_LABELS


def test_log_stage_console_emits_when_debug_enabled(capsys, monkeypatch):
    monkeypatch.setenv("FASTUS_DEBUG", "1")
    import app.nlp.fastus_debug as mod

    mod._fastus_logging_configured = False
    mod.logger.handlers.clear()
    assert fastus_logging_enabled()
    events: list = []
    log_stage(
        events,
        stage="6",
        lifecycle="skip",
        message="No claim drafts",
        detail={"openai_key": "set"},
    )
    assert len(events) == 1
    assert events[0].event == "stage_skip"
    captured = capsys.readouterr()
    assert "[FASTUS] Stage 6 SKIP" in captured.err


def test_configure_fastus_logging_adds_handler(monkeypatch):
    monkeypatch.setenv("FASTUS_DEBUG", "1")
    import app.nlp.fastus_debug as mod

    mod._fastus_logging_configured = False
    mod.logger.handlers.clear()
    assert configure_fastus_logging() is True
    assert mod.logger.handlers


def test_log_stage_console_silent_when_debug_disabled(caplog, monkeypatch):
    monkeypatch.delenv("FASTUS_DEBUG", raising=False)
    assert not fastus_logging_enabled()
    with caplog.at_level(logging.INFO, logger="app.nlp.fastus_debug"):
        log_stage_console("8", "begin", "test")
    assert not caplog.records
