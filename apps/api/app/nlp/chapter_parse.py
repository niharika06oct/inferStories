"""FASTUS Stage 1 - Tokens.

Turn raw chapter prose into structured tokens, sentences, and character offsets.
Uses spaCy when a model is installed; otherwise degrades to a regex tokenizer so
the rest of the pipeline (and tests) work without the model download.

Relevant reading: Jurafsky - Text Processing, POS Tagging.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache

# Tokens treated as negation cues by the fallback tokenizer (spaCy uses dep_ == "neg").
_NEGATION_LEMMAS = frozenset({"not", "never", "n't", "no", "neither", "without"})

_FALLBACK_TOKEN_RE = re.compile(r"\w+(?:'\w+)?|[^\w\s]")
_FALLBACK_SENT_RE = re.compile(r"[^.!?]+(?:[.!?]+|$)")

_SPACY_MODEL_ENV = "SPACY_MODEL"
_DEFAULT_MODEL = "en_core_web_sm"


@dataclass(frozen=True)
class ParsedToken:
    text: str
    lemma: str
    pos: str  # coarse POS ("PROPN", "VERB", ...); "" when unknown (fallback)
    tag: str  # fine-grained tag; "" when unknown
    dep: str  # dependency label ("nsubj", "dobj", "neg", ...); "" when unknown
    head: int  # index of the head token within the chunk; -1 when unknown
    start_char: int
    end_char: int
    is_negation: bool
    ent_type: str = ""  # spaCy entity type ("PERSON", "GPE", ...) or ""


@dataclass(frozen=True)
class ParsedSentence:
    text: str
    start_char: int
    end_char: int
    token_start: int  # index of first token (inclusive) in ParsedChunk.tokens
    token_end: int  # index one past last token (exclusive)


@dataclass(frozen=True)
class ParsedChunk:
    chunk_index: int
    text: str
    tokens: list[ParsedToken] = field(default_factory=list)
    sentences: list[ParsedSentence] = field(default_factory=list)
    # True only when a real spaCy parser produced dependency labels.
    has_dependencies: bool = False

    def sentence_for_offset(self, offset: int) -> ParsedSentence | None:
        for sent in self.sentences:
            if sent.start_char <= offset < sent.end_char:
                return sent
        return None

    def tokens_in_sentence(self, sent: ParsedSentence) -> list[ParsedToken]:
        return self.tokens[sent.token_start : sent.token_end]


@lru_cache(maxsize=2)
def _load_spacy(model_name: str):
    """Load a spaCy pipeline, or return None if spaCy/model is unavailable."""
    try:
        import spacy
    except ImportError:
        return None
    try:
        return spacy.load(model_name)
    except (OSError, IOError):
        # Model not downloaded. Try a blank English pipeline with a sentencizer so
        # we still get sentence boundaries (but no dependencies/NER).
        try:
            import spacy

            nlp = spacy.blank("en")
            if "sentencizer" not in nlp.pipe_names:
                nlp.add_pipe("sentencizer")
            return nlp
        except Exception:  # pragma: no cover - spaCy import already succeeded
            return None


def _model_name() -> str:
    return os.getenv(_SPACY_MODEL_ENV, _DEFAULT_MODEL).strip() or _DEFAULT_MODEL


def is_spacy_available() -> bool:
    """True if a spaCy model with a dependency parser is loadable."""
    nlp = _load_spacy(_model_name())
    return bool(nlp) and nlp.has_pipe("parser")


def _is_negation(text: str, lemma: str, dep: str) -> bool:
    if dep == "neg":
        return True
    return text.lower() in _NEGATION_LEMMAS or lemma.lower() in _NEGATION_LEMMAS


def _parse_with_spacy(text: str, chunk_index: int, nlp) -> ParsedChunk:
    doc = nlp(text)
    tokens: list[ParsedToken] = []
    has_parser = nlp.has_pipe("parser")
    for tok in doc:
        head_idx = tok.head.i if (has_parser and tok.head is not None) else -1
        tokens.append(
            ParsedToken(
                text=tok.text,
                lemma=tok.lemma_ or tok.text.lower(),
                pos=tok.pos_ or "",
                tag=tok.tag_ or "",
                dep=tok.dep_ or "",
                head=head_idx,
                start_char=tok.idx,
                end_char=tok.idx + len(tok.text),
                is_negation=_is_negation(tok.text, tok.lemma_ or "", tok.dep_ or ""),
                ent_type=tok.ent_type_ or "",
            )
        )

    sentences: list[ParsedSentence] = []
    try:
        sents = list(doc.sents)
    except ValueError:
        sents = []
    for sent in sents:
        sentences.append(
            ParsedSentence(
                text=sent.text,
                start_char=sent.start_char,
                end_char=sent.start_char + len(sent.text),
                token_start=sent.start,
                token_end=sent.end,
            )
        )
    if not sentences:
        sentences = _fallback_sentences(text, tokens)

    return ParsedChunk(
        chunk_index=chunk_index,
        text=text,
        tokens=tokens,
        sentences=sentences,
        has_dependencies=has_parser,
    )


def _fallback_tokens(text: str) -> list[ParsedToken]:
    tokens: list[ParsedToken] = []
    for m in _FALLBACK_TOKEN_RE.finditer(text):
        word = m.group(0)
        tokens.append(
            ParsedToken(
                text=word,
                lemma=word.lower(),
                pos="",
                tag="",
                dep="",
                head=-1,
                start_char=m.start(),
                end_char=m.end(),
                is_negation=_is_negation(word, word.lower(), ""),
            )
        )
    return tokens


def _fallback_sentences(text: str, tokens: list[ParsedToken]) -> list[ParsedSentence]:
    sentences: list[ParsedSentence] = []
    for m in _FALLBACK_SENT_RE.finditer(text):
        seg = m.group(0)
        if not seg.strip():
            continue
        start, end = m.start(), m.end()
        tok_start = next(
            (i for i, t in enumerate(tokens) if t.start_char >= start), len(tokens)
        )
        tok_end = next(
            (i for i, t in enumerate(tokens) if t.start_char >= end), len(tokens)
        )
        sentences.append(
            ParsedSentence(
                text=seg.strip(),
                start_char=start,
                end_char=end,
                token_start=tok_start,
                token_end=tok_end,
            )
        )
    if not sentences and text.strip():
        sentences.append(
            ParsedSentence(
                text=text.strip(),
                start_char=0,
                end_char=len(text),
                token_start=0,
                token_end=len(tokens),
            )
        )
    return sentences


def _parse_fallback(text: str, chunk_index: int) -> ParsedChunk:
    tokens = _fallback_tokens(text)
    sentences = _fallback_sentences(text, tokens)
    return ParsedChunk(
        chunk_index=chunk_index,
        text=text,
        tokens=tokens,
        sentences=sentences,
        has_dependencies=False,
    )


def parse_chunk(text: str, chunk_index: int = 0) -> ParsedChunk:
    """Parse one chunk of prose into tokens + sentences with offsets."""
    text = text or ""
    nlp = _load_spacy(_model_name())
    if nlp is not None:
        try:
            return _parse_with_spacy(text, chunk_index, nlp)
        except Exception:  # pragma: no cover - defensive; fall back to regex
            return _parse_fallback(text, chunk_index)
    return _parse_fallback(text, chunk_index)


def parse_text(chunks: list[str]) -> list[ParsedChunk]:
    return [parse_chunk(chunk, i) for i, chunk in enumerate(chunks)]
