"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { updateScene } from "./api";

export type SceneSaveState = "idle" | "dirty" | "saving" | "saved" | "error";

type Snapshot = {
  sceneNumber: number;
  sceneText: string;
};

export function useSceneAutosave({
  storyId,
  sceneId,
  sceneNumber,
  sceneText,
  enabled,
  debounceMs = 2000,
}: {
  storyId: number;
  sceneId: number | null;
  sceneNumber: number;
  sceneText: string;
  enabled: boolean;
  debounceMs?: number;
}): {
  saveState: SceneSaveState;
  lastSavedAt: Date | null;
  markPersisted: (snapshot: Snapshot) => void;
} {
  const [saveState, setSaveState] = useState<SceneSaveState>("idle");
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
  const lastPersisted = useRef<Snapshot | null>(null);

  useEffect(() => {
    lastPersisted.current = null;
    setSaveState("idle");
    setLastSavedAt(null);
  }, [sceneId]);

  useEffect(() => {
    if (!enabled || sceneId == null) return;
    const trimmed = sceneText.trim();
    if (!trimmed) return;

    const snapshot: Snapshot = { sceneNumber, sceneText: trimmed };
    const prev = lastPersisted.current;
    if (
      prev &&
      prev.sceneNumber === snapshot.sceneNumber &&
      prev.sceneText === snapshot.sceneText
    ) {
      return;
    }

    setSaveState("dirty");
    const timer = window.setTimeout(() => {
      void (async () => {
        setSaveState("saving");
        try {
          await updateScene(storyId, sceneId, {
            scene_number: snapshot.sceneNumber,
            text: snapshot.sceneText,
            claims: [],
            run_extraction: false,
          });
          lastPersisted.current = snapshot;
          setLastSavedAt(new Date());
          setSaveState("saved");
        } catch {
          setSaveState("error");
        }
      })();
    }, debounceMs);

    return () => window.clearTimeout(timer);
  }, [
    storyId,
    sceneId,
    sceneNumber,
    sceneText,
    enabled,
    debounceMs,
  ]);

  const markPersisted = useCallback((snapshot: Snapshot) => {
    lastPersisted.current = snapshot;
    setLastSavedAt(new Date());
    setSaveState("saved");
  }, []);

  return { saveState, lastSavedAt, markPersisted };
}
