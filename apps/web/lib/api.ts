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
  return "http://127.0.0.1:8000";
}

async function parseError(res: Response): Promise<string> {
  const t = await res.text();
  try {
    const j = JSON.parse(t) as { detail?: unknown };
    const d = j.detail;
    if (typeof d === "string") return d;
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
};

export type ValidationIssueOut = {
  id: number;
  story_id: number;
  scene_id: number;
  scene_number: number;
  severity: string;
  message: string;
  conflicting_claim_id: number | null;
  created_at: string;
};

export async function createStory(body: {
  title: string;
  description?: string;
}): Promise<StoryOut> {
  const res = await fetch(`${apiBase()}/stories`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<StoryOut>;
}

export async function addScene(
  storyId: number,
  body: {
    scene_number: number;
    text: string;
    claims: ClaimIn[];
  },
): Promise<SceneOut> {
  const res = await fetch(`${apiBase()}/stories/${storyId}/scenes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<ValidationIssueOut[]>;
}
