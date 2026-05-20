"use client";

import { cn } from "./ui";

type PanelEdgeCollapseProps = {
  /** Panel on the left side of the workspace — button sits on its right edge. */
  edge: "left" | "right";
  onCollapse: () => void;
  label: string;
};

export function PanelEdgeCollapse({
  edge,
  onCollapse,
  label,
}: PanelEdgeCollapseProps) {
  const glyph = edge === "left" ? "<" : ">";

  return (
    <button
      type="button"
      className={cn(
        "panel-edge-collapse",
        edge === "left" ? "panel-edge-collapse--left" : "panel-edge-collapse--right",
      )}
      onClick={onCollapse}
      title={`Hide ${label} panel`}
      aria-label={`Hide ${label} panel`}
    >
      <span aria-hidden>{glyph}</span>
    </button>
  );
}
