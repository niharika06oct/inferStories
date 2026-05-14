# inferStories

Monorepo for **story continuity memory**: a FastAPI backend (`apps/api`) stores stories, scenes, structured claims, and **persisted validation issues** when later scenes contradict earlier facts. A Next.js app (`apps/web`) provides a **single-page workflow** (create story → add scenes/claims → view issues with polling).

**Repo:** [github.com/niharika06oct/inferStories](https://github.com/niharika06oct/inferStories)

## Repository layout

| Path | Role |
|------|------|
| `apps/api` | FastAPI + SQLAlchemy + Alembic + PostgreSQL (`psycopg`) |
| `apps/web` | Next.js UI calling the API (see `lib/api.ts`, `app/StoryWorkspace.tsx`) |

## Prerequisites

- **Python 3.11+** and a venv under `apps/api/.venv` (or create one and `pip install -r requirements.txt`)
- **PostgreSQL** (local or Docker)
- **Node.js** + **pnpm** for the frontend

## Database

1. Create the database (once):

   ```bash
   createdb writers_ai_memory
   ```

2. Connection string (default in code):

   `postgresql+psycopg://postgres:postgres@localhost:5432/writers_ai_memory`

   Override with **`DATABASE_URL`** if your credentials differ.

3. **Migrations:** schema is applied with **Alembic** on API startup (`alembic upgrade head`), using `apps/api/alembic.ini` and `apps/api/alembic/`. You can also run upgrades manually from `apps/api`:

   ```bash
   cd apps/api && source .venv/bin/activate
   alembic upgrade head
   ```

   The initial revision creates all tables, including a **unique constraint** on `(story_id, scene_number)` so a story cannot have two scenes with the same number (API returns **409** on conflict).

## Run the API

```bash
cd apps/api
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

- OpenAPI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- CORS allows the default Next dev origins (`localhost:3000`, etc.) for browser `fetch`.

## Run the web app

1. Optional: copy `apps/web/.env.local.example` to `apps/web/.env.local` and set **`NEXT_PUBLIC_API_BASE_URL`** if the API is not on `http://127.0.0.1:8000`.

2. Start Next:

   ```bash
   cd apps/web
   pnpm install
   pnpm dev
   ```

3. Open [http://localhost:3000](http://localhost:3000): create a story, submit scenes with one or more claims, and watch **validation issues** update (**poll every 4s** plus manual **Refresh**).

## Backend tests

From `apps/api` with the venv active:

```bash
pytest
```

Tests use an in-memory SQLite database (`SKIP_ALEMBIC_ON_STARTUP=1`) and cover the contradiction flow, duplicate scene rejection, and **`validate_scene_claims`** behavior.

## HTTP API (MVP)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness: `{"status":"ok"}` |
| `POST` | `/stories` | Create a story (`title`, optional `description`) |
| `POST` | `/stories/{story_id}/scenes` | Add a scene (`scene_number`, `text`, `claims[]`). Returns **409** if `scene_number` duplicates for that story |
| `POST` | `/stories/{story_id}/validate` | List stored **`ValidationIssue`** rows (includes **`scene_number`**, timestamps, ids for UX) |

**Story IDs** are integer primary keys.

**Claims** in JSON use the field **`object`** for the triple’s object slot.

### Continuity rule

When a new scene is saved, each new claim is compared to claims in **earlier** scenes (lower `scene_number`). Same **`subject`** + **`predicate`** but different **`object`** → a stored issue: **`high`** if either side is **`is_major_plotline`**, else **`medium`**.

### Example: contradiction (curl)

```bash
# 1) Create story — note returned "id"
curl -s -X POST http://127.0.0.1:8000/stories \
  -H "Content-Type: application/json" \
  -d '{"title":"The Ashen Oath","description":"Fantasy political thriller"}'

# 2) Scene 1 — major claim (use your story id)
curl -s -X POST http://127.0.0.1:8000/stories/1/scenes \
  -H "Content-Type: application/json" \
  -d '{"scene_number":1,"text":"Asha swears she will always trust Rohan.","claims":[{"subject":"Asha","predicate":"trusts","object":"Rohan","is_major_plotline":true}]}'

# 3) Scene 2 — contradicting major claim
curl -s -X POST http://127.0.0.1:8000/stories/1/scenes \
  -H "Content-Type: application/json" \
  -d '{"scene_number":2,"text":"Asha never trusted Rohan.","claims":[{"subject":"Asha","predicate":"trusts","object":"Nobody","is_major_plotline":true}]}'

# 4) Issues
curl -s -X POST http://127.0.0.1:8000/stories/1/validate
```

## Workflow (high level)

```mermaid
flowchart TD
    A[Install Python, Node, pnpm, PostgreSQL] --> B[Clone repo + createdb]
    B --> C[apps/api venv + DATABASE_URL]
    C --> D[uvicorn — Alembic migrates on startup]
    D --> E[Next.js + NEXT_PUBLIC_API_BASE_URL]
    E --> F[POST /stories → scenes → validate / poll]
```

## Roadmap (scale & UX)

Planned next steps (not implemented yet):

- **Background jobs:** claim extraction / heavy validation on a **Redis-backed queue** so HTTP stays fast.
- **Realtime:** **SSE or WebSocket** push for new issues instead of only polling.
- **Issues model:** dedupe keys, stable references to conflicting pairs, richer payloads for editors.

---

Dependencies are listed in **`apps/api/requirements.txt`**.
