Yes. In fact, what you've photographed is one of the most relevant diagrams I've seen for InferStories.

This FASTUS pipeline is from an era before LLMs, but the surprising thing is:

> A production-grade InferStories should probably look more like FASTUS than like "send chapter to GPT and hope."

The diagram shows:

1. Tokens
2. Complex Words
3. Basic Phrases
4. Complex Phrases
5. Semantic Patterns
6. Merging

And that's almost exactly the architecture I'd recommend for your extraction pipeline.

---

# What FASTUS is teaching

The core idea:

Don't jump from:

```

```

```
Raw chapter
↓
LLM
↓
Claims
```

Instead:

```

```

```
Chapter
↓
Tokenization
↓
Entity Detection
↓
Phrase Detection
↓
Relationship Detection
↓
Coreference
↓
Fact Graph
↓
LLM refinement
```

---

# Mapping FASTUS to InferStories

## Level 1: Tokens

Example:

```

```

```
Charlie was not my father.
```

becomes:

```

```

```
Charlie
was
not
my
father
```

Today:

-   
spaCy  

-   
NLTK  

-   
Stanza  


already do this.

You don't need GPT here.

---

## Level 2: Complex Words

FASTUS:

```

```

```
New York
Forks High School
Edward Cullen
```

should become:

```

```

```
Single units
```

InferStories equivalent:

```

```

```
Ashan Thorne
Nahira Flammae
Athena Varkess
```

must be recognized before extraction.

Otherwise:

```

```

```
Ashan
Thorne
```

become separate entities.

---

### Relevant Jurafsky

NER chapters.

---

## Level 3: Basic Phrases

Example:

```

```

```
my father
the old king
the vampire hunter
```

becomes:

```

```

```
Noun phrase
```

This is critical.

Your extractor currently sees:

```

```

```
father
```

and immediately creates:

```

```

```
father_of(...)
```

which is dangerous.

Instead:

```

```

```
my father
```

must first become:

```

```

```
NOUN_PHRASE
```

before any claim extraction.

---

### Relevant Jurafsky

Syntax / Parsing chapters.

---

## Level 4: Complex Phrases

Example:

```

```

```
Charlie was not my father
```

Now we have:

```

```

```
Subject:
Charlie

Predicate:
father

Negation:
true

Object:
Bella
```

Notice:

We still haven't created a claim.

We're only building structure.

---

This is where most current bugs disappear.

---

### Relevant Jurafsky

Dependency Parsing

---

## Level 5: Semantic Patterns

This is where facts appear.

Input:

```

```

```
Charlie was not my father.
```

Output:

```

```

```
{
  "subject": "Charlie",
  "predicate": "father_of",
  "object": "Bella",
  "polarity": false
}
```

Now we're finally creating memory.

---

This is exactly where:

```

```

```
trusts
loves
hates
married_to
friend_of
```

should be extracted.

---

### Relevant AIMA

Knowledge Representation

First Order Logic

---

## Level 6: Merging

This may be the single most important stage.

Suppose chapter 1 says:

```

```

```
Charlie is Bella's father.
```

Chapter 13 says:

```

```

```
Charlie was not my father.
```

You now have:

```

```

```
father_of
```

and

```

```

```
NOT father_of
```

Merging decides:

```

```

```
New fact?
Duplicate?
Contradiction?
Character development?
Alternate timeline?
```

---

This is where your continuity engine lives.

---

### Relevant DDIA

Chapter 2

Data Models

---

# The biggest insight for InferStories

Look carefully at FASTUS.

The extraction happens before semantic reasoning.

Your current pipeline seems closer to:

```

```

```
Text
↓
LLM
↓
Claims
```

But FASTUS suggests:

```

```

```
Text
↓
Entities
↓
Phrases
↓
Coreference
↓
Relationships
↓
Facts
↓
LLM
```

That's exactly why you're getting:

```

```

```
did not trust him at all
```

stored as a claim.

The system skipped several FASTUS layers.

It never figured out:

```

```

```
who = Isabella
him = Charlie
predicate = trust
negation = true
```

before generating the fact.

---

# Can FASTUS be used directly?

Not literally.

FASTUS was built in the 1990s.

But the architecture is still excellent.

For InferStories I'd build:

```

```

```
1. Tokenization           (spaCy)

2. NER                    (spaCy + LLM)

3. Coreference            (LLM initially)

4. Entity Registry        (your new entity table)

5. Relation Extraction    (LLM)

6. Fact Graph Generation

7. Contradiction Engine

8. LLM Validation Layer
```

Notice:

The LLM is not Step 1.

The LLM is Step 5.

That dramatically reduces:

-   
hallucinations  

-   
cost  

-   
duplicate entities  

-   
bad claims  


---

# Which book chapter corresponds to this diagram?

### Jurafsky

For this exact FASTUS pipeline, prioritize:

1.   
Chapter 2–3 (Words, Morphology, Regex)  

2.   
Named Entity Recognition  

3.   
Syntactic Parsing  

4.   
Information Extraction  

5.   
Coreference Resolution  


### AIMA

1.   
Knowledge Representation  

2.   
First Order Logic  

3.   
Inference  


### DDIA

1.   
Chapter 2 — Data Models and Query Languages  


---

If you fully understand the FASTUS diagram and implement its modern equivalent, you'll solve about **70–80% of the extraction-quality problems you're currently seeing in InferStories**, including the exact bugs in your Twilight Chapter 13 test.

give me a workflow which I can give to the other system to implement FASTUS in my product to evolve and develop the current state.  
  
This workflow should compare my current system to the recommended FASTUS system, the stages involved and how I can realistically achieve each of those stages in the modern tech stack I am using.

Here’s a crisp workflow you can hand to the other system/team.

# InferStories FASTUS-Inspired Extraction Workflow

## Goal

Evolve InferStories from a mixed regex + LLM extraction system into a deterministic-first, FASTUS-inspired narrative extraction pipeline.

The aim is:

Raw chapter text  
→ structured linguistic layers  
→ entity-aware facts  
→ relationship memory  
→ continuity validation

LLM should remain mandatory, but only for semantic refinement, ambiguity resolution, and difficult reasoning — not basic parsing.

---

# 1. Current System vs Target FASTUS-Inspired System

## Current System

Current pipeline:

Chapter text  
→ chunking  
→ structural regex / family rules  
→ optional OpenAI full extraction  
→ heuristic fallback  
→ entity resolution  
→ claims  
→ validation  
→ relationship graph

Current issues:

- Regex creates fragment claims
- Negation is mishandled
- Pronouns are unresolved
- “did not trust him at all” becomes an incomplete claim
- “Charlie was not my father” may become “Charlie father_of Isabella”
- LLM and rules both generate overlapping claims
- Graph quality depends heavily on extraction quality
- LLM is doing too much too early

---

## Target FASTUS-Inspired System

Target pipeline:

Chapter text  
→ tokens  
→ complex words / named entities  
→ basic phrases  
→ complex phrases  
→ semantic patterns  
→ merging  
→ story memory  
→ validation

Modern equivalent:

Chapter text  
→ spaCy parse  
→ entity candidates  
→ phrase candidates  
→ SVO / dependency candidates  
→ semantic claim candidates  
→ LLM refinement  
→ entity registry  
→ claim store  
→ validation engine  
→ graph builder

---

# 2. FASTUS Stage 1 — Tokens

## Purpose

Convert raw text into structured tokens, sentences, punctuation, and offsets.

## Current State

Chunking exists, but token-level linguistic structure is not central to extraction.

## Target Implementation

Use spaCy per chunk.

Create module:

app/nlp/chapter_[parse.py](http://parse.py)

Responsibilities:

- Sentence splitting
- Tokenization
- POS tags
- Lemmas
- Dependency labels
- Start/end character offsets

Output:

ParsedChunk

fields:

- chunk_id
- text
- sentences
- tokens
- start_offset
- end_offset

Each token should include:

- text
- lemma
- pos
- dep
- start_char
- end_char

## Tech Stack

- Python
- spaCy
- en_core_web_sm initially
- Upgrade to en_core_web_trf later if needed

## Relevant Reading

Jurafsky:

- Text Processing
- POS Tagging

DDIA:

- Chapter 3, Storage and Retrieval, for indexing offsets and retrieval.

---

# 3. FASTUS Stage 2 — Complex Words / Named Entities

## Purpose

Recognize multiword units before extracting facts.

Examples:

- Edward Cullen
- Bella Swan
- Forks High School
- Olympic Peninsula
- Cullen family

## Current State

Entity registry exists, but many mentions are detected late or noisily.

## Target Implementation

Create entity candidate extractor:

app/nlp/entity_[candidates.py](http://candidates.py)

Extract:

- PERSON entities
- GPE / LOC
- ORG / group mentions
- proper noun spans
- recurring capitalized names
- known aliases from entity registry

Output:

EntityCandidate

fields:

- surface_text
- normalized_text
- entity_type_guess
- confidence
- start_offset
- end_offset
- source: spacy / registry / rule
- sentence_id

Entity types:

- character
- place
- object
- animal
- group
- concept

Hard rules:

- PERSON → character
- GPE/LOC → place
- ORG → group
- known alias → existing entity
- common nature terms like water/sun/rain → concept/object, not character

## Entity Registry Integration

Resolve candidate to canonical entity before claim extraction where possible.

Example:

“I” → Isabella Swan if POV character is set.

“Charlie” → Charlie Swan if already registered.

## Relevant Reading

Jurafsky:

- Named Entity Recognition
- Information Extraction

DDIA:

- Chapter 2, Data Models and Query Languages, for entity normalization.

---

# 4. FASTUS Stage 3 — Basic Phrases

## Purpose

Identify noun phrases and verb phrases before generating claims.

Examples:

- my father
- my mother
- the Cullen family
- Edward Cullen
- did not trust him
- had never missed me

## Current State

Family rules fire too early on phrases like “my father” without checking surrounding negation.

## Target Implementation

Create phrase extractor:

app/nlp/phrase_[candidates.py](http://candidates.py)

Extract:

- noun phrases
- verb phrases
- possessive phrases
- family phrases
- prepositional phrases

Important: Do not create claims here.

Only create phrase candidates.

Output:

PhraseCandidate

fields:

- phrase_text
- phrase_type: noun_phrase / verb_phrase / family_phrase / place_phrase
- head_token
- modifiers
- negated
- start_offset
- end_offset
- sentence_id

Examples:

“my father”

phrase_type = family_phrase

possessor = POV character

relation = father

negated = check parent sentence later

## Relevant Reading

Jurafsky:

- POS Tagging
- Dependency Parsing

---

# 5. FASTUS Stage 4 — Complex Phrases / Dependency Structures

## Purpose

Understand sentence-level structure:

Subject  
Predicate  
Object  
Negation  
Modifiers  
Coreference

Example:

“Charlie was not my father.”

Should produce:

subject = Charlie  
predicate = father_of  
object = Isabella Swan  
polarity = false

Not:

Charlie father_of Isabella Swan with polarity true

## Current State

Extractor sometimes produces fragment claims:

- “did not trusts him at all”
- “did not misses her either”

This means subject/object resolution failed.

## Target Implementation

Create relation candidate builder:

app/nlp/relation_[candidates.py](http://candidates.py)

Use spaCy dependency parse to extract:

- subject
- verb/predicate
- object
- negation
- complement
- evidence span

Candidate schema:

RelationCandidate

fields:

- subject_surface
- subject_entity_id
- predicate_raw
- predicate_normalized
- object_surface
- object_entity_id
- polarity
- confidence
- evidence_text
- start_offset
- end_offset
- extraction_origin: dependency / family_rule / pattern

## Negation Handling

Detect negation using:

- token.dep_ == "neg"
- words: not, never, no, neither, without
- phrases: did not, does not, was not, had never

Store polarity separately.

Preferred model:

predicate = father_of

polarity = false

Avoid creating predicates like:

- not_father_of
- does_not_trust

## Fragment Rejection Rules

Reject candidate if:

- subject is missing
- object is unresolved pronoun
- subject starts with auxiliary/verb: did, does, was, were, had
- predicate is malformed: trusts from “did not trust”
- evidence span is only a fragment without resolved subject
- object contains trailing filler: “him at all”, “her either”

Correct output:

“I did not trust him at all.”

With POV = Isabella and prior sentence mentioning Charlie:

subject = Isabella Swan  
predicate = trusts  
object = Charlie  
polarity = false

## Relevant Reading

Jurafsky:

- Dependency Parsing
- Coreference Resolution

AIMA:

- First Order Logic, for representing negation.

---

# 6. Coreference Resolution Layer

## Purpose

Resolve pronouns and descriptions to canonical entities.

Examples:

- I → POV character
- me → POV character
- my → POV character possessive
- him → nearest compatible male character
- her → nearest compatible female character
- them → nearest group or plural characters
- the Cullens → Cullen family group

## Current State

POV handling exists for “I”, but pronouns like him/her are not reliable.

## Target Implementation

Create module:

app/nlp/[coreference.py](http://coreference.py)

MVP rules:

1. POV resolution:
  - I, me, my, myself → scene.pov_character
2. Gender/role heuristic:
  - he/him/his → nearest recent male/person entity
  - she/her → nearest recent female/person entity
  - they/them → nearest group/plural entity
3. Family phrase resolution:
  - my father → entity linked by father_of if known, else candidate character
  - my mother → entity linked by mother_of if known
4. Registry-first:
  - if a relationship already exists, prefer known entity.

Maintain local context window:

- current sentence
- previous 3 sentences
- chapter-level recent entities

Output:

ResolvedMention

fields:

- mention_text
- entity_id
- confidence
- method: pov / nearest_entity / registry / llm

LLM escalation:

Only ask LLM when:

- multiple compatible candidates exist
- pronoun is important to a high-confidence relation candidate

## Relevant Reading

Jurafsky:

- Coreference Resolution

AIMA:

- Knowledge-Based Agents, for maintaining local context/state.

---

# 7. FASTUS Stage 5 — Semantic Patterns

## Purpose

Convert relation candidates into story claims.

Examples:

Candidate:

subject = Isabella  
predicate = trusts  
object = Charlie  
polarity = false

Claim:

Isabella does not trust Charlie.

claim_type = relationship_state

Semantic pattern categories:

- family relation
- relationship state
- character preference
- character state
- place fact
- object fact
- timeline fact
- world rule
- event

## Current State

Claims are created too early and sometimes store malformed text.

## Target Implementation

Create semantic mapper:

app/extraction/semantic_[patterns.py](http://patterns.py)

Input:

RelationCandidate

Output:

ClaimDraft

fields:

- subject_entity_id
- predicate
- object_entity_id
- claim_type
- polarity
- confidence
- evidence_text
- source_offsets
- status: suggested / needs_review / approved
- generation_origin

Rules:

If subject = character and object = character:

claim_type = relationship_state

If subject = character and object = place/object/concept:

claim_type = character_preference or character_fact

If predicate is family relation:

claim_type = family_relation

If predicate includes movement/location:

claim_type = location_fact

If sentence contains time marker:

claim_type = timeline_fact

## Predicate Normalization

Normalize:

- loves/loved/love → loves
- hates/hated/detests/detested → hates
- trust/trusts/trusted → trusts
- missed/misses/miss → misses
- is father / my father → father_of
- is mother / my mother → mother_of

## Negation

Represent:

Charlie was not my father

as:

predicate = father_of  
polarity = false

Not:

predicate = not_father_of

## Relevant Reading

Jurafsky:

- Information Extraction
- Relation Extraction

AIMA:

- Knowledge Representation

---

# 8. LLM Refinement Layer

## Purpose

Use LLM only after deterministic layers generate candidates.

LLM should refine, not invent everything from scratch.

## Current State

OpenAI can perform full extraction per chunk, causing cost, duplication, and noisy merges.

## Target Implementation

Replace broad LLM extraction with candidate refinement.

Old prompt:

“Extract all claims from this chapter.”

New prompt:

“Given these candidate claims and evidence spans, classify, correct, reject, or refine each. Return strict JSON.”

Input example:

[  
{  
"candidate_id": "c1",  
"evidence": "Charlie was not my father.",  
"subject": "Charlie",  
"predicate": "father_of",  
"object": "Isabella Swan",  
"polarity": false,  
"question": "Is this a valid story fact?"  
}  
]

LLM output:

[  
{  
"candidate_id": "c1",  
"valid": true,  
"claim_type": "family_relation",  
"predicate": "father_of",  
"polarity": false,  
"confidence": 0.96,  
"explanation": "The sentence explicitly denies Charlie is the narrator's father."  
}  
]

LLM should be used for:

- ambiguous pronouns
- emotional interpretation
- implicit relationships
- nuanced contradiction classification
- plotline significance

LLM should not be used for:

- tokenization
- sentence splitting
- basic NER
- graph building
- deterministic family rules
- hash/cache logic

## Relevant Reading

Jurafsky:

- Information Extraction

DDIA:

- Chapter 3, Storage and Retrieval, for caching results.

---

# 9. FASTUS Stage 6 — Merging

## Purpose

Merge extracted facts into story memory.

Decide:

- new claim
- duplicate claim
- updated claim
- contradiction
- deprecated claim
- needs review

## Current State

Approved claims are preserved on re-analysis, but semantic merging still needs improvement.

## Target Implementation

Enhance merge logic:

Claim identity should use:

- subject_entity_id
- predicate
- object_entity_id
- polarity
- claim_type

Keep:

- source_hash
- claim_version
- superseded_by_claim_id

Add:

- polarity
- valid_from_scene
- valid_until_scene
- confidence history

Merging rules:

1. Same subject, predicate, object, polarity:
  - duplicate or reinforcement
2. Same subject, predicate, object, opposite polarity:
  - contradiction candidate
3. Same subject, predicate, different object:
  - possible state change or contradiction depending on predicate
4. Later scene overrides active state:
  - create temporal state transition, not always contradiction

## Relevant Reading

DDIA:

- Chapter 2, Data Models
- Chapter 3, Storage and Retrieval

AIMA:

- Inference in First Order Logic

---

# 10. Validation Engine

## Purpose

Detect continuity problems from structured facts.

## Current State

Validation checks explicit incompatible objects and predicate oppositions conservatively.

## Target Implementation

Validation should operate on structured claims, not raw text.

Core contradiction rules:

1. Same triple, opposite polarity

Existing:

father_of(Charlie, Isabella) = true

New:

father_of(Charlie, Isabella) = false

Issue:

hard contradiction

1. Opposite predicates

trusts vs distrusts

loves vs hates

alive vs dead

1. World-rule violation

Stefan cannot die

Stefan dies permanently

1. Timeline impossibility

Character in two places at same time

1. Relationship state jump

Chapter N:

Bella fears Edward

Chapter N+1:

Bella fully trusts Edward

without bridging event

## Issue Output

Each issue should include:

- conflicting old claim
- new claim
- evidence from both
- severity
- explanation
- suggested fix
- resolution status

## Relevant Reading

AIMA:

- Logical Agents
- First Order Logic
- Inference

---

# 11. Graph Builder

## Purpose

Generate clean relationship graphs from trusted structured claims.

## Current State

Relationship graph exists and is rule-gated.

## Target Implementation

Graph rules remain deterministic.

Only render edges when:

- subject entity type = character
- object entity type = character
- claim_type = relationship_state or family_relation
- status = approved/canonized
- graph_eligible = true

Do not render:

- character → place
- character → object
- character → concept

Examples:

Bella loves Phoenix

Not graph edge.

Bella trusts Edward

Graph edge.

Charlie father_of Bella

Graph edge.

## Relevant Reading

DDIA:

- Chapter 2, Graph-like data models

AIMA:

- Knowledge Representation

---

# 12. Realistic Implementation Plan

## Phase 1 — Safety Fixes

Goal:  
Stop bad claims.

Tasks:

- Add polarity column to claims
- Add negation detection
- Reject fragment claims
- Add pronoun resolution for POV/I/me/my
- Add tests for Chapter 13

Expected result:

“Charlie was not my father” no longer becomes “Charlie father_of Isabella.”

---

## Phase 2 — spaCy Pipeline

Goal:  
Implement FASTUS stages 1–4.

Tasks:

- Add chapter_[parse.py](http://parse.py)
- Add entity_[candidates.py](http://candidates.py)
- Add phrase_[candidates.py](http://candidates.py)
- Add relation_[candidates.py](http://candidates.py)
- Use offsets and sentence IDs

Expected result:

Claims are based on actual sentence structure.

---

## Phase 3 — Semantic Pattern Layer

Goal:  
Generate clean claims from candidates.

Tasks:

- Add semantic_[patterns.py](http://patterns.py)
- Normalize predicates
- Assign claim_type based on entity types
- Preserve polarity
- Produce ClaimDrafts

Expected result:

Cleaner claims with fewer hallucinated fragments.

---

## Phase 4 — LLM Refinement

Goal:  
Use LLM only where useful.

Tasks:

- Replace full chunk extraction with candidate refinement
- Batch uncertain candidates
- Cache LLM responses
- Add prompt_hash and input_hash

Expected result:

Lower cost, higher consistency.

---

## Phase 5 — Merge and Validation Upgrade

Goal:  
Make continuity reliable.

Tasks:

- Enhance source_hash
- Use polarity in merge identity
- Add contradiction rules
- Add evidence comparison
- Add issue explanations

Expected result:

Continuity issues are understandable and reliable.

---

# 13. Acceptance Tests

Add tests for:

## Negation

Input:

Charlie was not my father.

Expected:

predicate = father_of  
polarity = false

## Pronoun Resolution

Input:

I did not trust him at all.

Context:

POV = Isabella Swan  
previous entity = Charlie

Expected:

subject = Isabella Swan  
predicate = trusts  
object = Charlie  
polarity = false

## No Fragment Claims

Input:

did not trust him at all

Expected:

Rejected unless subject/object resolved.

## Relationship Graph

Input:

I loved Phoenix.

Expected:

claim_type = character_preference  
no graph edge

Input:

I loved Edward.

Expected:

claim_type = relationship_state  
graph edge if approved

## Continuity

Earlier:

Charlie father_of Isabella = true

Later:

Charlie father_of Isabella = false

Expected:

hard contradiction issue

---

# 14. Final Target Architecture

Chapter  
→ Chunk  
→ Tokens  
→ Entities  
→ Phrases  
→ Relations  
→ Semantic Claims  
→ LLM Refinement  
→ Canon Memory  
→ Validation  
→ Graph

This should replace the current mixed extraction approach.

The principle:

Code handles structure.  
LLM handles meaning.  
Database handles memory.  
Rules handle consistency.  
Cache handles cost.  
UI gives writer control.

This is the cleanest implementation workflow: it preserves the spirit of FASTUS while fitting your current stack — FastAPI, SQLAlchemy, Postgres, Next.js, optional OpenAI, and soon spaCy.