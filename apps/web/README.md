# inferStories Web App

Next.js writer workspace for inferStories. It talks to the FastAPI backend in `apps/api`, the auth service, and the grammar-check proxy.

## Local Setup

```bash
cp .env.local.example .env.local
pnpm dev
```

Set `API_PROXY_TARGET=http://127.0.0.1:8001` in `.env.local` so `/api/upstream/*` routes reach the FastAPI app. Restart `pnpm dev` after env changes.

Open [http://localhost:3000](http://localhost:3000).

## Workspace Features

- Library page for story browsing, story creation, and manuscript import (`.docx`, `.txt`, `.md`).
- Story editor with chapter selection, new chapter creation, chapter deletion, autosave, POV character capture, grammar underlines, and markdown export.
- Memory analysis via **Save & analyze memory**, which asks the API to extract claims, resolve entities/aliases, persist claims, and rerun continuity validation.
- Claims review panels for suggested, accepted, and rejected claims. Claim actions call the API and refresh the current chapter plus continuity results.
- Continuity review panels split open issues from handled issues. Use **Fixed** or **Reject** to move resolved noise out of the active review list.
- Relationship graph panel for entity connections discovered from accepted story claims.

## Important Files

- `app/StoryEditor.tsx` - main writer workspace.
- `components/WorkspaceRightPanel.tsx` - accordion panel for continuity, graph, and claim review.
- `components/ContinuityIssuesList.tsx` - continuity issue cards and fixed/rejected actions.
- `components/RelationshipGraphView.tsx` - graph visualization.
- `components/ClaimsReviewPanel.tsx` - claim approval/rejection UI.
- `lib/api.ts` - typed API client for the Next proxy/FastAPI backend.
- `lib/claimEvidenceSpan.ts` - claim and continuity evidence anchor matching for editor focus/highlight.

## Dev Commands

```bash
pnpm install
pnpm dev
pnpm lint
pnpm typecheck
```

## Current Known Gap

Text focus/highlight after clicking a claim or continuity issue is improved but still not fully reliable in every case. The deferred bug is tracked in `docs/BUG_BACKLOG.md`.
