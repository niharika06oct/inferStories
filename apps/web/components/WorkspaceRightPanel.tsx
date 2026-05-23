"use client";

import { useRef, useState } from "react";
import { Badge, Button, Spinner, cn } from "./ui";
import {
  WritingReviewPanel,
  type WritingReviewPanelHandle,
} from "./WritingReviewPanel";
import type { ValidationIssueOut } from "../lib/api";
import type { WritingIssue } from "../lib/grammarCheck";

export type RightPanelTab = "writing" | "continuity";

type WorkspaceRightPanelProps = {
  storyLoading: boolean;
  busy: boolean;
  chapterText: string;
  chapterDisabled: boolean;
  writingIssues: WritingIssue[];
  onWritingIssuesChange: (issues: WritingIssue[]) => void;
  onApplyWritingSuggestion?: (
    issue: WritingIssue,
    replacement: string,
  ) => void;
  focusedWritingIssueKey?: string | null;
  onWritingIssueSelect?: (issue: WritingIssue) => void;
  activeTab: RightPanelTab;
  onTabChange: (tab: RightPanelTab) => void;
  continuityIssues: ValidationIssueOut[];
  continuityLoading: boolean;
  continuityLoadedAt: string | null;
  onRefreshContinuity: () => void;
};

function PanelTab({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "flex-1 rounded-md px-2 py-2 text-xs font-medium leading-snug transition-colors",
        active
          ? "bg-card text-foreground shadow-sm"
          : "text-muted-foreground hover:bg-card/50 hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

export function WorkspaceRightPanel({
  storyLoading,
  busy,
  chapterText,
  chapterDisabled,
  writingIssues,
  onWritingIssuesChange,
  onApplyWritingSuggestion,
  focusedWritingIssueKey,
  onWritingIssueSelect,
  activeTab,
  onTabChange,
  continuityIssues,
  continuityLoading,
  continuityLoadedAt,
  onRefreshContinuity,
}: WorkspaceRightPanelProps) {
  const writingRef = useRef<WritingReviewPanelHandle>(null);
  const [writingReviewing, setWritingReviewing] = useState(false);
  const [grammarLoadedAt, setGrammarLoadedAt] = useState<string | null>(null);

  const refreshDisabled = storyLoading || busy || chapterDisabled;

  async function onRefreshClick() {
    if (activeTab === "writing") {
      setWritingReviewing(true);
      try {
        await writingRef.current?.runReview();
      } finally {
        setWritingReviewing(false);
      }
    } else {
      onRefreshContinuity();
    }
  }

  const loadedAt =
    activeTab === "writing" ? grammarLoadedAt : continuityLoadedAt;

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="shrink-0 border-b border-border bg-secondary/30 px-3 py-2">
        <div
          role="tablist"
          aria-label="Right panel"
          className="flex gap-1 rounded-lg bg-muted/50 p-1"
        >
          <PanelTab
            active={activeTab === "writing"}
            onClick={() => onTabChange("writing")}
          >
            Review grammar & spelling
          </PanelTab>
          <PanelTab
            active={activeTab === "continuity"}
            onClick={() => onTabChange("continuity")}
          >
            Continuity
          </PanelTab>
        </div>
      </div>

      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border bg-secondary/40 px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-secondary-foreground">
            {activeTab === "writing" ? "Grammar & spelling" : "Continuity"}
          </h2>
          <p className="text-xs text-muted-foreground">
            {activeTab === "writing"
              ? "Refresh to check this chapter"
              : "Refresh to load the latest checks"}
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={refreshDisabled || writingReviewing}
          onClick={() => void onRefreshClick()}
        >
          {writingReviewing ? (
            <>
              <Spinner /> Reviewing…
            </>
          ) : (
            "Refresh"
          )}
        </Button>
      </div>

      <div className="flex h-0 min-h-0 flex-1 flex-col overflow-hidden">
        {activeTab === "writing" ? (
          <WritingReviewPanel
            ref={writingRef}
            text={chapterText}
            disabled={refreshDisabled}
            issues={writingIssues}
            focusedIssueKey={focusedWritingIssueKey}
            onIssuesChange={onWritingIssuesChange}
            onReviewedAt={setGrammarLoadedAt}
            onApplySuggestion={onApplyWritingSuggestion}
            onIssueSelect={onWritingIssueSelect}
          />
        ) : (
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4">
            {storyLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : continuityLoading && continuityIssues.length === 0 ? (
              <div className="space-y-3">
                {[1, 2, 3].map((n) => (
                  <div
                    key={n}
                    className="h-16 animate-pulse rounded-lg bg-muted"
                  />
                ))}
              </div>
            ) : continuityIssues.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border bg-muted/30 px-4 py-8 text-center">
                <p className="text-sm font-medium text-foreground">
                  No issues yet
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Contradictions show up when a new chapter conflicts with
                  earlier claims.
                </p>
              </div>
            ) : (
              <ul className="space-y-3">
                {continuityIssues.map((iss) => (
                  <li
                    key={iss.id}
                    className="rounded-lg border border-border bg-background p-3 shadow-sm"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge
                        variant={
                          iss.severity === "high" ? "destructive" : "warning"
                        }
                      >
                        {iss.severity}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        Chapter {iss.scene_number}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-foreground">
                      {iss.message}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {loadedAt ? (
          <p className="shrink-0 border-t border-border py-2 text-center text-xs text-muted-foreground">
            Updated {new Date(loadedAt).toLocaleTimeString()}
          </p>
        ) : null}
      </div>
    </div>
  );
}
