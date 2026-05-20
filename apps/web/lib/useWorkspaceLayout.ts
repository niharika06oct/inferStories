"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "inferStories.workspaceLayout";

const LEFT_MIN = 200;
const LEFT_MAX = 520;
const RIGHT_MIN = 200;
const RIGHT_MAX = 520;
const DEFAULT_LEFT = 300;
const DEFAULT_RIGHT = 300;

export type SceneEditorHeight = "default" | "large" | "focus";

type LayoutState = {
  leftOpen: boolean;
  rightOpen: boolean;
  leftWidth: number;
  rightWidth: number;
  sceneEditorHeight: SceneEditorHeight;
};

const DEFAULTS: LayoutState = {
  leftOpen: true,
  rightOpen: true,
  leftWidth: DEFAULT_LEFT,
  rightWidth: DEFAULT_RIGHT,
  sceneEditorHeight: "default",
};

function clamp(n: number, min: number, max: number) {
  return Math.min(max, Math.max(min, n));
}

function readStored(): LayoutState {
  if (typeof window === "undefined") return DEFAULTS;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<LayoutState>;
    return {
      leftOpen: parsed.leftOpen ?? DEFAULTS.leftOpen,
      rightOpen: parsed.rightOpen ?? DEFAULTS.rightOpen,
      leftWidth: clamp(parsed.leftWidth ?? DEFAULT_LEFT, LEFT_MIN, LEFT_MAX),
      rightWidth: clamp(parsed.rightWidth ?? DEFAULT_RIGHT, RIGHT_MIN, RIGHT_MAX),
      sceneEditorHeight:
        parsed.sceneEditorHeight === "large" ||
        parsed.sceneEditorHeight === "focus" ||
        parsed.sceneEditorHeight === "default"
          ? parsed.sceneEditorHeight
          : DEFAULTS.sceneEditorHeight,
    };
  } catch {
    return DEFAULTS;
  }
}

export function useWorkspaceLayout() {
  const [layout, setLayout] = useState<LayoutState>(DEFAULTS);
  const [hydrated, setHydrated] = useState(false);
  const beforeFocusRef = useRef<Pick<LayoutState, "leftOpen" | "rightOpen"> | null>(
    null,
  );

  useEffect(() => {
    setLayout(readStored());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
  }, [layout, hydrated]);

  const setLeftOpen = useCallback((open: boolean) => {
    setLayout((prev) => ({
      ...prev,
      leftOpen: open,
      sceneEditorHeight:
        prev.sceneEditorHeight === "focus" && open ? "large" : prev.sceneEditorHeight,
    }));
  }, []);

  const setRightOpen = useCallback((open: boolean) => {
    setLayout((prev) => ({
      ...prev,
      rightOpen: open,
      sceneEditorHeight:
        prev.sceneEditorHeight === "focus" && open ? "large" : prev.sceneEditorHeight,
    }));
  }, []);

  const resizeLeft = useCallback((delta: number) => {
    setLayout((prev) => ({
      ...prev,
      leftWidth: clamp(prev.leftWidth + delta, LEFT_MIN, LEFT_MAX),
    }));
  }, []);

  const resizeRight = useCallback((delta: number) => {
    setLayout((prev) => ({
      ...prev,
      // Handle sits on the left edge of the right panel: drag left = wider, drag right = narrower.
      rightWidth: clamp(prev.rightWidth - delta, RIGHT_MIN, RIGHT_MAX),
    }));
  }, []);

  const cycleSceneHeight = useCallback(() => {
    setLayout((prev) => {
      const next: SceneEditorHeight =
        prev.sceneEditorHeight === "default"
          ? "large"
          : prev.sceneEditorHeight === "large"
            ? "focus"
            : "default";
      if (next === "focus") {
        beforeFocusRef.current = {
          leftOpen: prev.leftOpen,
          rightOpen: prev.rightOpen,
        };
        return {
          ...prev,
          sceneEditorHeight: "focus",
          leftOpen: false,
          rightOpen: false,
        };
      }
      return { ...prev, sceneEditorHeight: next };
    });
  }, []);

  const enterWritingFocus = useCallback(() => {
    setLayout((prev) => {
      beforeFocusRef.current = {
        leftOpen: prev.leftOpen,
        rightOpen: prev.rightOpen,
      };
      return {
        ...prev,
        sceneEditorHeight: "focus",
        leftOpen: false,
        rightOpen: false,
      };
    });
  }, []);

  const exitWritingFocus = useCallback(() => {
    const restore = beforeFocusRef.current ?? {
      leftOpen: true,
      rightOpen: true,
    };
    beforeFocusRef.current = null;
    setLayout((prev) => ({
      ...prev,
      sceneEditorHeight: prev.sceneEditorHeight === "focus" ? "large" : prev.sceneEditorHeight,
      leftOpen: restore.leftOpen,
      rightOpen: restore.rightOpen,
    }));
  }, []);

  const isWritingFocus =
    layout.sceneEditorHeight === "focus" && !layout.leftOpen && !layout.rightOpen;

  return {
    ...layout,
    hydrated,
    isWritingFocus,
    setLeftOpen,
    setRightOpen,
    resizeLeft,
    resizeRight,
    cycleSceneHeight,
    enterWritingFocus,
    exitWritingFocus,
    setSceneEditorHeight: (sceneEditorHeight: SceneEditorHeight) =>
      setLayout((prev) => ({ ...prev, sceneEditorHeight })),
  };
}

export { LEFT_MIN, LEFT_MAX, RIGHT_MIN, RIGHT_MAX };
