const PREFIX = "inferstories:scene-draft:";

export type SceneDraft = {
  sceneNumber: number;
  sceneText: string;
  updatedAt: string;
};

export function loadSceneDraft(storyId: number): SceneDraft | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(`${PREFIX}${storyId}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as SceneDraft;
    if (
      typeof parsed.sceneNumber !== "number" ||
      typeof parsed.sceneText !== "string"
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function saveSceneDraft(storyId: number, draft: SceneDraft): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(`${PREFIX}${storyId}`, JSON.stringify(draft));
}

export function clearSceneDraft(storyId: number): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(`${PREFIX}${storyId}`);
}
