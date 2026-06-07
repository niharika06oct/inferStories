"""FASTUS Stage 1 - tokenization/sentence/offset parsing.

These assertions hold whether or not the spaCy model is installed (fallback path).
"""

from app.nlp.chapter_parse import (
    ParsedChunk,
    is_spacy_available,
    parse_chunk,
    parse_text,
)


def test_parse_returns_tokens_with_offsets():
    text = "Charlie was not my father."
    parsed = parse_chunk(text, 0)
    assert isinstance(parsed, ParsedChunk)
    assert parsed.tokens
    # Every token offset slices back to its own surface text.
    for tok in parsed.tokens:
        assert text[tok.start_char : tok.end_char] == tok.text


def test_parse_detects_negation_token():
    parsed = parse_chunk("Charlie was not my father.", 0)
    assert any(t.is_negation for t in parsed.tokens)


def test_parse_splits_sentences():
    text = "Charlie was not my father. He was a stranger from Phoenix."
    parsed = parse_chunk(text, 0)
    assert len(parsed.sentences) >= 2
    for sent in parsed.sentences:
        assert text[sent.start_char : sent.end_char].strip()


def test_sentence_for_offset_round_trips():
    text = "Charlie was not my father. He was a stranger."
    parsed = parse_chunk(text, 0)
    idx = text.index("stranger")
    sent = parsed.sentence_for_offset(idx)
    assert sent is not None
    assert "stranger" in text[sent.start_char : sent.end_char]


def test_parse_text_indexes_chunks():
    parsed = parse_text(["First chunk.", "Second chunk."])
    assert [p.chunk_index for p in parsed] == [0, 1]


def test_dependencies_only_when_model_available():
    parsed = parse_chunk("Bella trusted Edward completely.", 0)
    if is_spacy_available():
        assert parsed.has_dependencies
        assert any(t.dep for t in parsed.tokens)
    else:
        assert not parsed.has_dependencies
