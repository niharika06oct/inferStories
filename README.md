# inferStories

Monorepo for **story continuity memory**: a FastAPI backend (`apps/api`) stores stories, scenes, structured claims, and **persisted validation issues** when later scenes contradict earlier facts. A Next.js app (`apps/web`) provides a **writer workspace** — browse stories, import manuscripts, edit scenes, and review continuity issues in real time.

**Repo:** [github.com/niharika06oct/inferStories](https://github.com/niharika06oct/inferStories)

## Repository layout

| Path | Role |
|------|------|
| `apps/api` | FastAPI + SQLAlchemy + Alembic + PostgreSQL (`psycopg`) |
| `apps/web` | Next.js writer workspace (`app/StoryEditor.tsx`, review panels, import helpers, API client) |
| `apps/api/scripts/reset_local_postgres.sql` | Optional local Postgres role + database bootstrap |

## Prerequisites

- **Python 3.11+** and a venv under `apps/api/.venv`
- **PostgreSQL 16** (local Homebrew or Docker)
- **Node.js** + **pnpm** for the frontend

## Database

1. **Configure credentials** — copy `apps/api/env.example` to `apps/api/.env` and set **`DATABASE_URL`** (required; the API will not start without it):

   ```bash
   cp apps/api/env.example apps/api/.env
   # Edit DATABASE_URL — URL-encode special characters in passwords (@ → %40, etc.)
   ```

   Example:

   `postgresql+psycopg://writers_app:YOUR_PASSWORD@localhost:5432/writers_ai_memory`

2. **Bootstrap role + database** (first time on a machine), or create manually:

   ```bash
   psql postgres -f apps/api/scripts/reset_local_postgres.sql
   ```

   Set the password in that script to match `.env`.

3. **Migrations:** schema is applied with **Alembic** on API startup (`alembic upgrade head`). Manual upgrade:

   ```bash
   cd apps/api && source .venv/bin/activate
   alembic upgrade head
   ```

   Skip startup migrations when debugging: `SKIP_ALEMBIC_ON_STARTUP=1`.

   The schema includes a **unique constraint** on `(story_id, scene_number)` (API returns **409** on duplicate scene numbers).

## Run the API

```bash
cd apps/api
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Use **port 8001** if something else (Docker, EDB, Django) already uses **8000**.

- OpenAPI: [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)
- CORS allows Next dev origins (`localhost:3000`, etc.).

### Optional: AI features

Add to `apps/api/.env` for OpenAI-backed synopses, claim extraction, and optional semantic continuity judging. Without these settings, the app still runs with local heuristics and rule-only continuity validation.

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
# OPENAI_BASE_URL=https://api.openai.com/v1

# FASTUS pipeline debug + LLM fallback (see docs/LLM_FASTUS_INTEGRATION_OPTIONS.md)
# FASTUS_DEBUG=1       # Stage 0–9 lifecycle lines on API stderr at startup + on Save & analyze memory
# FASTUS_LLM_LEGACY=1  # Full-chunk LLM extract when FASTUS claim drafts are empty

# Optional: use AI only after rule-based continuity candidates are found.
# CONTINUITY_AI_JUDGE_ENABLED=1
# CONTINUITY_AI_MODEL=gpt-4o-mini
```

Optional NLP: `python -m spacy download en_core_web_sm` (enables spaCy-backed FASTUS stages 1–4; regex fallback if missing).

## Run the web app

1. Copy env and point the dev proxy at FastAPI:

   ```bash
   cp apps/web/.env.local.example apps/web/.env.local
   ```

   Ensure **`API_PROXY_TARGET=http://127.0.0.1:8001`** matches your API port. Restart `pnpm dev` after changing env files.

2. Install and start:

   ```bash
   cd apps/web
   pnpm install
   pnpm dev
   ```

3. Open [http://localhost:3000](http://localhost:3000).

### Web UI overview

| Area | What you can do |
|------|-----------------|
| **Left — Your stories** | List all stories; **Import from this device** (`.docx`, `.txt`, `.md`); **+ New story** |
| **Left — Scenes & chapters** | Jump to a chapter, **Write new scene**, delete a chapter, download `.md` export |
| **Center** | Story metadata; chapter text with **autosave**, in-editor **grammar underlines** (right-click to apply/dismiss), **POV character**, **Save & analyze memory**, story-memory summary |
| **Right — accordion** | **Open / handled continuity**, **relationship graph**, **New / Accepted / Rejected claims** (expand one section at a time; click a claim to jump to evidence when anchors are available) |

**Import flow:** pick a file → choose **new** or **existing** story → name scenes → import. If description is empty, a synopsis is generated from scene text after import.

**Design:** [Open Design](https://opendesigner.io/quickstart) “Neutral Modern” tokens, warm paper background, botanical line art in `apps/web/public/decor/`.

For production or direct API calls from the browser, set **`NEXT_PUBLIC_API_BASE_URL`** to your API origin (skips the Next proxy).

## Backend tests

From `apps/api` with the venv active:

```bash
pytest
```

Tests use in-memory SQLite (`SKIP_ALEMBIC_ON_STARTUP=1`) and cover stories/scenes CRUD, entity resolution, claim extraction and dedupe, FASTUS stages (parse, entities, phrases, relations, semantic patterns, LLM refine, merge, validation), relationship graph output, continuity validation/judging, issue resolution, duplicate scene rejection, and description generation.

Use the project venv for pytest: `apps/api/.venv/bin/python -m pytest` (see `.cursor/rules/spacy-venv-python.mdc`).

## HTTP API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness: `{"status":"ok"}` |
| `GET` | `/stories` | List stories (with `scene_count`, `created_at`) |
| `POST` | `/stories` | Create a story (`title`, optional `description`) |
| `GET` | `/stories/{story_id}` | Get one story |
| `PATCH` | `/stories/{story_id}` | Update `title` and/or `description` |
| `POST` | `/stories/{story_id}/generate-description` | AI/heuristic synopsis from scenes; saves to story |
| `GET` | `/stories/{story_id}/entities` | List canonical entities and aliases for a story |
| `GET` | `/stories/{story_id}/relationship-graph` | Build the character/entity relationship graph |
| `GET` | `/stories/{story_id}/scenes` | List scenes (summary) |
| `GET` | `/stories/{story_id}/scenes/{scene_id}` | Scene detail with claims |
| `POST` | `/stories/{story_id}/scenes` | Add a scene (`scene_number`, `text`, `claims[]`). **409** if duplicate `scene_number` |
| `PATCH` | `/stories/{story_id}/scenes/{scene_id}` | Update scene text, number, and claims (re-validates) |
| `DELETE` | `/stories/{story_id}/scenes/{scene_id}` | Delete a chapter and its derived claims/issues |
| `PATCH` | `/stories/{story_id}/scenes/{scene_id}/claims/{claim_id}` | Approve, reject, or edit a claim; revalidates the scene |
| `POST` | `/stories/{story_id}/validate` | List stored **`ValidationIssue`** rows |
| `PATCH` | `/stories/{story_id}/validation-issues/{issue_id}` | Mark a continuity issue as `open`, `fixed`, or `rejected` |

**Story IDs** are integer primary keys.

**Claims** in JSON use the field **`object`** for the triple’s object slot (stored as `claim_object` in the DB).

### FASTUS extraction pipeline (current)

inferStories is evolving from regex + LLM toward a **FASTUS-inspired, deterministic-first** pipeline (reference: [`docs/FASTUS_ChatGPT.md`](docs/FASTUS_ChatGPT.md)). **Stages 0–9 are implemented and instrumented**; primary claim output today still comes from **structural + family regex** plus **Stage 6 LLM** (refine drafts or legacy full-chunk extract).

| Stage | What it does |
|-------|----------------|
| **0** | Negation/polarity on claims, fragment rejection before persist |
| **1** | Token/sentence parse (spaCy + regex fallback) |
| **2** | Entity candidates (NER, proper nouns, registry aliases) |
| **3** | Phrase candidates (noun/verb/possessive/family, negation flags) |
| **4** | Relation candidates (SVO, coreference MVP) |
| **5** | Semantic patterns → claim drafts |
| **6** | LLM **refine** drafts; `FASTUS_LLM_LEGACY=1` → full-chunk extract when drafts empty |
| **7** | Polarity-aware merge, cross-scene canon suppress, stale claim prune on re-save |
| **8** | Polarity-aware continuity validation + relationship graph |
| **9** | Validation issue enrichment (both-side evidence, explanation, suggested fix) |

**Shadow vs primary:** Stages 1–5 run on every **Save & analyze memory** and populate the **Extraction details** panel (`FastusDebugSection`). Regex layers still drive most persisted claims until FASTUS promotion.

**Debug:** Set `FASTUS_DEBUG=1` — API startup prints a banner; stage BEGIN/COMPLETE/SKIP lines appear in the **uvicorn terminal** on analyze (not autosave).

**Next direction:** How to combine LLM recall with FASTUS grounding — three options in [`docs/LLM_FASTUS_INTEGRATION_OPTIONS.md`](docs/LLM_FASTUS_INTEGRATION_OPTIONS.md) for review.

### Continuity memory

When a scene is saved or updated with extraction enabled, inferStories:

1. Extracts claims from structural patterns, family/relationship language, FASTUS drafts (refined by LLM when present), optional legacy full-chunk LLM, and heuristic fallbacks.
2. Resolves subjects and objects to canonical story entities where possible, including aliases like short names and nicknames.
3. Filters placeholder or unresolved entities such as `Narrator` and unresolved first-person pronouns when no POV character is known.
4. Prunes stale extracted claims when chapter text changes; suppresses duplicates already canonized in earlier chapters.
5. Compares current claims against accepted claims from **earlier** scenes (polarity-aware).
6. Saves persisted `ValidationIssue` rows with evidence anchors, conflicting claim references, resolution status, judge metadata, and enriched explanations.

Continuity checking is intentionally conservative. It focuses on explicit incompatible objects and explicit predicate oppositions, and treats emotional progression more carefully. For example, "uncomfortable with" is not automatically treated as "distrusts." Optional AI judging can classify rule candidates as `hard_contradiction`, `soft_tension`, `compatible_progression`, or `not_issue`; only hard contradictions and soft tensions are shown.

Handled issues can be moved out of the active review list by marking them **Fixed** or **Rejected** in the web app.

### Example: contradiction (curl)

Replace `8001` with your API port and use the returned story `id`.

```bash
# 1) Create story
curl -s -X POST http://127.0.0.1:8001/stories \
  -H "Content-Type: application/json" \
  -d '{"title":"The Ashen Oath","description":"Fantasy political thriller"}'

# 2) Scene 1 — major claim
curl -s -X POST http://127.0.0.1:8001/stories/1/scenes \
  -H "Content-Type: application/json" \
  -d '{"scene_number":1,"text":"Asha swears she will always trust Rohan.","claims":[{"subject":"Asha","predicate":"trusts","object":"Rohan","is_major_plotline":true}]}'

# 3) Scene 2 — contradicting major claim
curl -s -X POST http://127.0.0.1:8001/stories/1/scenes \
  -H "Content-Type: application/json" \
  -d '{"scene_number":2,"text":"Asha never trusted Rohan.","claims":[{"subject":"Asha","predicate":"trusts","object":"Nobody","is_major_plotline":true}]}'

# 4) List issues
curl -s -X POST http://127.0.0.1:8001/stories/1/validate
```

## Workflow (high level)

inferStories splits **writing** (browser + Next.js), **memory** (FastAPI + Postgres), and **optional AI** (OpenAI for extraction/synopses). The diagrams below are the system design for how the website behaves end-to-end.

### System architecture

```mermaid
flowchart TB
    subgraph Browser["Browser — localhost:3000"]
        Pages["Pages: Library · StoryEditor"]
        Editor["Chapter editor<br/>underlines · claim highlight"]
    end

    subgraph Web["apps/web — Next.js"]
        Upstream["/api/upstream/* → FastAPI"]
        AuthRoute["/api/auth/* → auth-service"]
        LTProxy["/api/writing/check → LanguageTool"]
    end

    subgraph Backend["apps/api — FastAPI :8001"]
        API["REST: stories · scenes · claims · entities · validate"]
        Extract["Claim extraction<br/>FASTUS 0–9 · structural · family · LLM refine"]
        Registry["Entity registry<br/>canonical names · aliases · graph eligibility"]
        Canon["Continuity judge<br/>rules first · optional AI for ambiguous candidates"]
    end

    AuthSvc["auth-service :4000<br/>session / Bearer token"]
    DB[(PostgreSQL<br/>stories · scenes · claims · issues)]
    OpenAI["OpenAI API<br/>optional"]
    LT["LanguageTool<br/>grammar / spelling"]

    Pages --> Upstream --> API
    Pages --> AuthRoute --> AuthSvc
    Editor --> LTProxy --> LT
    API --> AuthSvc
    API --> DB
    API --> Extract --> Registry --> DB
    API --> Canon --> DB
    Extract --> OpenAI
    Canon --> OpenAI
```

| Request path | Purpose |
|--------------|---------|
| `/api/upstream/...` | Story/scene CRUD, claims, continuity issues (Bearer from auth-service) |
| `/api/auth/...` | Sign-in, session cookies/token for the UI |
| `/api/writing/check` | Server-side grammar check (avoids CORS to LanguageTool) |

### Writer workflow (website functionality)

```mermaid
flowchart TD
    Start([Library / home]) --> SignIn{Authenticated?}
    SignIn -->|no| Login[Login via auth-service]
    Login --> Start
    SignIn -->|yes| Hub[Your stories]

    Hub --> NewStory[+ New story]
    Hub --> Import[Import .docx / .txt / .md]
    Hub --> OpenStory[Open story → StoryEditor]

    Import --> Split[Split into chapters] --> Hub
    NewStory --> Meta[Title · description] --> OpenStory

    OpenStory --> PickChapter[Select or create chapter]

    subgraph Center["Center — chapter editor"]
        PickChapter --> Write[Edit chapter text + optional POV character]
        Write --> Autosave["Autosave (~2s)<br/>PATCH text only<br/>run_extraction = false"]
        Write --> Grammar["Grammar check (~3.5s debounce)<br/>blue underlines in editor"]
        Grammar --> RCMenu["Right-click underline<br/>Apply fix or Dismiss<br/>dismissals persist in localStorage"]
        PickChapter --> DeleteChapter["Delete chapter<br/>removes derived claims/issues"]
        Write --> Analyze["Save & analyze memory<br/>run_extraction = true"]
    end

    subgraph Extract["API — extraction on analyze"]
        Analyze --> Chunk[Chunk long chapters]
        Chunk --> Fastus[FASTUS 1–5 shadow<br/>parse · entities · relations · drafts]
        Chunk --> Structural[Structural + family regex<br/>POV-aware I → character]
        Fastus --> LLM[Stage 6 LLM refine drafts<br/>or FASTUS_LLM_LEGACY full extract]
        Structural --> Registry[Resolve canonical entities<br/>aliases · no Narrator placeholders]
        LLM --> Registry
        Registry --> StoreClaims[(Save claims with status)]
        StoreClaims --> Confidence["approved / needs_review / suggested"]
    end

    StoreClaims --> Validate[Validate vs accepted claims in earlier chapters]
    Validate --> Judge[Rules-first judge<br/>optional AI classification]
    Judge --> StoreIssues[(Persist ValidationIssue rows<br/>anchors · source · confidence · resolution)]

    subgraph Right["Right panel — accordion sections"]
        StoreIssues --> Cont["Open continuity<br/>fixed · reject"]
        StoreIssues --> Handled["Handled continuity<br/>fixed / rejected"]
        StoreClaims --> Graph["Relationship graph"]
        Confidence --> NewC["New claims<br/>approve · reject"]
        Confidence --> Acc["Accepted claims"]
        Confidence --> Rej["Rejected claims<br/>hidden from New until opened"]
    end

    NewC -->|click claim card| Jump[Scroll chapter + amber highlight<br/>evidence quote in text]
    Cont -->|Refresh| Poll[Reload continuity list]
    Cont -->|Fixed / Reject| Handled

    Write --> ExportMd[Export story .md]
```

**Save behavior (important):**

| Action | API | Claims / continuity |
|--------|-----|---------------------|
| **Autosave** while typing | `PATCH` scene, `run_extraction: false` | Text + POV only; no new extraction |
| **Save & analyze memory** | `PATCH` or `POST` scene, `run_extraction: true` | Re-extracts claims for that chapter, re-runs continuity validation |
| **Approve / reject claim** | `PATCH` claim status | Moves claim between New / Accepted / Rejected in the UI |
| **Fixed / reject continuity** | `PATCH` validation issue | Moves handled issues out of the open continuity list |
| **Delete chapter** | `DELETE` scene | Removes the chapter plus its dependent claims and validation issues |

## Conceptual references

These are useful chapters/sections for understanding the current implementation choices:

- **DDIA:** Chapter 2, *Data Models and Query Languages* for the relational story/claim/entity model; Chapter 3, *Storage and Retrieval* for persisted validation issues as derived data.
- **Speech and Language Processing:** information extraction, named entity recognition, relation extraction, and coreference sections for claim extraction and alias/entity resolution.
- **AIMA:** knowledge representation and logical agents sections for treating accepted claims as story facts and continuity checks as reasoning over those facts.

### Local dev startup (quick)

```mermaid
flowchart LR
    PG[(Postgres)] --> API[uvicorn :8001]
    API --> Web[pnpm dev :3000]
    Auth[auth-service :4000] --> Web
    Web --> Browser[Open inferStories]
```

## Roadmap

Planned next steps:

- **FASTUS promotion:** pick LLM+FASTUS integration (see [`docs/LLM_FASTUS_INTEGRATION_OPTIONS.md`](docs/LLM_FASTUS_INTEGRATION_OPTIONS.md)); promote stages 1–5 from shadow to primary extractor.
- **Background jobs:** claim extraction / heavy validation on a **Redis-backed queue**.
- **Realtime:** **SSE or WebSocket** push for new issues instead of only polling.
- **Cloud import:** direct connectors (Google Drive, Notion, etc.) without manual export.

Longer-term product roadmap: [`docs/MEGA_SERIES_ROADMAP.md`](docs/MEGA_SERIES_ROADMAP.md).

---

Dependencies: **`apps/api/requirements.txt`**, **`apps/web/package.json`** (includes **mammoth** for `.docx` import).
