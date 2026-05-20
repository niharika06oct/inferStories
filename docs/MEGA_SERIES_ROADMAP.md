# Mega-series author roadmap (living TODO)

Track features aimed at universe-scale continuity (e.g. multi-book series, shared worlds).  
**Update this file as you ship items, reprioritize, or add notes.**

| Field | Value |
|-------|--------|
| **Last updated** | 2026-05-17 |
| **Current product** | Single story → scenes → manual subject/predicate/object claims; 2 backward contradiction rules |
| **North star** | Universe bible + continuity engine for epic / shared-world fiction |

---

## How to use this file

- Change `[ ]` → `[x]` when done (or `[-]` for in progress).
- Add **Notes** under any item (design links, blockers, PRs).
- Add new items under the right tier; don’t delete history—strike through or move to **Done** at the bottom.

---

## Tier 1 — Must-have for “sellable” to a mega-series author

- [ ] **Universe → works → chapters/scenes**  
  Westeros as one universe; *A Game of Thrones*, *Fire & Blood*, etc. as works; chapters/POV as ordered units.  
  - Notes:

- [ ] **Character & place registry**  
  Canonical IDs, aliases, houses, birth/death (or “unknown”), so claims attach to **entities**, not spelling variants.  
  - Notes:

- [ ] **Timeline-aware facts**  
  Facts valid “as of” a date, chapter, or book—not only “scene 47 vs scene 12.”  
  - Notes:

- [ ] **Canon & draft layers**  
  Published vs working draft; optional “non-canon” branches without polluting main continuity.  
  - Notes:

- [ ] **Automatic fact candidates from prose**  
  AI (or rules) proposes claims from scenes; author approves—manual triples alone won’t scale to huge output.  
  - Notes:

- [ ] **Smarter contradiction detection**  
  Negation (“does not trust”), temporal change (“was alive” → “is dead”), POV-limited knowledge, synonyms via entity IDs.  
  - Notes:

- [ ] **Search & dashboards**  
  “All facts about Daenerys,” “open contradictions,” “facts introduced in book 3 never referenced again.”  
  - Notes:

---

## Tier 2 — Differentiators he’d actually feel day to day

- [ ] **POV tagging** — fact known only to Tyrion vs world-true.  
  - Notes:

- [ ] **Genealogy & succession** — lords, heirs, marriages (structured, not only triples).  
  - Notes:

- [ ] **Maps & locations** — where characters are when (reduces “they can’t be in King’s Landing and Winterfell”).  
  - Notes:

- [ ] **Import at scale** — existing manuscripts, encyclopedias, structured wikis (with licensing care).  
  - Notes:

- [ ] **Collaboration** — editors, fact-checkers, permissions, audit trail.  
  - Notes:

- [ ] **Export** — bible PDF, wiki, writers’ room briefs.  
  - Notes:

---

## Tier 3 — “Enterprise author platform”

- [ ] **Versioning** — git-like history per chapter.  
  - Notes:

- [ ] **Link to external bibles** — Notion, Scrivener, etc.  
  - Notes:

- [ ] **Performance** — indexed graph or search (Elasticsearch, vector DB) over huge corpora.  
  - Notes:

- [ ] **Privacy** — air-gapped or self-hosted; unpublished work must not leak.  
  - Notes:

---

## Backlog / ideas (unprioritized)

_Add scratch items here before promoting to a tier._

- 

---

## Done

_Move completed items here with date and optional PR link._

- 

---

## Data model direction (reference)

Evolve from flat `subject | predicate | object` strings toward:

- **Entity** (character, place, house, …) with aliases  
- **Fact** (`subject_id`, `predicate_type`, `object_id`, scope, `valid_from` / `valid_until`, canon layer)  
- **Scene / chapter** as prose anchor and ordering for validation  

See also: `apps/api/app/models.py`, `apps/api/app/validation.py`.
