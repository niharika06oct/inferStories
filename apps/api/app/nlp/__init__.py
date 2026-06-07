"""FASTUS-style linguistic layers (tokens -> entities -> phrases -> relations).

Each module here produces *candidates*, never final claims. The semantic layer
in app.extraction turns candidates into ClaimDrafts.
"""

from app.nlp.chapter_parse import (
    ParsedChunk,
    ParsedSentence,
    ParsedToken,
    is_spacy_available,
    parse_chunk,
    parse_text,
)
from app.nlp.entity_candidates import (
    EntityCandidate,
    extract_entity_candidates,
    extract_entity_candidates_from_text,
)
from app.nlp.phrase_candidates import (
    PhraseCandidate,
    extract_phrase_candidates,
    extract_phrase_candidates_from_text,
)
from app.nlp.coreference import CorefContext, ResolvedMention, build_coref_context, resolve_surface
from app.nlp.relation_candidates import (
    RelationCandidate,
    extract_relation_candidates,
    extract_relation_candidates_from_text,
)

__all__ = [
    "ParsedChunk",
    "ParsedSentence",
    "ParsedToken",
    "EntityCandidate",
    "is_spacy_available",
    "parse_chunk",
    "parse_text",
    "extract_entity_candidates",
    "extract_entity_candidates_from_text",
    "PhraseCandidate",
    "extract_phrase_candidates",
    "extract_phrase_candidates_from_text",
    "CorefContext",
    "ResolvedMention",
    "build_coref_context",
    "resolve_surface",
    "RelationCandidate",
    "extract_relation_candidates",
    "extract_relation_candidates_from_text",
]
