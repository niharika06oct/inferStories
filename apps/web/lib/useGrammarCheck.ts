"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { checkWriting, type WritingIssue } from "./grammarCheck";
import {
  filterDismissedWritingIssues,
  loadDismissedWritingFingerprints,
} from "./writingDismissedStorage";

export function useGrammarCheck({
  storyId,
  sceneId,
  text,
  enabled,
  debounceMs = 3500,
}: {
  storyId: number;
  sceneId: number | null;
  text: string;
  enabled: boolean;
  debounceMs?: number;
}): {
  issues: WritingIssue[];
  setIssues: React.Dispatch<React.SetStateAction<WritingIssue[]>>;
  checking: boolean;
  checkError: string | null;
  runCheck: () => Promise<void>;
  dismissedRef: React.MutableRefObject<Set<string>>;
} {
  const [issues, setIssues] = useState<WritingIssue[]>([]);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const dismissedRef = useRef<Set<string>>(new Set());
  const lastCheckedText = useRef("");

  useEffect(() => {
    dismissedRef.current = loadDismissedWritingFingerprints(storyId, sceneId);
    setIssues([]);
    lastCheckedText.current = "";
  }, [storyId, sceneId]);

  const runCheck = useCallback(async () => {
    const trimmed = text.trim();
    if (trimmed.length < 2) {
      setIssues([]);
      setCheckError(null);
      lastCheckedText.current = trimmed;
      return;
    }
    if (trimmed === lastCheckedText.current) {
      return;
    }

    setChecking(true);
    setCheckError(null);
    try {
      const found = await checkWriting(text);
      const filtered = filterDismissedWritingIssues(
        found,
        dismissedRef.current,
      );
      setIssues(filtered);
      lastCheckedText.current = trimmed;
    } catch (e) {
      setCheckError(e instanceof Error ? e.message : "Grammar check failed");
    } finally {
      setChecking(false);
    }
  }, [text]);

  useEffect(() => {
    if (!enabled) return;
    const trimmed = text.trim();
    if (trimmed.length < 2) {
      setIssues([]);
      return;
    }
    const timer = window.setTimeout(() => {
      void runCheck();
    }, debounceMs);
    return () => window.clearTimeout(timer);
  }, [text, enabled, debounceMs, runCheck]);

  return {
    issues,
    setIssues,
    checking,
    checkError,
    runCheck,
    dismissedRef,
  };
}
