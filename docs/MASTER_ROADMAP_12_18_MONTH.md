# InferStories Master Roadmap: 12-18 Months

InferStories is not an AI writing assistant.

InferStories is a **Narrative Intelligence Platform** that converts stories into structured knowledge and helps writers maintain continuity, understand their worlds, and reason about their narratives.

Core transformation:

```text
Story Text
-> Entities
-> Events
-> Relationships
-> Facts
-> Knowledge Graph
-> Reasoning Engine
-> Writer Intelligence
```

## Roadmap Horizon

| Horizon | Product Focus | Primary Outcome |
|---|---|---|
| Months 0-3 | Deterministic extraction foundation | Replace heuristic-first extraction with local NLP, confidence scoring, and caching. |
| Months 3-6 | Event intelligence | Make events first-class story objects separate from claims. |
| Months 6-9 | Timeline engine | Track narrative chronology and detect temporal inconsistencies. |
| Months 9-12 | Story knowledge graph | Make the story world queryable across characters, places, objects, factions, and events. |
| Months 12-15 | Reasoning engine | Move from direct contradiction checks to inference-based validation. |
| Months 15-18 | Writer intelligence and scale | Surface arcs, plotlines, story health, background jobs, realtime updates, and semantic retrieval. |

## Phase 1: Solidify The Foundation

**Goal:** Replace heuristic extraction with a deterministic-first architecture.

**Status:** Partially implemented.

### 1.1 Entity System

Current:

- Entity registry exists.
- Aliases exist.
- Relationship graph exists.

Next:

- Improve entity classification.
- Add confidence scores.
- Add graph eligibility flags.

Entity types:

- Character
- Place
- Object
- Animal
- Group
- Concept

Examples:

- Bella -> Character
- Forks -> Place
- Truck -> Object
- Sun -> Concept

Success criteria:

- Water never becomes a character.
- Places never appear in relationship graphs.
- Graph contains only meaningful nodes.

### 1.2 Local NLP Layer

Implement **spaCy**.

Use for:

- Sentence splitting
- Named Entity Recognition
- POS tagging
- Dependency parsing
- Pronoun detection

The LLM should not perform grammar understanding. It should consume structured candidates from deterministic NLP and review them semantically.

Success criteria:

- Subject/verb/object extraction works without AI.
- Character detection quality increases significantly.

Book pointer: Jurafsky & Martin, *Speech and Language Processing*, chapters on POS tagging, named entity recognition, and dependency parsing. Section titles may differ by edition.

### 1.3 Extraction Refactor

Current:

```text
Text
-> Regex
-> OpenAI
-> Merge
```

Target:

```text
Text
-> spaCy
-> Rule Candidates
-> Confidence Scoring
-> LLM Refinement
-> Final Claims
```

The LLM becomes a semantic reviewer, not a semantic creator.

Success criteria:

- Lower cost.
- Better consistency.
- Fewer hallucinated claims.

### 1.4 Caching

Implement a chunk hash cache:

```text
chunk_hash -> extracted results
```

Implement an LLM cache:

```text
prompt_hash + chunk_hash -> LLM response
```

Success criteria:

- Unchanged text never triggers re-analysis.

Book pointer: DDIA Ch. 3, storage and retrieval. Use this for cache key design, durable storage choices, and invalidation strategy.

## Phase 2: Event Intelligence

Current model:

- Story
- Scene
- Entity
- Claim

Missing:

- Event

### 2.1 Event Model

Add `events` as first-class records:

- `id`
- `story_id`
- `scene_id`
- `title`
- `participants`
- `description`
- `importance_score`
- `chapter_position`

Examples:

- Bella moves to Forks.
- Ashan proposes.
- Nahira leaves home.

Events become first-class citizens rather than being hidden inside claims.

### 2.2 Event Extraction

Extract:

- Movement events
- Relationship changes
- Combat events
- Discovery events
- Character decisions

Store events separately from claims.

Success criteria:

- A story can be summarized through events.

Book pointer: Jurafsky & Martin, information extraction; DDIA chapters on data models.

## Phase 3: Timeline Engine

Current:

- Scene order

Target:

- Narrative timeline

### 3.1 Timeline Model

Add `timeline_events`:

- `event_id`
- `occurs_at`
- `relative_position`
- `certainty`

Support temporal expressions:

- 3 years later
- before the war
- when she was 12

### 3.2 Timeline Validation

Detect:

- Age inconsistencies
- Missing travel
- Impossible chronology

Example:

- Chapter 5: Ashan age = 22
- Chapter 20: Five years later
- Chapter 20: Ashan age = 23
- Result: flag an issue.

Book pointer: AIMA, knowledge representation chapters. Use this for temporal facts, constraints, and uncertainty.

## Phase 4: Knowledge Graph

Current:

- Character relationship graph

Target:

- Story knowledge graph

Nodes:

- Characters
- Places
- Objects
- Events
- Factions

Edges:

- loves
- hates
- lives_in
- owns
- fought
- discovered
- visited

Graph queries:

- Who loves Nahira?
- Who knows Ashan?
- Where has Nahira lived?
- What events involve Aezaric?

Success criteria:

- The story becomes queryable.

Book pointer: AIMA, knowledge representation; Jurafsky & Martin, relation extraction.

## Phase 5: Reasoning Engine

Current:

- Direct contradiction detection

Target:

- Inference-based validation

### Rule Engine

Example:

- Fact: Stefan cannot die.
- New fact: Stefan died permanently.
- Inference: contradiction.

### Derived Facts

Example:

- Aezaric father_of X.
- X father_of Y.
- Infer: Aezaric grandfather_of Y.

### Story Logic

Detect:

- Contradictions
- Missing consequences
- Broken world rules

Book pointer: AIMA, first-order logic and inference chapters.

## Phase 6: Writer Intelligence

**Goal:** Move beyond continuity checking.

### Character Arc Analysis

Track:

- Emotional state
- Growth
- Relationship evolution

Example:

```text
Ashan
Distrust
-> Curiosity
-> Affection
-> Love
```

### Plotline Tracking

Major plotlines become tracked objects.

Example:

- Plotline: The Lost Crown
- Status: Introduced, Active, Resolved

### Story Health Dashboard

Show:

- Main characters
- Unresolved arcs
- Missing payoffs
- Relationship evolution
- Timeline gaps

## Phase 7: Scale And Production

Only after previous phases.

### Background Jobs

Use Celery and Redis for:

- Extraction
- Validation
- Summaries

### Realtime Updates

Use SSE or WebSocket updates for long-running analysis and validation workflows.

### Semantic Retrieval

Use Postgres and `pgvector` for:

- Similar scenes
- Memory retrieval
- Context selection

Book pointer: DDIA Ch. 10 and Ch. 11, batch processing and stream processing. Use these once extraction and validation need production job orchestration.

## Long-Term Vision

InferStories should evolve into a **Narrative Operating System**.

Capabilities:

- Understand stories.
- Track continuity.
- Track timelines.
- Track character arcs.
- Build knowledge graphs.
- Answer questions.
- Explain contradictions.
- Suggest missing narrative links.

The system should ultimately reason over stories rather than merely store them.

