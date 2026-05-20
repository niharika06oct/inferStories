"use client";

import { useCallback, useRef } from "react";
import { cn } from "./ui";

type PanelResizeHandleProps = {
  side: "left" | "right";
  onResize: (deltaX: number) => void;
  className?: string;
};

export function PanelResizeHandle({
  side,
  onResize,
  className,
}: PanelResizeHandleProps) {
  const dragging = useRef(false);
  const lastX = useRef(0);

  const onPointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      e.preventDefault();
      dragging.current = true;
      lastX.current = e.clientX;
      e.currentTarget.setPointerCapture(e.pointerId);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    },
    [],
  );

  const onPointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!dragging.current) return;
      const dx = e.clientX - lastX.current;
      lastX.current = e.clientX;
      onResize(dx);
    },
    [onResize, side],
  );

  const endDrag = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging.current) return;
    dragging.current = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      /* already released */
    }
  }, []);

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={
        side === "left" ? "Resize chapters panel" : "Resize continuity panel"
      }
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      className={cn(
        "panel-resize-handle hidden w-1.5 shrink-0 cursor-col-resize touch-none lg:block",
        className,
      )}
    />
  );
}
