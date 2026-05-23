"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { Button, cn } from "./ui";
import { issueKey } from "../lib/applyWritingSuggestion";
import { excerptAround, checkWriting, type WritingIssue } from "../lib/grammarCheck";

export type WritingReviewPanelHandle = {
  runReview: () => Promise<void>;
};

type WritingReviewPanelProps = {
  text: string;
  disabled?: boolean;
  issues: WritingIssue[];
  focusedIssueKey?: string | null;
  onIssuesChange: (issues: WritingIssue[]) => void;
  onReviewedAt?: (iso: string) => void;
  onApplySuggestion?: (issue: WritingIssue, replacement: string) => void;
  onIssueSelect?: (issue: WritingIssue) => void;
};

export const WritingReviewPanel = forwardRef<
  WritingReviewPanelHandle,
  WritingReviewPanelProps
>(function WritingReviewPanel(
  {
    text,
    disabled,
    issues,
    focusedIssueKey,
    onIssuesChange,
    onReviewedAt,
    onApplySuggestion,
    onIssueSelect,
  },
  ref,
) {
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const issueRefs = useRef<Map<string, HTMLLIElement>>(new Map());

  const runReview = useCallback(async () => {
    if (text.trim().length < 2) {
      onIssuesChange([]);
      setReviewed(true);
      setCheckError("Add a little more text before reviewing.");
      return;
    }
    setChecking(true);
    setCheckError(null);
    try {
      const found = await checkWriting(text);
      onIssuesChange(found);
      setReviewed(true);
      onReviewedAt?.(new Date().toISOString());
    } catch (e) {
      onIssuesChange([]);
      setCheckError(e instanceof Error ? e.message : "Review failed");
    } finally {
      setChecking(false);
    }
  }, [text, onIssuesChange, onReviewedAt]);

  useImperativeHandle(ref, () => ({ runReview }), [runReview]);

  useEffect(() => {
    if (!focusedIssueKey) return;
    const el = issueRefs.current.get(focusedIssueKey);
    if (!el) return;
    el.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [focusedIssueKey, issues]);

  return (
    <div className="flex h-0 min-h-0 flex-1 flex-col overflow-hidden">
      <div className="shrink-0 space-y-2 border-b border-border/50 px-4 py-3">
        <p className="text-xs text-muted-foreground">
          Browser spellcheck runs while you type. Click Refresh above to check
          grammar; issues appear as blue underlines in the chapter. Click an
          underline or a card below to jump between the text and its suggestion.
        </p>
        {checkError ? (
          <p className="text-xs text-destructive">{checkError}</p>
        ) : null}
        {reviewed && issues.length === 0 && !checkError ? (
          <p className="text-xs text-muted-foreground">
            No issues found for this chapter.
          </p>
        ) : null}
      </div>

      <div className="writing-review-panel__scroll h-0 min-h-0 flex-1 overflow-y-auto px-4 py-3">
        {issues.length > 0 ? (
          <ul className="space-y-2">
            {issues.map((issue) => {
              const key = issueKey(issue);
              const primary = issue.replacements[0];
              const isFocused = focusedIssueKey === key;
              return (
                <li
                  key={key}
                  ref={(node) => {
                    if (node) issueRefs.current.set(key, node);
                    else issueRefs.current.delete(key);
                  }}
                  role={onIssueSelect ? "button" : undefined}
                  tabIndex={onIssueSelect ? 0 : undefined}
                  onClick={() => onIssueSelect?.(issue)}
                  onKeyDown={(e) => {
                    if (!onIssueSelect) return;
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onIssueSelect(issue);
                    }
                  }}
                  className={cn(
                    "rounded-lg border border-border/60 bg-card/50 px-3 py-2 text-xs transition-colors",
                    onIssueSelect && "cursor-pointer hover:bg-card/80",
                    isFocused && "writing-review-panel__issue--focused",
                  )}
                >
                  <p className="font-medium text-foreground">
                    {issue.shortMessage}
                  </p>
                  <p className="mt-0.5 text-muted-foreground">{issue.message}</p>
                  <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                    {excerptAround(text, issue.offset, issue.length)}
                  </p>
                  {issue.replacements.length > 0 ? (
                    <p className="mt-1 text-muted-foreground">
                      Suggestions: {issue.replacements.join(", ")}
                    </p>
                  ) : null}
                  <div className="mt-2 flex flex-wrap gap-2">
                    {primary && onApplySuggestion ? (
                      <Button
                        type="button"
                        variant="cta"
                        size="sm"
                        disabled={disabled}
                        onClick={(e) => {
                          e.stopPropagation();
                          onApplySuggestion(issue, primary);
                        }}
                      >
                        Apply “{primary}”
                      </Button>
                    ) : null}
                    {issue.replacements.slice(1, 3).map((alt) =>
                      onApplySuggestion ? (
                        <Button
                          key={alt}
                          type="button"
                          variant="outline"
                          size="sm"
                          disabled={disabled}
                          onClick={(e) => {
                            e.stopPropagation();
                            onApplySuggestion(issue, alt);
                          }}
                        >
                          {alt}
                        </Button>
                      ) : null,
                    )}
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={disabled}
                      onClick={(e) => {
                        e.stopPropagation();
                        onIssuesChange(
                          issues.filter((item) => issueKey(item) !== key),
                        );
                      }}
                    >
                      Dismiss
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : checking ? (
          <p className="text-xs text-muted-foreground">Checking…</p>
        ) : null}
      </div>
    </div>
  );
});
