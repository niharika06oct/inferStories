"use client";

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { Button, cn } from "./ui";
import type { WritingIssue } from "../lib/grammarCheck";

type WritingIssueContextMenuProps = {
  issue: WritingIssue;
  x: number;
  y: number;
  disabled?: boolean;
  onApply: (issue: WritingIssue, replacement: string) => void;
  onDismiss: (issue: WritingIssue) => void;
  onClose: () => void;
};

export function WritingIssueContextMenu({
  issue,
  x,
  y,
  disabled,
  onApply,
  onDismiss,
  onClose,
}: WritingIssueContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onPointerDown(e: MouseEvent) {
      if (menuRef.current?.contains(e.target as Node)) return;
      onClose();
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose]);

  useEffect(() => {
    const el = menuRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const pad = 8;
    let left = x;
    let top = y;
    if (left + rect.width > window.innerWidth - pad) {
      left = Math.max(pad, window.innerWidth - rect.width - pad);
    }
    if (top + rect.height > window.innerHeight - pad) {
      top = Math.max(pad, window.innerHeight - rect.height - pad);
    }
    el.style.left = `${left}px`;
    el.style.top = `${top}px`;
  }, [x, y, issue]);

  return createPortal(
    <div
      ref={menuRef}
      role="menu"
      className={cn(
        "writing-issue-menu fixed z-[100] w-[min(18rem,calc(100vw-1rem))]",
        "rounded-lg border border-border bg-popover p-2 shadow-lg",
      )}
      style={{ left: x, top: y }}
      onContextMenu={(e) => e.preventDefault()}
    >
      <p className="px-2 py-1 text-xs font-medium text-foreground">
        {issue.shortMessage}
      </p>
      <p className="px-2 pb-2 text-[11px] leading-snug text-muted-foreground">
        {issue.message}
      </p>
      {issue.replacements.length > 0 ? (
        <div className="flex flex-col gap-1 border-t border-border/60 pt-2">
          {issue.replacements.slice(0, 4).map((replacement) => (
            <button
              key={replacement}
              type="button"
              role="menuitem"
              disabled={disabled}
              className={cn(
                "rounded-md px-2 py-1.5 text-left text-sm text-foreground",
                "hover:bg-accent disabled:opacity-50",
              )}
              onClick={() => {
                onApply(issue, replacement);
                onClose();
              }}
            >
              Apply &ldquo;{replacement}&rdquo;
            </button>
          ))}
        </div>
      ) : null}
      <div className="mt-2 flex gap-2 border-t border-border/60 pt-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="flex-1"
          disabled={disabled}
          onClick={() => {
            onDismiss(issue);
            onClose();
          }}
        >
          Dismiss
        </Button>
      </div>
    </div>,
    document.body,
  );
}
