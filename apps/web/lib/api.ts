import { authHeaders } from "./auth-token";

/**
 * API base URL:
 * - In the browser, default is same-origin `/api/upstream` (see `next.config.ts` rewrites)
 *   so requests avoid CORS against FastAPI on :8000.
 * - Set `NEXT_PUBLIC_API_BASE_URL` to a full URL (e.g. production API) to skip the proxy.
 */
function apiBase(): string {
  const explicit = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (explicit?.trim()) {
    return explicit.replace(/\/$/, "");
  }
  if (typeof window !== "undefined") {
    return "/api/upstream";
  }
  return "http://127.0.0.1:8001";
}

function proxyUnreachableHint(status: number, body: string): string | null {
  const generic =
    body === "Internal Server Error" ||
    body.trim() === "" ||
    body.includes("<!DOCTYPE html>");
  if (status === 502 || status === 503 || (status === 500 && generic)) {
    return (
      "Cannot reach the FastAPI backend. In a terminal: start Postgres, then run " +
      "`cd apps/api && source .venv/bin/activate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8001`. " +
      "Ensure `apps/web/.env.local` has `API_PROXY_TARGET=http://127.0.0.1:8001` and restart `pnpm dev`."
    );
  }
  return null;
}

async function parseError(res: Response): Promise<string> {
  const t = await res.text();
  const proxyHint = proxyUnreachableHint(res.status, t);
  if (proxyHint) return proxyHint;

  try {
    const j = JSON.parse(t) as { detail?: unknown };
    const d = j.detail;
    if (typeof d === "string") {
      if (d === "Internal Server Error" && res.status >= 500) {
        return proxyUnreachableHint(res.status, t) ?? d;
      }
      return d;
    }
    if (Array.isArray(d)) {
      return d
        .map((item: { loc?: unknown[]; msg?: string }) =>
          Array.isArray(item.loc)
            ? `${item.loc.join(".")}: ${item.msg ?? ""}`
            : JSON.stringify(item),
        )
        .join("; ");
    }
    return t || res.statusText;
  } catch {
    return t || res.statusText;
  }
}

export type StoryOut = {
  id: number;
  title: string;
  description: string | null;
  created_at: string;
};

export type StoryListOut = StoryOut & {
  scene_count: number;
};

export type ClaimIn = {
  subject: string;
  predicate: string;
  object: string;
  is_major_plotline: boolean;
};

export type SceneOut = {
  id: number;
  story_id: number;
  scene_number: number;
  text: string;
  extraction?: SceneExtractionOut | null;
};

export type SceneSummaryOut = {
  id: number;
  story_id: number;
  scene_number: number;
  text: string;
  pov_character?: string | null;
  created_at: string;
  claim_count: number;
};

export type ClaimOut = {
  id: number;
  subject: string;
  predicate: string;
  object: string;
  is_major_plotline: boolean;
  claim_type?: string | null;
  claim_text?: string | null;
  target?: string | null;
  confidence: number;
  canon_level: string;
  status: string;
  evidence_text?: string | null;
  source: string;
  generation_origin?: string;
  created_at?: string | null;
  updated_at?: string | null;
  extracted_at?: string | null;
  chunk_index?: number | null;
  claim_version?: number;
  superseded_by_claim_id?: number | null;
  source_hash?: string | null;
};

export type FastusDebugEventOut = {
  stage: string;
  event: string;
  message: string;
  detail?: Record<string, string>;
};

export type ChunkExtractionDebugOut = {
  chunk_index: number;
  word_count: number;
  openai_attempted: boolean;
  openai_ok: boolean;
  fallback_used: boolean;
  structural_claims: number;
  llm_claims: number;
  entities: string[];
  fastus_token_count?: number;
  fastus_sentence_count?: number;
  fastus_has_dependencies?: boolean;
  fastus_entity_candidate_count?: number;
  fastus_phrase_candidate_count?: number;
  fastus_relation_candidate_count?: number;
  fastus_claim_draft_count?: number;
  fastus_llm_refined_count?: number;
  fastus_llm_rejected_count?: number;
  fastus_llm_cache_hit?: boolean;
  fastus_events?: FastusDebugEventOut[];
};

export type SceneExtractionOut = {
  source: string;
  chunk_count: number;
  word_count: number;
  claim_count: number;
  approved_count: number;
  needs_review_count: number;
  suggested_count: number;
  error?: string | null;
  duration_ms?: number;
  openai_attempted?: boolean;
  fallback_used?: boolean;
  large_chapter_warning?: boolean;
  structural_entity_count?: number;
  suppressed_structural_count?: number;
  generation_counts?: Record<string, number>;
  chunks?: ChunkExtractionDebugOut[];
  fastus_spacy_available?: boolean;
  fastus_stage0_negated_claims?: number;
  fastus_stage0_rejected_fragments?: number;
  fastus_events?: FastusDebugEventOut[];
};

export type SceneDetailOut = {
  id: number;
  story_id: number;
  scene_number: number;
  text: string;
  pov_character?: string | null;
  created_at: string;
  claims: ClaimOut[];
};

export type GraphSupportingClaimOut = {
  claim_id: number;
  predicate: string;
  claim_text: string | null;
  confidence: number;
  scene_number: number;
};

export type RelationshipGraphNodeOut = {
  id: string;
  entity_id: number;
  label: string;
  type: string;
  importance_score: number;
  mention_count: number;
  relationship_degree: number;
};

export type RelationshipGraphEdgeOut = {
  id: string;
  source: string;
  target: string;
  source_entity_id: number;
  target_entity_id: number;
  predicate: string;
  primary_relationship: string;
  sub_relationships: string[];
  strength: number;
  confidence: number;
  claim_count: number;
  status: string;
  supporting_claims: GraphSupportingClaimOut[];
};

export type RelationshipGraphOut = {
  story_id: number;
  nodes: RelationshipGraphNodeOut[];
  edges: RelationshipGraphEdgeOut[];
  meta: {
    canon_statuses: string[];
    relationship_predicate_count: number;
    approved_relationship_claim_count?: number;
    pending_preview_claim_count?: number;
    include_preview?: boolean;
  };
};

export async function fetchRelationshipGraph(
  storyId: number,
  options?: { includePreview?: boolean },
): Promise<RelationshipGraphOut> {
  const qs = options?.includePreview ? "?include_preview=true" : "";
  const res = await fetch(
    `${apiBase()}/stories/${storyId}/relationship-graph${qs}`,
    { headers: await authHeaders() },
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<RelationshipGraphOut>;
}

export type ContinuityResolutionStatus = "open" | "fixed" | "rejected";

export type ValidationIssueOut = {
  id: number;
  story_id: number;
  scene_id: number;
  scene_number: number;
  severity: string;
  message: string;
  conflicting_claim_id: number | null;
  conflicting_scene_number?: number | null;
  current_claim_id?: number | null;
  text_offset?: number;
  anchor_text?: string | null;
  anchor_length?: number;
  resolution_status?: ContinuityResolutionStatus;
  judge_source?: "rules" | "ai" | "fallback" | string;
  judge_classification?:
    | "hard_contradiction"
    | "soft_tension"
    | "compatible_progression"
    | "not_issue"
    | string;
  judge_confidence?: number;
  judge_reason?: string | null;
  conflict_kind?: string | null;
  conflicting_evidence_text?: string | null;
  current_evidence_text?: string | null;
  evidence_comparison?: string | null;
  explanation?: string | null;
  suggested_fix?: string | null;
  created_at: string;
};

export async function fetchStories(): Promise<StoryListOut[]> {
  const res = await fetch(`${apiBase()}/stories`, {
    headers: await authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<StoryListOut[]>;
}

export async function fetchStory(storyId: number): Promise<StoryOut> {
  const res = await fetch(`${apiBase()}/stories/${storyId}`, {
    headers: await authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<StoryOut>;
}

export async function updateStory(
  storyId: number,
  body: { title?: string; description?: string },
): Promise<StoryOut> {
  const res = await fetch(`${apiBase()}/stories/${storyId}`, {
    method: "PATCH",
    headers: await authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<StoryOut>;
}

export type StoryDescriptionOut = {
  description: string;
  source: "openai" | "heuristic" | string;
};

export async function generateStoryDescription(
  storyId: number,
): Promise<StoryDescriptionOut> {
  const res = await fetch(
    `${apiBase()}/stories/${storyId}/generate-description`,
    { method: "POST", headers: await authHeaders() },
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<StoryDescriptionOut>;
}

export async function createStory(body: {
  title: string;
  description?: string;
}): Promise<StoryOut> {
  const res = await fetch(`${apiBase()}/stories`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<StoryOut>;
}

export async function fetchScenes(storyId: number): Promise<SceneSummaryOut[]> {
  const res = await fetch(`${apiBase()}/stories/${storyId}/scenes`, {
    headers: await authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<SceneSummaryOut[]>;
}

export async function fetchScene(
  storyId: number,
  sceneId: number,
): Promise<SceneDetailOut> {
  const res = await fetch(`${apiBase()}/stories/${storyId}/scenes/${sceneId}`, {
    headers: await authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<SceneDetailOut>;
}

async function apiFetch(
  input: string,
  init?: RequestInit,
): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (err) {
    const msg =
      err instanceof Error ? err.message : String(err);
    if (
      msg.includes("fetch failed") ||
      msg.includes("ECONNRESET") ||
      msg.includes("socket hang up") ||
      err instanceof TypeError
    ) {
      throw new Error(
        "Cannot reach the FastAPI backend (connection dropped or timed out). " +
          "Chapter extraction with OpenAI can take 15–60s — wait and retry, or check the API terminal. " +
          "Run API without `--reload` if saves fail mid-request. " +
          "Ensure `apps/web/.env.local` has `API_PROXY_TARGET=http://127.0.0.1:8001` and restart `pnpm dev`.",
      );
    }
    throw err;
  }
}

export async function updateScene(
  storyId: number,
  sceneId: number,
  body: {
    scene_number: number;
    text: string;
    pov_character?: string | null;
    claims: ClaimIn[];
    run_extraction?: boolean;
  },
): Promise<SceneOut> {
  const res = await apiFetch(`${apiBase()}/stories/${storyId}/scenes/${sceneId}`, {
    method: "PATCH",
    headers: await authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<SceneOut>;
}

export async function addScene(
  storyId: number,
  body: {
    scene_number: number;
    text: string;
    pov_character?: string | null;
    claims: ClaimIn[];
  },
): Promise<SceneOut> {
  const res = await fetch(`${apiBase()}/stories/${storyId}/scenes`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<SceneOut>;
}

export async function fetchValidationIssues(
  storyId: number,
): Promise<ValidationIssueOut[]> {
  const res = await fetch(`${apiBase()}/stories/${storyId}/validate`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<ValidationIssueOut[]>;
}

export async function updateValidationIssueStatus(
  storyId: number,
  issueId: number,
  resolution_status: ContinuityResolutionStatus,
): Promise<ValidationIssueOut> {
  const res = await fetch(
    `${apiBase()}/stories/${storyId}/validation-issues/${issueId}`,
    {
      method: "PATCH",
      headers: await authHeaders(),
      body: JSON.stringify({ resolution_status }),
    },
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<ValidationIssueOut>;
}

export async function deleteScene(
  storyId: number,
  sceneId: number,
): Promise<void> {
  const res = await fetch(`${apiBase()}/stories/${storyId}/scenes/${sceneId}`, {
    method: "DELETE",
    headers: await authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function updateClaimStatus(
  storyId: number,
  sceneId: number,
  claimId: number,
  body: {
    status: "approved" | "rejected" | "needs_review" | "suggested" | "deprecated";
    claim_text?: string;
    subject?: string;
    target?: string;
  },
): Promise<ClaimOut> {
  const res = await fetch(
    `${apiBase()}/stories/${storyId}/scenes/${sceneId}/claims/${claimId}`,
    {
      method: "PATCH",
      headers: await authHeaders(),
      body: JSON.stringify(body),
    },
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<ClaimOut>;
}
