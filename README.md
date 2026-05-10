# inferStories

Monorepo for **story continuity memory**: a FastAPI backend (`apps/api`) stores stories, scenes, structured claims, and **persisted validation issues** when later scenes contradict earlier facts. A Next.js app (`apps/web`) is scaffolded for a future UI.

## Repository layout

| Path | Role |
|------|------|
| `apps/api` | FastAPI + SQLAlchemy + PostgreSQL (`psycopg`) |
| `apps/web` | Next.js frontend (not yet wired to the API) |

## Prerequisites

- **Python 3.11+** (backend virtualenv under `apps/api/.venv` locally)
- **PostgreSQL** reachable from the machine running the API
- **Node.js** + **pnpm** (for `apps/web` when you develop the UI)

Optional: Docker for Postgres if you do not run it natively.

## Database

1. Create the database (once):

   ```bash
   createdb writers_ai_memory
   ```

2. Connection string (default in code):

   `postgresql+psycopg://postgres:postgres@localhost:5432/writers_ai_memory`

   Override with **`DATABASE_URL`** if your user, password, host, or database name differ.

Tables are created automatically on API startup (`create_all`).

## Backend dependencies

Core packages used by the API: `fastapi`, `uvicorn`, `pydantic`, `sqlalchemy`, `psycopg` (binary driver in practice). `alembic` may be present in the environment for future migrations; the MVP relies on SQLAlchemy metadata creation at startup.

## Run the API

From the repo root:

```bash
cd apps/api
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

- OpenAPI docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## HTTP API (MVP)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness: `{"status":"ok"}` |
| `POST` | `/stories` | Create a story (`title`, optional `description`) |
| `POST` | `/stories/{story_id}/scenes` | Add a scene (`scene_number`, `text`, `claims[]`) |
| `POST` | `/stories/{story_id}/validate` | Return **stored** validation issues for that story |

**Story IDs** are integer primary keys (e.g. `1` after the first create).

**Claims** in JSON use the field name **`object`** for the claim object (subject / predicate / object triple). Internally the DB column is named `object` as well.

### Continuity rule

When a new scene is added, each new claim is checked against **earlier scenes** (lower `scene_number`) in the same story. If the same **`subject`** and **`predicate`** appear but the **`object`** differs, a **`ValidationIssue`** row is stored: **`high`** severity if either claim is marked **`is_major_plotline`**, otherwise **`medium`**.

`POST /stories/{story_id}/validate` returns those persisted issues (newest first by issue id).

### Example: contradiction flow

Assume story id **`1`** after create.

**1. Create story**

```bash
curl -s -X POST http://127.0.0.1:8000/stories \
  -H "Content-Type: application/json" \
  -d '{"title":"The Ashen Oath","description":"Fantasy political thriller"}'
```

**2. Scene 1 — major claim**

```bash
curl -s -X POST http://127.0.0.1:8000/stories/1/scenes \
  -H "Content-Type: application/json" \
  -d '{
    "scene_number": 1,
    "text": "Asha swears she will always trust Rohan.",
    "claims": [
      {"subject":"Asha","predicate":"trusts","object":"Rohan","is_major_plotline": true}
    ]
  }'
```

**3. Scene 2 — contradicting claim**

```bash
curl -s -X POST http://127.0.0.1:8000/stories/1/scenes \
  -H "Content-Type: application/json" \
  -d '{
    "scene_number": 2,
    "text": "Asha never trusted Rohan.",
    "claims": [
      {"subject":"Asha","predicate":"trusts","object":"Nobody","is_major_plotline": true}
    ]
  }'
```

**4. List stored issues**

```bash
curl -s -X POST http://127.0.0.1:8000/stories/1/validate
```

You should see a **high** severity issue referencing the major plotline conflict.

## Run the web app (optional)

```bash
cd apps/web
pnpm install
pnpm dev
```

Visit the URL printed in the terminal (commonly [http://localhost:3000](http://localhost:3000)). The UI does not yet call the backend; that is the next milestone.

## Workflow (high level)

```mermaid
flowchart TD
    A[Install Python, Node, pnpm, PostgreSQL] --> B[Clone repo + create DB]
    B --> C[apps/api venv + DATABASE_URL]
    C --> D[uvicorn app.main:app]
    D --> E[POST /stories]
    E --> F[POST /stories/id/scenes with claims]
    F --> G[Contradictions persisted as ValidationIssue]
    G --> H[POST /stories/id/validate returns issues]
```

## Next milestone

Wire **`apps/web`** to **`apps/api`** for a single-page flow:

1. Create story  
2. Add scene + claims  
3. Show validation issues after each scene (poll or refresh)

**Repo:** [github.com/niharika06oct/inferStories](https://github.com/niharika06oct/inferStories)
