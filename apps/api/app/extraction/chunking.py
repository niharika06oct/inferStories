"""Split chapter prose into overlapping chunks for extraction."""

from __future__ import annotations

import re

# ~1,500 words per chunk; 200-word overlap
TARGET_WORDS = 1500
OVERLAP_WORDS = 200
SINGLE_CHUNK_MAX_WORDS = 3000
WARN_WORDS = 10_000


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def chunk_chapter_text(text: str) -> tuple[list[str], int | None]:
    """
    Returns (chunks, warn_threshold_words).
    warn_threshold_words is set when chapter exceeds WARN_WORDS.
    """
    words = (text or "").split()
    n = len(words)
    warn = WARN_WORDS if n > WARN_WORDS else None

    if n <= SINGLE_CHUNK_MAX_WORDS:
        return [text.strip()], warn

    chunks: list[str] = []
    start = 0
    while start < n:
        end = min(start + TARGET_WORDS, n)
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))
        if end >= n:
            break
        start = max(0, end - OVERLAP_WORDS)

    return chunks, warn
