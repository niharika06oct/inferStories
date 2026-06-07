"""FASTUS Stage 3 - Basic Phrases.

Extract noun, verb, possessive, family, and prepositional phrase *candidates*
from a parsed chunk. No claims — only structured phrases with negation flags
and offsets for Stage 4 relation building.

Relevant reading: Jurafsky - POS Tagging, Dependency Parsing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.nlp.chapter_parse import ParsedChunk, ParsedSentence, ParsedToken, parse_chunk
from app.nlp.negation import has_identity_negation

PhraseType = Literal[
    "noun_phrase",
    "verb_phrase",
    "state_phrase",
    "family_phrase",
    "possessive_phrase",
    "prep_phrase",
    "place_phrase",
]
_POSSESSIVE_RE = re.compile(
    r"\b(?:my|his|her|their|our|your)\s+(\w+(?:\s+\w+)?)\b",
    re.I,
)
_VERB_PHRASE_FALLBACK_RE = re.compile(
    r"\b(?:did|do|does|had|have|has|was|were|is|are|am|will|would|could|should|can)?\s*"
    r"(?:not|never|no\s+longer)?\s*"
    r"(?:really|still|even|just)?\s*"
    r"(trust|trusted|love|loved|hate|hated|fear|feared|miss|missed|distrust|distrusted|know|knew)\s+"
    r"(\w+(?:\s+\w+)?)",
    re.I,
)
_PREP_PLACE_RE = re.compile(
    r"\b(?:in|at|from|to|near|around)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
)

_NP_POS = frozenset({"DET", "ADJ", "NOUN", "PROPN", "NUM"})
_FAMILY_RELATION = frozenset({
    "father",
    "mother",
    "dad",
    "mom",
    "mum",
    "pa",
    "papa",
    "daddy",
    "mama",
    "mommy",
    "mammy",

    "parent",
    "parents",

    "son",
    "daughter",
    "child",
    "children",

    "brother",
    "sister",
    "sibling",
})
_EXTENDED_FAMILY_RELATION = frozenset({
    "grandfather",
    "grandmother",
    "grandpa",
    "grandma",
    "granny",
    "nan",
    "nana",

    "grandson",
    "granddaughter",
    "grandchild",

    "uncle",
    "aunt",
    "auntie",

    "nephew",
    "niece",

    "cousin",
})
_MARRIAGE_RELATION = frozenset({
    "husband",
    "wife",
    "spouse",

    "fiance",
    "fiancée",

    "partner",

    "boyfriend",
    "girlfriend",

    "lover",
    "sweetheart",
})
_STEP_FAMILY_RELATION = frozenset({
    "stepfather",
    "stepmother",

    "stepdad",
    "stepmom",

    "stepson",
    "stepdaughter",

    "stepbrother",
    "stepsister",

    "stepparent",
    "stepchild",
})
_INLAW_RELATION = frozenset({
    "father-in-law",
    "mother-in-law",

    "brother-in-law",
    "sister-in-law",

    "son-in-law",
    "daughter-in-law",

    "in-law",
})
_GUARDIAN_RELATION = frozenset({
    "guardian",
    "ward",

    "adoptive father",
    "adoptive mother",

    "adoptive parent",

    "adopted son",
    "adopted daughter",
    "adopted child",

    "foster father",
    "foster mother",
    "foster parent",

    "foster son",
    "foster daughter",
    "foster child",
})
_EMOTION_LEMMAS = frozenset({
    # Love / Attachment
    "love",
    "adore",
    "cherish",
    "treasure",
    "care",
    "like",
    "fancy",
    "crush",
    "desire",
    "long",
    "yearn",
    "miss",
    "need",
    "want",
    "crave",
    "prefer",

    # Trust / Respect
    "trust",
    "believe",
    "respect",
    "admire",
    "appreciate",
    "value",
    "revere",

    # Fear / Anxiety
    "fear",
    "dread",
    "worry",
    "panic",
    "fret",
    "suspect",
    "doubt",
    "mistrust",
    "distrust",

    # Anger / Hostility
    "hate",
    "despise",
    "loathe",
    "resent",
    "detest",
    "abhor",
    "dislike",
    "begrudge",

    # Sadness / Loss
    "grieve",
    "mourn",
    "lament",
    "regret",
    "weep",
    "sob",
    "cry",

    # Happiness / Joy
    "enjoy",
    "delight",
    "rejoice",
    "celebrate",
    "laugh",

    # Jealousy / Envy
    "envy",
    "covet",

    # Compassion
    "pity",
    "sympathize",
    "empathize",
    "comfort",
    "console",

    # Forgiveness / Acceptance
    "forgive",
    "accept",
    "tolerate",

    # Rejection / Avoidance
    "avoid",
    "reject",
    "ignore",
    "shun",

    # Hope / Anticipation
    "hope",
    "wish",
    "anticipate",
    "expect",

    # Pride / Shame
    "boast",
    "brag",
    "humiliate",
    "embarrass",

    # Attraction
    "attract",
    "tempt",
    "seduce",

    # Emotional Cognitive States
    "know",
    "understand",
    "realize",
    "recognize",
    "remember",
    "forget",
    "wonder",
    "confuse",
})
_EMOTION_ADJECTIVES = frozenset({
    "afraid",
    "jealous",
    "angry",
    "furious",
    "sad",
    "happy",
    "confused",
    "worried",
    "anxious",
    "embarrassed",
    "ashamed",
    "proud",
    "lonely",
    "heartbroken",
    "devoted",
    "resentful",
    "grateful",
    "uncomfortable",
    "comfortable",
    "curious",
    "hopeful",
    "suspicious",
    "fearful",
})

_ALL_FAMILY_RELATIONS: frozenset[str] = (
    _FAMILY_RELATION
    | _EXTENDED_FAMILY_RELATION
    | _MARRIAGE_RELATION
    | _STEP_FAMILY_RELATION
    | _INLAW_RELATION
    | _GUARDIAN_RELATION
)

_FAMILY_RE = re.compile(
    rf"\bmy\s+({'|'.join(re.escape(t) for t in sorted(_ALL_FAMILY_RELATIONS, key=len, reverse=True))})\b",
    re.I,
)

_STATE_PHRASE_FALLBACK_RE = re.compile(
    rf"\b(?:was|were|is|are|am)\s+(?:not|never)?\s*"
    rf"({'|'.join(re.escape(a) for a in sorted(_EMOTION_ADJECTIVES, key=len, reverse=True))})"
    rf"(?:\s+(?:with|of|about)\s+([A-Za-z][\w'-]+(?:\s+[A-Za-z][\w'-]+)?))?",
    re.I,
)


def _normalize_relation(head: str) -> str:
    return " ".join((head or "").strip().lower().split())


def _is_family_relation(head: str) -> bool:
    return _normalize_relation(head) in _ALL_FAMILY_RELATIONS


@dataclass(frozen=True)
class PhraseCandidate:
    phrase_text: str
    phrase_type: PhraseType
    head_token: str
    modifiers: tuple[str, ...] = ()
    negated: bool = False
    start_char: int = 0
    end_char: int = 0
    sentence_index: int = 0
    chunk_index: int = 0
    # Family phrases: relation role (father, mother, …). Stage 4 resolves possessor.
    family_relation: str = ""
    possessor_hint: str = ""


def _sentence_index(parsed: ParsedChunk, offset: int) -> int:
    for i, sent in enumerate(parsed.sentences):
        if sent.start_char <= offset < sent.end_char:
            return i
    return 0


def _span_text(tokens: list[ParsedToken], start: int, end: int) -> str:
    return " ".join(t.text for t in tokens[start:end]).strip()


def _children_of(head_idx: int, tokens: list[ParsedToken]) -> list[int]:
    return [i for i, t in enumerate(tokens) if t.head == head_idx]


def _collect_subtree(
    root_idx: int,
    tokens: list[ParsedToken],
    *,
    deps: frozenset[str] | None = None,
) -> list[int]:
    """Indices in phrase order for root + matching dependent tokens."""
    indices = [root_idx]
    for child in _children_of(root_idx, tokens):
        if deps is None or tokens[child].dep in deps:
            indices.append(child)
    return sorted(set(indices))


def _negated_in_span(
    tokens: list[ParsedToken],
    indices: list[int],
    *,
    sentence_text: str,
    check_identity: bool = False,
) -> bool:
    if any(tokens[i].is_negation for i in indices):
        return True
    if check_identity and has_identity_negation(sentence_text):
        return True
    return False


def _emit_span(
    parsed: ParsedChunk,
    tokens: list[ParsedToken],
    indices: list[int],
    *,
    phrase_type: PhraseType,
    head_token: str,
    modifiers: tuple[str, ...] = (),
    negated: bool = False,
    family_relation: str = "",
    possessor_hint: str = "",
    seen: set[tuple[int, int, str]],
    out: list[PhraseCandidate],
) -> None:
    if not indices:
        return
    start = tokens[indices[0]].start_char
    end = tokens[indices[-1]].end_char
    key = (start, end, phrase_type)
    if key in seen:
        return
    text = parsed.text[start:end].strip()
    if not text:
        return
    seen.add(key)
    out.append(
        PhraseCandidate(
            phrase_text=text,
            phrase_type=phrase_type,
            head_token=head_token,
            modifiers=modifiers,
            negated=negated,
            start_char=start,
            end_char=end,
            sentence_index=_sentence_index(parsed, start),
            chunk_index=parsed.chunk_index,
            family_relation=family_relation,
            possessor_hint=possessor_hint,
        )
    )


def _family_phrases(
    parsed: ParsedChunk,
    sent: ParsedSentence,
    tokens: list[ParsedToken],
    *,
    seen: set[tuple[int, int, str]],
    out: list[PhraseCandidate],
) -> None:
    for m in _FAMILY_RE.finditer(sent.text):
        abs_start = sent.start_char + m.start()
        abs_end = sent.start_char + m.end()
        relation = _normalize_relation(m.group(1))
        negated = has_identity_negation(sent.text)
        key = (abs_start, abs_end, "family_phrase")
        if key in seen:
            continue
        seen.add(key)
        out.append(
            PhraseCandidate(
                phrase_text=m.group(0),
                phrase_type="family_phrase",
                head_token=relation,
                modifiers=("my",),
                negated=negated,
                start_char=abs_start,
                end_char=abs_end,
                sentence_index=_sentence_index(parsed, abs_start),
                chunk_index=parsed.chunk_index,
                family_relation=relation,
                possessor_hint="my",
            )
        )


def _possessive_phrases_regex(
    parsed: ParsedChunk,
    sent: ParsedSentence,
    *,
    seen: set[tuple[int, int, str]],
    out: list[PhraseCandidate],
) -> None:
    for m in _POSSESSIVE_RE.finditer(sent.text):
        full = m.group(0)
        head = m.group(1).strip()
        if _is_family_relation(head):
            continue  # covered by family_phrase
        abs_start = sent.start_char + m.start()
        abs_end = sent.start_char + m.end()
        poss = full.split()[0].lower()
        key = (abs_start, abs_end, "possessive_phrase")
        if key in seen:
            continue
        seen.add(key)
        out.append(
            PhraseCandidate(
                phrase_text=full,
                phrase_type="possessive_phrase",
                head_token=head,
                modifiers=(poss,),
                negated=has_identity_negation(sent.text),
                start_char=abs_start,
                end_char=abs_end,
                sentence_index=_sentence_index(parsed, abs_start),
                chunk_index=parsed.chunk_index,
                possessor_hint=poss,
            )
        )


def _verb_phrases_deps(
    parsed: ParsedChunk,
    sent: ParsedSentence,
    tokens: list[ParsedToken],
    *,
    seen: set[tuple[int, int, str]],
    out: list[PhraseCandidate],
) -> None:
    sent_indices = list(range(sent.token_start, sent.token_end))
    for idx in sent_indices:
        tok = tokens[idx]
        if tok.dep != "ROOT" or tok.pos != "VERB":
            continue
        if tok.lemma.lower() not in _EMOTION_LEMMAS:
            continue
        # aux, neg, adverbs, and direct object for short VPs ("did not trust him").
        deps = frozenset({"aux", "neg", "advmod", "prt", "dobj", "xcomp"})
        subtree = _collect_subtree(idx, tokens, deps=deps)
        # Include leading aux tokens that point at this root.
        for j in sent_indices:
            if tokens[j].dep == "aux" and tokens[j].head == idx and j not in subtree:
                subtree.append(j)
        subtree = sorted(set(i for i in subtree if sent.token_start <= i < sent.token_end))
        if not subtree:
            continue
        mods = tuple(
            tokens[i].text
            for i in subtree
            if i != idx and tokens[i].dep in ("aux", "neg", "advmod", "prt")
        )
        negated = _negated_in_span(tokens, subtree, sentence_text=sent.text)
        _emit_span(
            parsed,
            tokens,
            subtree,
            phrase_type="verb_phrase",
            head_token=tok.lemma or tok.text,
            modifiers=mods,
            negated=negated,
            seen=seen,
            out=out,
        )


def _state_phrases_deps(
    parsed: ParsedChunk,
    sent: ParsedSentence,
    tokens: list[ParsedToken],
    *,
    seen: set[tuple[int, int, str]],
    out: list[PhraseCandidate],
) -> None:
    """Copular emotional states: 'was uncomfortable with Edward', 'was jealous of Rosalie'."""
    sent_indices = list(range(sent.token_start, sent.token_end))
    for idx in sent_indices:
        tok = tokens[idx]
        if tok.dep != "ROOT" or tok.lemma.lower() != "be":
            continue

        adj_idx: int | None = None
        for child in _children_of(idx, tokens):
            ct = tokens[child]
            if ct.dep not in ("acomp", "attr"):
                continue
            if ct.lemma.lower() in _EMOTION_ADJECTIVES or ct.text.lower() in _EMOTION_ADJECTIVES:
                adj_idx = child
                break
        if adj_idx is None:
            continue

        subtree = [idx, adj_idx]
        for child in _children_of(idx, tokens):
            if tokens[child].dep in ("neg", "nsubj", "nsubjpass", "aux"):
                subtree.append(child)
        for child in _children_of(adj_idx, tokens):
            if tokens[child].dep == "prep":
                subtree.append(child)
                for gc in _children_of(child, tokens):
                    if tokens[gc].dep == "pobj":
                        subtree.append(gc)

        subtree = sorted(set(i for i in subtree if sent.token_start <= i < sent.token_end))
        adj_tok = tokens[adj_idx]
        mods = tuple(
            tokens[i].text
            for i in subtree
            if i != adj_idx and tokens[i].dep in ("neg", "nsubj", "nsubjpass", "aux", "prep")
        )
        negated = _negated_in_span(tokens, subtree, sentence_text=sent.text)
        _emit_span(
            parsed,
            tokens,
            subtree,
            phrase_type="state_phrase",
            head_token=adj_tok.lemma or adj_tok.text,
            modifiers=mods,
            negated=negated,
            seen=seen,
            out=out,
        )


def _noun_phrases_deps(
    parsed: ParsedChunk,
    sent: ParsedSentence,
    tokens: list[ParsedToken],
    *,
    seen: set[tuple[int, int, str]],
    out: list[PhraseCandidate],
) -> None:
    for idx in range(sent.token_start, sent.token_end):
        tok = tokens[idx]
        if tok.dep not in ("nsubj", "dobj", "pobj", "attr", "nsubjpass"):
            continue
        # Collect compound/det/amod children + head.
        subtree = [idx]
        for child in _children_of(idx, tokens):
            if tokens[child].pos in _NP_POS or tokens[child].dep in ("compound", "det", "amod"):
                subtree.append(child)
        subtree = sorted(set(subtree))
        mods = tuple(
            tokens[i].text for i in subtree if i != idx and tokens[i].dep != "compound"
        )
        _emit_span(
            parsed,
            tokens,
            subtree,
            phrase_type="noun_phrase",
            head_token=tok.text,
            modifiers=mods,
            negated=False,
            seen=seen,
            out=out,
        )


def _prep_phrases_deps(
    parsed: ParsedChunk,
    sent: ParsedSentence,
    tokens: list[ParsedToken],
    *,
    seen: set[tuple[int, int, str]],
    out: list[PhraseCandidate],
) -> None:
    for idx in range(sent.token_start, sent.token_end):
        tok = tokens[idx]
        if tok.dep != "prep" and tok.pos != "ADP":
            continue
        subtree = [idx]
        for child in _children_of(idx, tokens):
            if tokens[child].dep == "pobj":
                subtree.append(child)
                for gc in _children_of(child, tokens):
                    if tokens[gc].pos in _NP_POS:
                        subtree.append(gc)
        subtree = sorted(set(subtree))
        pobj = next((tokens[i].text for i in subtree if tokens[i].dep == "pobj"), "")
        phrase_type: PhraseType = (
            "place_phrase" if tokens[subtree[-1]].ent_type in ("GPE", "LOC", "FAC") else "prep_phrase"
        )
        _emit_span(
            parsed,
            tokens,
            subtree,
            phrase_type=phrase_type,
            head_token=pobj or tok.text,
            modifiers=(tok.text,),
            negated=False,
            seen=seen,
            out=out,
        )


def _fallback_phrases(parsed: ParsedChunk, *, seen: set[tuple[int, int, str]], out: list[PhraseCandidate]) -> None:
    for sent in parsed.sentences:
        _family_phrases(parsed, sent, parsed.tokens, seen=seen, out=out)
        _possessive_phrases_regex(parsed, sent, seen=seen, out=out)

        for m in _STATE_PHRASE_FALLBACK_RE.finditer(sent.text):
            abs_start = sent.start_char + m.start()
            abs_end = sent.start_char + m.end()
            adj = m.group(1).lower()
            phrase = parsed.text[abs_start:abs_end]
            negated = bool(re.search(r"\b(?:not|never)\b", phrase, re.I))
            key = (abs_start, abs_end, "state_phrase")
            if key in seen:
                continue
            seen.add(key)
            out.append(
                PhraseCandidate(
                    phrase_text=phrase.strip(),
                    phrase_type="state_phrase",
                    head_token=adj,
                    modifiers=(),
                    negated=negated,
                    start_char=abs_start,
                    end_char=abs_end,
                    sentence_index=_sentence_index(parsed, abs_start),
                    chunk_index=parsed.chunk_index,
                )
            )

        for m in _VERB_PHRASE_FALLBACK_RE.finditer(sent.text):
            abs_start = sent.start_char + m.start()
            abs_end = sent.start_char + m.end()
            verb = m.group(1).lower()
            obj = m.group(2)
            phrase = parsed.text[abs_start:abs_end]
            negated = bool(re.search(r"\b(?:not|never)\b", phrase, re.I))
            key = (abs_start, abs_end, "verb_phrase")
            if key in seen:
                continue
            seen.add(key)
            out.append(
                PhraseCandidate(
                    phrase_text=phrase.strip(),
                    phrase_type="verb_phrase",
                    head_token=verb,
                    modifiers=(),
                    negated=negated,
                    start_char=abs_start,
                    end_char=abs_end,
                    sentence_index=_sentence_index(parsed, abs_start),
                    chunk_index=parsed.chunk_index,
                )
            )

        for m in _PREP_PLACE_RE.finditer(sent.text):
            abs_start = sent.start_char + m.start()
            abs_end = sent.start_char + m.end()
            place = m.group(1)
            key = (abs_start, abs_end, "place_phrase")
            if key in seen:
                continue
            seen.add(key)
            out.append(
                PhraseCandidate(
                    phrase_text=m.group(0),
                    phrase_type="place_phrase",
                    head_token=place,
                    modifiers=(m.group(0).split()[0].lower(),),
                    negated=False,
                    start_char=abs_start,
                    end_char=abs_end,
                    sentence_index=_sentence_index(parsed, abs_start),
                    chunk_index=parsed.chunk_index,
                )
            )


def extract_phrase_candidates(
    parsed: ParsedChunk,
    *,
    pov_character: str | None = None,
) -> list[PhraseCandidate]:
    """
    Build phrase candidates from a ParsedChunk.

    pov_character is stored as possessor hint on family phrases when set (Stage 4
    will resolve coreference fully).
    """
    del pov_character  # reserved: family possessor wiring in Stage 4

    seen: set[tuple[int, int, str]] = set()
    out: list[PhraseCandidate] = []

    if parsed.has_dependencies and parsed.tokens:
        for sent in parsed.sentences:
            tokens = parsed.tokens
            _family_phrases(parsed, sent, tokens, seen=seen, out=out)
            _possessive_phrases_regex(parsed, sent, seen=seen, out=out)
            _verb_phrases_deps(parsed, sent, tokens, seen=seen, out=out)
            _state_phrases_deps(parsed, sent, tokens, seen=seen, out=out)
            _noun_phrases_deps(parsed, sent, tokens, seen=seen, out=out)
            _prep_phrases_deps(parsed, sent, tokens, seen=seen, out=out)
    else:
        _fallback_phrases(parsed, seen=seen, out=out)

    return sorted(out, key=lambda p: (p.start_char, p.end_char))


def extract_phrase_candidates_from_text(
    text: str,
    chunk_index: int = 0,
    *,
    pov_character: str | None = None,
) -> list[PhraseCandidate]:
    parsed = parse_chunk(text, chunk_index)
    return extract_phrase_candidates(parsed, pov_character=pov_character)
