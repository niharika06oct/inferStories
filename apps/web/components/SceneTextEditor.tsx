"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
} from "react";
import { cn } from "./ui";
import type { WritingIssue } from "../lib/grammarCheck";
import { findIssueAtOffset, issueKey } from "../lib/applyWritingSuggestion";
import {
  scrollElementIntoContainer,
  scrollTextareaToRange,
  syncContainerScrollFromTextarea,
  syncTextareaScrollFromContainer,
} from "../lib/scrollTextareaToRange";
import { buildHighlightSegments } from "../lib/writingHighlight";

export type SceneTextEditorHandle = {
  scrollToIssue: (issue: WritingIssue) => void;
};

type SceneTextEditorProps = {
  value: string;
  onChange: (value: string) => void;
  issues: WritingIssue[];
  focusedIssueKey?: string | null;
  onIssueClick?: (issue: WritingIssue) => void;
  disabled?: boolean;
  required?: boolean;
  placeholder?: string;
  className?: string;
};

const innerClass =
  "px-3 py-2 text-[15px] leading-7 [font-family:inherit]";

function segmentOverlapsIssue(
  segStart: number,
  segEnd: number,
  issue: WritingIssue,
): boolean {
  return issue.offset < segEnd && issue.offset + issue.length > segStart;
}

export const SceneTextEditor = forwardRef<
  SceneTextEditorHandle,
  SceneTextEditorProps
>(function SceneTextEditor(
  {
    value,
    onChange,
    issues,
    focusedIssueKey,
    onIssueClick,
    disabled,
    required,
    placeholder,
    className,
  },
  ref,
) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const backdropRef = useRef<HTMLDivElement>(null);
  const issueMarkRefs = useRef<Map<string, HTMLElement>>(new Map());

  const segments = useMemo(
    () => buildHighlightSegments(value, issues),
    [value, issues],
  );

  const activeIssue = useMemo(
    () =>
      focusedIssueKey
        ? issues.find((item) => issueKey(item) === focusedIssueKey)
        : null,
    [focusedIssueKey, issues],
  );

  useEffect(() => {
    const valid = new Set(issues.map((item) => issueKey(item)));
    for (const key of issueMarkRefs.current.keys()) {
      if (!valid.has(key)) issueMarkRefs.current.delete(key);
    }
  }, [issues]);

  const syncScroll = useCallback(() => {
    const ta = textareaRef.current;
    const backdrop = backdropRef.current;
    if (!ta || !backdrop) return;
    backdrop.scrollTop = ta.scrollTop;
    backdrop.scrollLeft = ta.scrollLeft;
  }, []);

  const scrollToIssue = useCallback(
    (issue: WritingIssue) => {
      const ta = textareaRef.current;
      const backdrop = backdropRef.current;
      if (!ta) return;

      const start = issue.offset;
      const end = issue.offset + issue.length;
      const key = issueKey(issue);

      const apply = () => {
        const anchor = issueMarkRefs.current.get(key);
        ta.focus();
        ta.setSelectionRange(start, end);

        if (anchor && backdrop) {
          scrollElementIntoContainer(backdrop, anchor);
          syncTextareaScrollFromContainer(ta, backdrop);
        } else {
          scrollTextareaToRange(ta, start, end);
          if (backdrop) syncContainerScrollFromTextarea(backdrop, ta);
        }

        ta.scrollIntoView({ block: "center", behavior: "auto" });
      };

      apply();
      requestAnimationFrame(apply);
    },
    [],
  );

  useImperativeHandle(ref, () => ({ scrollToIssue }), [scrollToIssue]);

  return (
    <div
      className={cn(
        "scene-text-editor grid w-full [&>*]:col-start-1 [&>*]:row-start-1",
        className,
      )}
    >
      <div
        ref={backdropRef}
        aria-hidden
        className={cn(
          "scene-text-editor__backdrop min-h-0 overflow-auto",
          "pointer-events-none [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
        )}
      >
        <div
          className={cn(
            innerClass,
            "whitespace-pre-wrap break-words text-slate-50",
          )}
        >
          {value ? (
            (() => {
              let cursor = 0;
              return segments.map((seg, i) => {
                const segStart = cursor;
                cursor += seg.text.length;
                const segEnd = cursor;
                const isActive =
                  !!activeIssue &&
                  seg.issue &&
                  segmentOverlapsIssue(segStart, segEnd, activeIssue);
                const overlappingIssues = seg.issue
                  ? issues.filter((item) =>
                      segmentOverlapsIssue(segStart, segEnd, item),
                    )
                  : [];

                if (seg.issue) {
                  return (
                    <mark
                      key={i}
                      ref={(node) => {
                        for (const item of overlappingIssues) {
                          const k = issueKey(item);
                          if (node) issueMarkRefs.current.set(k, node);
                          else issueMarkRefs.current.delete(k);
                        }
                      }}
                      className={cn(
                        "scene-text-editor__issue text-inherit",
                        isActive && "scene-text-editor__issue--active",
                      )}
                    >
                      {seg.text}
                    </mark>
                  );
                }

                return <span key={i}>{seg.text}</span>;
              });
            })()
          ) : (
            <span className="text-slate-400">{placeholder}</span>
          )}
        </div>
      </div>
      <textarea
        ref={textareaRef}
        required={required}
        value={value}
        disabled={disabled}
        placeholder={placeholder}
        spellCheck
        lang="en"
        onChange={(e) => onChange(e.target.value)}
        onClick={(e) => {
          if (!onIssueClick || issues.length === 0) return;
          const issue = findIssueAtOffset(
            issues,
            e.currentTarget.selectionStart,
          );
          if (issue) onIssueClick(issue);
        }}
        onScroll={syncScroll}
        className={cn(
          "scene-text-editor__input min-h-0 w-full resize-y overflow-auto",
          "border-0 bg-transparent text-transparent shadow-none",
          "caret-slate-50 selection:bg-sky-500/40",
          "placeholder:text-slate-300/90",
          "focus-visible:outline-none focus-visible:ring-0",
          "disabled:cursor-not-allowed disabled:opacity-50",
          innerClass,
        )}
      />
    </div>
  );
});
