# InferStories Production Readiness: 1 Month Plan

Spend the next 3 weeks making InferStories:

- Reliable
- Fast
- Predictable
- Useful

The biggest near-term risk is not poor AI. It is this product failure loop:

```text
Writer uploads manuscript
-> Extraction misses things
-> Graphs look wrong
-> Validation feels random
-> Writer never comes back
```

The fastest path to a usable product is not making it smarter. It is making it trustworthy enough that writers are willing to let it remember things for them.

## Production Readiness Roadmap: Next 3 Weeks

## Week 1: Stability And Trust

**Goal:** Make the product feel trustworthy.

Book pointer: DDIA Ch. 1, reliability and maintainability.

### Task 1: Fix Extraction Quality

Current problems:

- Water becomes a character.
- Phoenix becomes a relationship target.

Implement:

- spaCy
- Entity typing
- Graph eligibility filtering

Success criteria:

- Characters are more than 90% correct.

### Task 2: Entity Review UI

Add tabs for:

- Characters
- Places
- Objects
- Groups

Writers can:

- Merge entities.
- Rename entities.
- Delete wrong entities.
- Change entity type.

Example:

- `Jon`
- `Jon Snow`
- Action: merge into one canonical entity.

This alone massively increases trust.

### Task 3: Claim Editing

Current actions:

- Approve
- Reject

Add:

- Edit

Writers should be able to correct:

```text
Ashan loves Nahira
```

to:

```text
Ashan desires Nahira
```

without database surgery.

### Task 4: Extraction Confidence

Show claim confidence scores:

- 95%
- 82%
- 61%

Writers instantly understand uncertainty when the system exposes confidence instead of pretending every extraction is equally reliable.

## Week 2: Memory And Continuity

**Goal:** Make continuity genuinely useful.

Book pointer: AIMA, knowledge representation and first-order logic.

### Task 5: Canon Memory

Introduce memory levels:

- Canon
- Accepted
- Draft
- Rejected

Today, `approved`, `needs_review`, and `rejected` are not enough.

Canon means:

```text
This is truth.
```

### Task 6: Major Plotlines

Add `major_plotline` as a tracked entity type.

Examples:

- Lost Crown
- Ashan/Nahira Romance
- Civil War

Track status:

- Introduced
- Active
- Resolved

This becomes a killer feature because writers think in plotlines, not only entities and claims.

### Task 7: Better Validation

Current validation:

```text
claim A vs claim B
```

Target validation:

- Issue
- Why
- Evidence
- Suggested fix

Writers need plain-language explanations, not database language.

### Task 8: Character Cards

Each character gets:

- Description
- Aliases
- Relationships
- Claims
- Mentions
- Importance

This is where readers and writers start saying:

```text
Wow.
```

## Week 3: Production MVP

**Goal:** People can actually use it.

Book pointer: DDIA Ch. 3, storage and retrieval.

### Task 9: Chunk Hashing

Store:

- `chunk_hash`

Only reprocess changed chunks.

Reduces:

- Cost
- Latency
- Bugs

### Task 10: LLM Cache

Store:

- `prompt_hash`
- `input_hash`
- `response`

Never pay twice for the same analysis.

### Task 11: Background Jobs

Current flow:

```text
Save
-> Wait
```

Target flow:

```text
Save
-> Job queued
-> Processing...
-> Results appear
```

Use:

- Celery
- Redis

### Task 12: Error Visibility

Current failure mode:

```text
OpenAI failed
```

buried somewhere invisible.

Target failure mode:

```text
Analysis failed
Reason: quota exceeded
```

Users should understand immediately what happened and whether they can fix it.

## What Not To Build Yet

Avoid:

- Neo4j
- Microservices
- Realtime collaboration
- Voice
- Mobile app
- Multi-tenant enterprise features

These add complexity without increasing immediate product value.

## Production MVP Definition

At the end of 3 weeks, a writer should be able to:

- Upload a 100 chapter novel.
- Get characters, places, relationships, continuity issues, character cards, and plotlines.
- Fix entities, claims, and continuity issues.
- Trust that memory updates correctly.
- Trust that re-analysis preserves approved facts.
- Trust that graphs are mostly correct.

If InferStories achieves this, it already has something real writers can use.

## Effort Allocation

For the next 3 weeks:

| Area | Allocation |
|---|---:|
| Extraction quality | 40% |
| Writer editing/control | 25% |
| Performance/caching | 20% |
| Validation UX | 10% |
| Fancy graphs | 5% |

## After MVP: Next 3-12 Months

Once the production MVP is trustworthy, start adding the "wow" features.

### Phase 2: Event Intelligence

Book pointer: Jurafsky & Martin, information extraction; DDIA, data models.

Build:

- Event model
- Event extraction

### Phase 3: Timeline Engine

Book pointer: AIMA, knowledge representation.

Build:

- Timeline engine

### Phase 4: Reasoning Engine

Book pointer: AIMA, inference.

Build:

- Reasoning engine

### Phase 5: Story Q&A

Book pointer: Jurafsky & Martin, coreference; AIMA, knowledge agents.

Build story questions such as:

- Who knows Ashan's secret?
- Which characters have met Nahira?
- What unresolved plotlines exist?

