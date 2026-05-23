"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import { cn } from "./ui";
import type { TextSpan } from "../lib/claimEvidenceSpan";
import type { WritingIssue } from "../lib/grammarCheck";
import { findIssueAtOffset, issueKey } from "../lib/applyWritingSuggestion";
import {
  scrollElementIntoContainer,
  scrollTextareaToRange,
  syncContainerScrollFromTextarea,
  syncTextareaScrollFromContainer,
} from "../lib/scrollTextareaToRange";
import { buildEditorHighlightSegments } from "../lib/writingHighlight";
import { WritingIssueContextMenu } from "./WritingIssueContextMenu";

export type SceneTextEditorHandle = {
  scrollToIssue: (issue: WritingIssue) => void;
  scrollToRange: (start: number, end: number) => void;
};

type SceneTextEditorProps = {
  value: string;
  onChange: (value: string) => void;
  issues: WritingIssue[];
  claimFocusSpan?: TextSpan | null;
  onApplySuggestion?: (issue: WritingIssue, replacement: string) => void;
  onDismissIssue?: (issue: WritingIssue) => void;
  suggestionsDisabled?: boolean;
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
    claimFocusSpan,
    onApplySuggestion,
    onDismissIssue,
    suggestionsDisabled,
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
  const claimMarkRef = useRef<HTMLElement | null>(null);
  const [contextMenu, setContextMenu] = useState<{
    issue: WritingIssue;
    x: number;
    y: number;
  } | null>(null);

  const segments = useMemo(
    () => buildEditorHighlightSegments(value, issues, claimFocusSpan),
    [value, issues, claimFocusSpan],
  );

  const menuIssueKey = contextMenu ? issueKey(contextMenu.issue) : null;

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

  const scrollToRange = useCallback(
    (start: number, end: number, backdropAnchor?: HTMLElement | null) => {
      const ta = textareaRef.current;
      const backdrop = backdropRef.current;
      if (!ta) return;

      const apply = () => {
        ta.focus();
        ta.setSelectionRange(start, end);
        if (backdropAnchor && backdrop) {
          scrollElementIntoContainer(backdrop, backdropAnchor);
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

  const scrollToIssue = useCallback(
    (issue: WritingIssue) => {
      const key = issueKey(issue);
      scrollToRange(
        issue.offset,
        issue.offset + issue.length,
        issueMarkRefs.current.get(key),
      );
    },
    [scrollToRange],
  );

  useImperativeHandle(
    ref,
    () => ({ scrollToIssue, scrollToRange }),
    [scrollToIssue, scrollToRange],
  );

  useEffect(() => {
    if (!claimFocusSpan) {
      claimMarkRef.current = null;
      return;
    }
    requestAnimationFrame(() => {
      scrollToRange(
        claimFocusSpan.offset,
        claimFocusSpan.offset + claimFocusSpan.length,
        claimMarkRef.current,
      );
    });
  }, [claimFocusSpan, scrollToRange]);

  function openContextMenu(issue: WritingIssue, clientX: number, clientY: number) {
    setContextMenu({ issue, x: clientX, y: clientY });
    scrollToIssue(issue);
  }

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
                  !!menuIssueKey &&
                  seg.issue &&
                  issues.some(
                    (item) =>
                      issueKey(item) === menuIssueKey &&
                      segmentOverlapsIssue(segStart, segEnd, item),
                  );
                const overlappingIssues = seg.issue
                  ? issues.filter((item) =>
                      segmentOverlapsIssue(segStart, segEnd, item),
                    )
                  : [];

                if (seg.issue || seg.claimFocus) {
                  return (
                    <mark
                      key={i}
                      ref={(node) => {
                        if (seg.claimFocus) {
                          claimMarkRef.current = node;
                        }
                        for (const item of overlappingIssues) {
                          const k = issueKey(item);
                          if (node) issueMarkRefs.current.set(k, node);
                          else issueMarkRefs.current.delete(k);
                        }
                      }}
                      className={cn(
                        "text-inherit",
                        seg.issue && "scene-text-editor__issue",
                        isActive && "scene-text-editor__issue--active",
                        seg.claimFocus && "scene-text-editor__claim-focus",
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
        onContextMenu={(e) => {
          if (!onApplySuggestion && !onDismissIssue) return;
          const offset =
            e.currentTarget.selectionStart ?? e.currentTarget.selectionEnd;
          const issue = findIssueAtOffset(issues, offset);
          if (!issue) return;
          e.preventDefault();
          openContextMenu(issue, e.clientX, e.clientY);
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
      {contextMenu && onApplySuggestion && onDismissIssue ? (
        <WritingIssueContextMenu
          issue={contextMenu.issue}
          x={contextMenu.x}
          y={contextMenu.y}
          disabled={suggestionsDisabled}
          onApply={onApplySuggestion}
          onDismiss={onDismissIssue}
          onClose={() => setContextMenu(null)}
        />
      ) : null}
    </div>
  );
});
