"use client";

import { Badge, Button, cn } from "./ui";
import type { ContinuityResolutionStatus, ValidationIssueOut } from "../lib/api";

type ContinuityIssuesListProps = {
  issues: ValidationIssueOut[];
  emptyMessage: string;
  focusedContinuityIssueId?: number | null;
  onContinuityIssueSelect?: (issue: ValidationIssueOut) => void;
  onResolve?: (
    issue: ValidationIssueOut,
    status: ContinuityResolutionStatus,
  ) => void;
  showResolveActions?: boolean;
  resolveBusyId?: number | null;
};

export function ContinuityIssuesList({
  issues,
  emptyMessage,
  focusedContinuityIssueId,
  onContinuityIssueSelect,
  onResolve,
  showResolveActions = false,
  resolveBusyId = null,
}: ContinuityIssuesListProps) {
  if (issues.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-border bg-muted/20 px-3 py-6 text-center text-sm text-muted-foreground">
        {emptyMessage}
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {issues.map((iss) => (
        <li
          key={iss.id}
          role={onContinuityIssueSelect ? "button" : undefined}
          tabIndex={onContinuityIssueSelect ? 0 : undefined}
          onClick={() => onContinuityIssueSelect?.(iss)}
          onKeyDown={(e) => {
            if (!onContinuityIssueSelect) return;
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onContinuityIssueSelect(iss);
            }
          }}
          className={cn(
            "rounded-lg border border-border bg-background/60 p-3 text-left transition-colors",
            onContinuityIssueSelect && "cursor-pointer hover:bg-muted/40",
            focusedContinuityIssueId === iss.id &&
              "border-amber-400/70 bg-amber-500/10 ring-2 ring-amber-400/35",
            iss.resolution_status === "fixed" &&
              "border-emerald-500/30 bg-emerald-500/5",
            iss.resolution_status === "rejected" &&
              "border-border/80 bg-muted/30 opacity-90",
          )}
        >
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              variant={iss.severity === "high" ? "destructive" : "warning"}
            >
              {iss.severity}
            </Badge>
            {iss.resolution_status === "fixed" ? (
              <Badge variant="success">Fixed</Badge>
            ) : null}
            {iss.resolution_status === "rejected" ? (
              <Badge variant="secondary">Rejected</Badge>
            ) : null}
            <span className="text-xs text-muted-foreground">
              Ch. {iss.scene_number}
              {iss.conflicting_scene_number != null
                ? ` vs Ch. ${iss.conflicting_scene_number}`
                : ""}
            </span>
          </div>
          <p className="mt-2 text-sm leading-6">{iss.message}</p>
          {iss.judge_reason ? (
            <p className="mt-2 rounded-md bg-muted/35 px-2 py-1.5 text-[11px] leading-5 text-muted-foreground">
              <span className="font-medium text-foreground">Reason:</span>{" "}
              {iss.judge_reason}
              {iss.judge_source ? (
                <span className="ml-1 opacity-75">({iss.judge_source})</span>
              ) : null}
            </p>
          ) : null}
          {showResolveActions && onResolve ? (
            <div
              className="mt-3 flex flex-wrap gap-2"
              onClick={(e) => e.stopPropagation()}
              onKeyDown={(e) => e.stopPropagation()}
            >
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={resolveBusyId === iss.id}
                onClick={() => onResolve(iss, "fixed")}
              >
                {resolveBusyId === iss.id ? "…" : "Fixed"}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={resolveBusyId === iss.id}
                onClick={() => onResolve(iss, "rejected")}
              >
                Reject
              </Button>
            </div>
          ) : onContinuityIssueSelect ? (
            <p className="mt-2 text-[10px] text-muted-foreground">
              Click to open chapter and jump to passage
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
