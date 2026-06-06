import type { ValidationIssueOut } from "./api";

export type ContinuitySortOrder = "text" | "detection";

const STORAGE_KEY = "inferstories.continuitySortOrder";

export const CONTINUITY_SORT_OPTIONS: {
  value: ContinuitySortOrder;
  label: string;
}[] = [
  { value: "text", label: "Increasing order of text" },
  { value: "detection", label: "Detection time" },
];

export function loadContinuitySortOrder(): ContinuitySortOrder {
  if (typeof window === "undefined") return "text";
  const raw = window.localStorage.getItem(STORAGE_KEY);
  return raw === "detection" ? "detection" : "text";
}

export function saveContinuitySortOrder(order: ContinuitySortOrder): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, order);
}

export function sortContinuityIssues(
  issues: ValidationIssueOut[],
  order: ContinuitySortOrder,
): ValidationIssueOut[] {
  const copy = [...issues];
  if (order === "detection") {
    copy.sort(
      (a, b) =>
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    );
    return copy;
  }
  copy.sort((a, b) => {
    if (a.scene_number !== b.scene_number) {
      return a.scene_number - b.scene_number;
    }
    const ao = a.text_offset ?? 0;
    const bo = b.text_offset ?? 0;
    if (ao !== bo) return ao - bo;
    return a.id - b.id;
  });
  return copy;
}
