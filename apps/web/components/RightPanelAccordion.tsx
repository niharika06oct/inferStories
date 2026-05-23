"use client";

import { cn } from "./ui";

export function RightPanelAccordionRow({
  id,
  title,
  description,
  count,
  expanded,
  onToggle,
  children,
}: {
  id: string;
  title: string;
  description?: string;
  count?: number;
  expanded: boolean;
  onToggle: () => void;
  children?: React.ReactNode;
}) {
  const panelId = `right-panel-${id}`;

  return (
    <section
      className={cn(
        "border-b border-border/80",
        expanded && "bg-background/20",
      )}
    >
      <button
        type="button"
        id={`${panelId}-trigger`}
        aria-expanded={expanded}
        aria-controls={panelId}
        onClick={onToggle}
        className={cn(
          "flex w-full items-start gap-3 px-3 py-3 text-left transition-colors",
          "hover:bg-muted/30",
          expanded && "bg-muted/25",
        )}
      >
        <span
          className={cn(
            "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border border-border/80 text-[10px] text-muted-foreground transition-transform",
            expanded && "rotate-90 border-primary/40 text-foreground",
          )}
          aria-hidden
        >
          ›
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-foreground">{title}</span>
            {count != null && count > 0 ? (
              <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-semibold tabular-nums text-primary">
                {count}
              </span>
            ) : null}
          </span>
          {description ? (
            <span className="mt-0.5 block text-[11px] leading-snug text-muted-foreground">
              {description}
            </span>
          ) : null}
        </span>
      </button>
      {expanded && children ? (
        <div
          id={panelId}
          role="region"
          aria-labelledby={`${panelId}-trigger`}
          className="flex min-h-0 flex-col border-t border-border/60"
        >
          {children}
        </div>
      ) : null}
    </section>
  );
}
