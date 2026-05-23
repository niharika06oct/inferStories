"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  FieldLabel,
  Input,
  Panel,
  Spinner,
  Textarea,
  cn,
} from "../components/ui";
import {
  addScene,
  fetchScene,
  fetchScenes,
  fetchStory,
  fetchValidationIssues,
  generateStoryDescription,
  updateClaimStatus,
  updateScene,
  updateStory,
  type ClaimOut,
  type SceneExtractionOut,
  type SceneSummaryOut,
  type ValidationIssueOut,
} from "../lib/api";
import {
  formatSceneText,
  parseManuscriptText,
  type ImportedManuscript,
} from "../lib/importManuscript";
import {
  isSupportedManuscriptFile,
  readManuscriptFile,
} from "../lib/readManuscriptFile";
import { useWorkspaceLayout } from "../lib/useWorkspaceLayout";
import { ExtractionDebugPanel } from "../components/ExtractionDebugPanel";
import { PanelEdgeCollapse } from "../components/PanelEdgeCollapse";
import { PanelResizeHandle } from "../components/PanelResizeHandle";
import { UserAccountMenuGate } from "../components/UserAccountMenu";
import {
  SceneTextEditor,
  type SceneTextEditorHandle,
} from "../components/SceneTextEditor";
import {
  WorkspaceRightPanel,
  type WorkspaceRightPanelHandle,
} from "../components/WorkspaceRightPanel";
import { claimBucketCounts } from "../lib/claimBuckets";
import type { WritingIssue } from "../lib/grammarCheck";
import {
  applyTextReplacement,
  issuesAfterApply,
} from "../lib/applyWritingSuggestion";
import { findClaimEvidenceSpan } from "../lib/claimEvidenceSpan";
import { useGrammarCheck } from "../lib/useGrammarCheck";
import { rememberDismissedWritingIssue } from "../lib/writingDismissedStorage";
import { writingIssueFingerprint } from "../lib/writingIssueFingerprint";
import { reconcileWritingIssuesAfterEdit } from "../lib/writingIssueSync";
import {
  clearSceneDraft,
  loadSceneDraft,
  saveSceneDraft,
} from "../lib/sceneDraftStorage";
import { useSceneAutosave } from "../lib/useSceneAutosave";

function formatErr(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "Something went wrong";
}

function excerpt(text: string, max = 72): string {
  const t = text.trim().replace(/\s+/g, " ");
  if (t.length <= max) return t;
  return `${t.slice(0, max)}…`;
}

function nextSceneNumber(scenes: SceneSummaryOut[]): number {
  if (scenes.length === 0) return 1;
  return Math.max(...scenes.map((s) => s.scene_number)) + 1;
}

type StoryEditorProps = {
  storyId: number;
};

export default function StoryEditor({ storyId }: StoryEditorProps) {
  const [scenes, setScenes] = useState<SceneSummaryOut[]>([]);
  const [scenesLoading, setScenesLoading] = useState(false);
  type CenterView = "story-form" | "scenes";
  const [centerView, setCenterView] = useState<CenterView>("scenes");
  const [storyLoading, setStoryLoading] = useState(true);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const [editingSceneId, setEditingSceneId] = useState<number | null>(null);
  const [sceneNumber, setSceneNumber] = useState(1);
  const [povCharacter, setPovCharacter] = useState("");
  const [sceneText, setSceneText] = useState("");
  const [claims, setClaims] = useState<ClaimOut[]>([]);
  const [lastExtraction, setLastExtraction] = useState<SceneExtractionOut | null>(
    null,
  );

  const [issues, setIssues] = useState<ValidationIssueOut[]>([]);
  const [issuesLoadedAt, setIssuesLoadedAt] = useState<string | null>(null);
  const [issuesLoading, setIssuesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [analyzeStatus, setAnalyzeStatus] = useState<string | null>(null);
  const [importStatus, setImportStatus] = useState<string | null>(null);
  const [importDraft, setImportDraft] = useState<{
    fileName: string;
    manuscript: ImportedManuscript;
  } | null>(null);
  const [importSceneTitles, setImportSceneTitles] = useState<string[]>([]);
  const [generatingDescription, setGeneratingDescription] = useState(false);
  const [focusedClaimId, setFocusedClaimId] = useState<number | null>(null);
  const [claimFocusSpan, setClaimFocusSpan] = useState<{
    offset: number;
    length: number;
  } | null>(null);
  const errorBoxRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const sceneTextRef = useRef(sceneText);
  const sceneEditorRef = useRef<SceneTextEditorHandle>(null);
  const rightPanelRef = useRef<WorkspaceRightPanelHandle>(null);
  const workspace = useWorkspaceLayout();
  const {
    leftOpen,
    rightOpen,
    leftWidth,
    rightWidth,
    sceneEditorHeight,
    isWritingFocus,
    setLeftOpen,
    setRightOpen,
    resizeLeft,
    resizeRight,
    enterWritingFocus,
    exitWritingFocus,
  } = workspace;

  const loadScenes = useCallback(async () => {
    setScenesLoading(true);
    try {
      const data = await fetchScenes(storyId);
      setScenes(data);
      return data;
    } catch (e) {
      setError(formatErr(e));
      return [];
    } finally {
      setScenesLoading(false);
    }
  }, [storyId]);

  const resetSceneEditor = useCallback(
    (sceneList: SceneSummaryOut[]) => {
      setEditingSceneId(null);
      setSceneNumber(nextSceneNumber(sceneList));
      setPovCharacter("");
      setSceneText("");
      setClaims([]);
      setLastExtraction(null);
      const draft = loadSceneDraft(storyId);
      if (draft) {
        setSceneNumber(draft.sceneNumber);
        setSceneText(draft.sceneText);
      }
    },
    [storyId],
  );

  const isEditingScene = editingSceneId != null;
  const sceneFormActive =
    centerView === "scenes" && !storyLoading;

  const {
    issues: writingIssues,
    setIssues: setWritingIssues,
    checking: grammarChecking,
    checkError: grammarCheckError,
    dismissedRef: dismissedWritingRef,
  } = useGrammarCheck({
    storyId,
    sceneId: editingSceneId,
    text: sceneText,
    enabled: sceneFormActive && sceneText.trim().length >= 2,
  });

  const { saveState, lastSavedAt, markPersisted } = useSceneAutosave({
    storyId,
    sceneId: editingSceneId,
    sceneNumber,
    sceneText,
    povCharacter,
    enabled: isEditingScene && sceneFormActive,
  });

  const openScene = useCallback(
    async (sceneId: number) => {
      setBusy(true);
      setError(null);
      try {
        const scene = await fetchScene(storyId, sceneId);
        setEditingSceneId(scene.id);
        setSceneNumber(scene.scene_number);
        setPovCharacter(scene.pov_character ?? "");
        setSceneText(scene.text);
        setClaims(scene.claims);
        setLastExtraction(null);
        markPersisted({
          sceneNumber: scene.scene_number,
          sceneText: scene.text.trim(),
          povCharacter: (scene.pov_character ?? "").trim(),
        });
      } catch (err) {
        setError(formatErr(err));
      } finally {
        setBusy(false);
      }
    },
    [storyId, markPersisted],
  );

  useEffect(() => {
    let cancelled = false;
    async function loadStory() {
      setStoryLoading(true);
      setError(null);
      try {
        const s = await fetchStory(storyId);
        if (cancelled) return;
        setTitle(s.title);
        setDescription(s.description ?? "");
        setCenterView("scenes");
        const sceneList = await fetchScenes(storyId);
        if (cancelled) return;
        setScenes(sceneList);
        resetSceneEditor(sceneList);
      } catch (err) {
        if (!cancelled) setError(formatErr(err));
      } finally {
        if (!cancelled) setStoryLoading(false);
      }
    }
    void loadStory();
    return () => {
      cancelled = true;
    };
  }, [storyId, resetSceneEditor]);

  useEffect(() => {
    if (storyLoading) return;
    void loadScenes();
  }, [storyId, loadScenes, storyLoading]);

  const loadIssues = useCallback(async () => {
    setIssuesLoading(true);
    setError(null);
    try {
      const data = await fetchValidationIssues(storyId);
      setIssues(data);
      setIssuesLoadedAt(new Date().toISOString());
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setIssuesLoading(false);
    }
  }, [storyId]);

  useEffect(() => {
    if (storyLoading) return;
    void loadIssues();
  }, [storyId, loadIssues, storyLoading]);

  useEffect(() => {
    if (error && errorBoxRef.current) {
      errorBoxRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [error]);

  function cancelImport() {
    setImportDraft(null);
    setImportSceneTitles([]);
  }

  async function maybeGenerateDescription(
    id: number,
    hasDescription: boolean,
  ): Promise<string | null> {
    if (hasDescription) return null;
    try {
      const result = await generateStoryDescription(id);
      setDescription(result.description);
      return result.source;
    } catch {
      return null;
    }
  }

  async function onSaveStoryDetails(e: React.FormEvent) {
    e.preventDefault();
    const nextTitle = title.trim();
    if (!nextTitle) {
      setError("Story name cannot be empty.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await updateStory(storyId, {
        title: nextTitle,
        description: description.trim(),
      });
      setTitle(updated.title);
      setDescription(updated.description ?? "");
      setImportStatus("Story details saved.");
      setCenterView("scenes");
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  async function onGenerateDescriptionClick() {
    setGeneratingDescription(true);
    setError(null);
    try {
      const result = await generateStoryDescription(storyId);
      setDescription(result.description);
      await updateStory(storyId, { description: result.description });
      const via =
        result.source === "openai"
          ? "AI"
          : "a quick summary (add OPENAI_API_KEY for richer AI)";
      setImportStatus(`Description generated via ${via}.`);
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setGeneratingDescription(false);
    }
  }

  async function onImportFilePicked(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    if (!isSupportedManuscriptFile(file)) {
      setError("Please choose a .docx, .txt, or .md file from your device.");
      return;
    }

    setBusy(true);
    setError(null);
    setImportStatus(null);
    try {
      const raw = await readManuscriptFile(file);
      if (!raw.trim()) {
        setError("That file is empty.");
        return;
      }
      const manuscript = parseManuscriptText(file.name, raw);
      setImportDraft({ fileName: file.name, manuscript });
      setImportSceneTitles(
        manuscript.scenes.map((s) => s.title ?? ""),
      );
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  async function onConfirmImport(e: React.FormEvent) {
    e.preventDefault();
    if (!importDraft) return;

    setBusy(true);
    setError(null);
    try {
      const existingScenes = await fetchScenes(storyId);
      let sceneNum = nextSceneNumber(existingScenes);

      for (let i = 0; i < importDraft.manuscript.scenes.length; i++) {
        const scene = importDraft.manuscript.scenes[i];
        const label = importSceneTitles[i]?.trim() || scene.title;
        await addScene(storyId, {
          scene_number: sceneNum,
          text: formatSceneText(label, scene.text),
          claims: [],
        });
        sceneNum += 1;
      }

      const sceneList = (await loadScenes()) ?? [];
      resetSceneEditor(sceneList);

      const meta = await fetchStory(storyId);
      const aiSource = meta.description?.trim()
        ? null
        : await maybeGenerateDescription(storyId, false);

      let status = `Imported ${importDraft.manuscript.scenes.length} chapter${importDraft.manuscript.scenes.length === 1 ? "" : "s"} into this story.`;
      if (aiSource) {
        status +=
          aiSource === "openai"
            ? " AI wrote the story description from your chapters."
            : " A short description was drafted from your chapters (set OPENAI_API_KEY for full AI).";
      }
      setImportStatus(status);
      cancelImport();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  async function onExportStory() {
    setBusy(true);
    setError(null);
    try {
      const sceneList = await fetchScenes(storyId);
      const lines: string[] = [`# ${title}`, ""];
      if (description.trim()) {
        lines.push(description.trim(), "", "---", "");
      }
      for (const sc of sceneList) {
        const full = await fetchScene(storyId, sc.id);
        lines.push(`## Chapter ${full.scene_number}`, "", full.text, "");
        if (full.claims.length > 0) {
          lines.push("### Claims", "");
          for (const c of full.claims) {
            lines.push(
              `- ${c.subject} | ${c.predicate} | ${c.object}${c.is_major_plotline ? " (major)" : ""}`,
            );
          }
          lines.push("");
        }
        lines.push("---", "");
      }
      const blob = new Blob([lines.join("\n").trim() + "\n"], {
        type: "text/markdown;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${title.replace(/[^\w\s-]/g, "").trim() || "story"}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  async function onClaimApprove(claimId: number) {
    if (editingSceneId == null) return;
    setBusy(true);
    try {
      await updateClaimStatus(storyId, editingSceneId, claimId, {
        status: "approved",
      });
      await openScene(editingSceneId);
      await loadIssues();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  async function onClaimReject(claimId: number) {
    if (editingSceneId == null) return;
    setBusy(true);
    try {
      await updateClaimStatus(storyId, editingSceneId, claimId, {
        status: "rejected",
      });
      await openScene(editingSceneId);
      await loadIssues();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  async function onAddScene(e: React.FormEvent) {
    e.preventDefault();
    if (!sceneText.trim()) {
      setError("Chapter text is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body = {
        scene_number: sceneNumber,
        text: sceneText.trim(),
        pov_character: povCharacter.trim() || null,
        claims: [] as { subject: string; predicate: string; object: string; is_major_plotline: boolean }[],
      };
      let savedId = editingSceneId;
      let extraction: SceneExtractionOut | null = null;
      if (editingSceneId != null) {
        const res = await updateScene(storyId, editingSceneId, {
          ...body,
          run_extraction: true,
        });
        extraction = res.extraction ?? null;
      } else {
        const res = await addScene(storyId, body);
        savedId = res.id;
        extraction = res.extraction ?? null;
      }
      setLastExtraction(extraction);
      const sceneList = (await loadScenes()) ?? [];
      const trimmed = sceneText.trim();
      markPersisted({
        sceneNumber,
        sceneText: trimmed,
        povCharacter: povCharacter.trim(),
      });
      clearSceneDraft(storyId);
      if (savedId != null) {
        await openScene(savedId);
        markPersisted({
          sceneNumber,
          sceneText: trimmed,
          povCharacter: povCharacter.trim(),
        });
      } else {
        resetSceneEditor(sceneList);
      }
      await loadIssues();
      if (
        extraction &&
        extraction.needs_review_count + extraction.suggested_count > 0
      ) {
        rightPanelRef.current?.expandSection("newClaims");
      }
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  const sceneDisabled = busy || !sceneFormActive;

  useEffect(() => {
    sceneTextRef.current = sceneText;
  }, [sceneText]);

  useEffect(() => {
    if (!busy) {
      setAnalyzeStatus(null);
      return;
    }
    const steps = [
      "Saving chapter…",
      "Chunking text…",
      "Running structural scan…",
      "Extracting story memory…",
      "Validating canon…",
    ];
    let index = 0;
    setAnalyzeStatus(steps[0]);
    const timer = window.setInterval(() => {
      index = Math.min(index + 1, steps.length - 1);
      setAnalyzeStatus(steps[index]);
    }, 1100);
    return () => window.clearInterval(timer);
  }, [busy]);

  useEffect(() => {
    setFocusedClaimId(null);
    setClaimFocusSpan(null);
  }, [editingSceneId]);

  const rememberWritingDismissal = useCallback(
    (issue: WritingIssue) => {
      const fp = writingIssueFingerprint(issue);
      rememberDismissedWritingIssue(storyId, editingSceneId, fp);
      dismissedWritingRef.current.add(fp);
    },
    [storyId, editingSceneId, dismissedWritingRef],
  );

  const dismissWritingIssue = useCallback(
    (issue: WritingIssue) => {
      rememberWritingDismissal(issue);
      const fp = writingIssueFingerprint(issue);
      setWritingIssues((prev) =>
        prev.filter((item) => writingIssueFingerprint(item) !== fp),
      );
    },
    [rememberWritingDismissal, setWritingIssues],
  );

  const focusClaimInText = useCallback(
    (claim: ClaimOut) => {
      const span = findClaimEvidenceSpan(sceneText, claim);
      setFocusedClaimId(claim.id);
      setClaimFocusSpan(span);
      if (claim.status === "rejected") {
        rightPanelRef.current?.expandSection("rejectedClaims");
      } else if (claim.status === "approved") {
        rightPanelRef.current?.expandSection("acceptedClaims");
      } else {
        rightPanelRef.current?.expandSection("newClaims");
      }
      if (span) {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            sceneEditorRef.current?.scrollToRange(
              span.offset,
              span.offset + span.length,
            );
          });
        });
      }
    },
    [sceneText],
  );

  const applyWritingSuggestion = useCallback(
    (issue: WritingIssue, replacement: string) => {
      rememberWritingDismissal(issue);
      const nextText = applyTextReplacement(
        sceneText,
        issue.offset,
        issue.length,
        replacement,
      );
      sceneTextRef.current = nextText;
      setSceneText(nextText);
      setWritingIssues((prev) => issuesAfterApply(prev, issue, replacement));
      if (editingSceneId != null) {
        markPersisted({
          sceneNumber,
          sceneText: nextText.trim(),
          povCharacter: povCharacter.trim(),
        });
      }
    },
    [
      sceneText,
      sceneNumber,
      povCharacter,
      editingSceneId,
      markPersisted,
      rememberWritingDismissal,
      setWritingIssues,
    ],
  );

  useEffect(() => {
    if (editingSceneId != null || storyLoading) return;
    const trimmed = sceneText.trim();
    if (!trimmed) {
      clearSceneDraft(storyId);
      return;
    }
    saveSceneDraft(storyId, {
      sceneNumber,
      sceneText: trimmed,
      updatedAt: new Date().toISOString(),
    });
  }, [storyId, editingSceneId, sceneNumber, sceneText, storyLoading]);

  const sceneTextareaClass = cn(
    "w-full resize-y text-[15px] leading-7",
    "bg-[#0f172a]/92 text-slate-50 placeholder:text-slate-300",
    "border-white/10 focus-visible:ring-2 focus-visible:ring-sky-200/30",
    sceneEditorHeight === "default" && "scene-textarea--default",
    sceneEditorHeight === "large" && "scene-textarea--large",
    sceneEditorHeight === "focus" && "scene-textarea--focus",
  );

  return (
    <div className="workspace-canvas workspace-canvas--editor flex min-h-0 flex-col">
      <div className="workspace-content flex min-h-0 flex-1 flex-col">
      <header className="glass-panel flex h-14 shrink-0 items-center justify-between border-b border-border/60 px-4 lg:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            href="/"
            className="shrink-0 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            ← Library
          </Link>
          <div className="hidden h-4 w-px shrink-0 bg-border sm:block" aria-hidden />
          <div className="min-w-0">
            <p className="soft-heading truncate text-sm font-semibold leading-none text-foreground">
              {title || "Loading…"}
            </p>
            <p className="mt-0.5 truncate text-xs text-muted-foreground">
              Chapters & continuity
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Badge variant="default">#{storyId}</Badge>
          <UserAccountMenuGate />
        </div>
      </header>

      <div
        className="glass-panel flex shrink-0 items-center justify-end border-b border-border/60 px-3 py-2 lg:px-6"
        role="toolbar"
        aria-label="Writing focus"
      >
        <Button
          type="button"
          variant={isWritingFocus ? "cta" : "outline"}
          size="sm"
          onClick={() =>
            isWritingFocus ? exitWritingFocus() : enterWritingFocus()
          }
        >
          {isWritingFocus ? "Exit focus mode" : "Focus on writing"}
        </Button>
      </div>

      {error ? (
        <div ref={errorBoxRef} className="shrink-0 border-b border-border px-4 py-3 lg:px-6">
          <Alert title="Request failed">
            <p className="whitespace-pre-wrap text-foreground">{error}</p>
            <p className="mt-2 text-xs">
              Ensure the API is running on port{" "}
              <code className="rounded bg-muted px-1 font-mono text-xs">
                8001
              </code>{" "}
              and{" "}
              <code className="rounded bg-muted px-1 font-mono text-xs">
                API_PROXY_TARGET
              </code>{" "}
              is set in{" "}
              <code className="rounded bg-muted px-1 font-mono text-xs">
                apps/web/.env.local
              </code>
              .
            </p>
          </Alert>
        </div>
      ) : null}

      <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden lg:flex-row">
        {!leftOpen ? (
          <button
            type="button"
            className="workspace-edge-tab workspace-edge-tab--left"
            onClick={() => setLeftOpen(true)}
            aria-label="Show chapters panel"
          >
            &gt;
          </button>
        ) : null}
        {!rightOpen ? (
          <button
            type="button"
            className="workspace-edge-tab workspace-edge-tab--right"
            onClick={() => setRightOpen(true)}
            aria-label="Show checks panel"
          >
            &lt;
          </button>
        ) : null}
        {leftOpen ? (
          <div className="workspace-panel-shell">
            <aside
              className="workspace-side-panel flex flex-col overflow-hidden border-b border-sidebar-border bg-sidebar/50 text-xs shadow-[0_18px_55px_rgba(0,0,0,0.06)] backdrop-blur-xl lg:border-b-0 lg:border-r"
              style={{ ["--panel-w" as string]: `${leftWidth}px` }}
            >
              <div className="shrink-0 border-b border-sidebar-border bg-sidebar/80 px-3 py-2">
                <span className="text-xs font-semibold text-foreground">
                  Chapters & import
                </span>
              </div>
          <div className="flex-1 space-y-5 overflow-y-auto p-3 lg:p-4">
            <Panel
              compact
              title="Import manuscript"
              description="Add chapters from a file on this device into this story."
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".docx,.txt,.md,.markdown,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                className="sr-only"
                onChange={(e) => void onImportFilePicked(e)}
              />
              {importDraft ? (
                <form
                  onSubmit={(e) => void onConfirmImport(e)}
                  className="mb-4 space-y-4 rounded-lg border border-primary/30 bg-card p-3 shadow-sm"
                >
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      Import preview
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {importDraft.fileName} ·{" "}
                      {importDraft.manuscript.scenes.length} chapter
                      {importDraft.manuscript.scenes.length === 1 ? "" : "s"}
                    </p>
                  </div>

                  <div className="space-y-2">
                    <FieldLabel>Chapter names</FieldLabel>
                    <ul className="max-h-48 space-y-2 overflow-y-auto">
                      {importDraft.manuscript.scenes.map((sc, i) => (
                        <li
                          key={sc.scene_number}
                          className="rounded-md border border-border bg-muted/20 p-2"
                        >
                          <span className="text-xs font-medium text-muted-foreground">
                            Chapter {sc.scene_number}
                          </span>
                          <Input
                            value={importSceneTitles[i] ?? ""}
                            onChange={(e) =>
                              setImportSceneTitles((prev) => {
                                const next = [...prev];
                                next[i] = e.target.value;
                                return next;
                              })
                            }
                            disabled={busy}
                            placeholder="Chapter title (optional)"
                            className="mt-1"
                          />
                          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                            {excerpt(sc.text, 100)}
                          </p>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="flex flex-col gap-2">
                    <Button type="submit" variant="cta" disabled={busy} className="w-full">
                      {busy ? (
                        <>
                          <Spinner /> Importing…
                        </>
                      ) : (
                        "Import chapters"
                      )}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={busy}
                      onClick={cancelImport}
                    >
                      Cancel
                    </Button>
                  </div>
                </form>
              ) : (
                <div className="mb-3 flex flex-col gap-2">
                  <Button
                    type="button"
                    variant="cta"
                    size="sm"
                    className="w-full"
                    disabled={busy}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    {busy ? (
                      <>
                        <Spinner /> Reading file…
                      </>
                    ) : (
                      "Import from this device"
                    )}
                  </Button>
                </div>
              )}

              <p className="mb-3 text-xs leading-5 text-muted-foreground">
                <span className="font-medium text-foreground">
                  .docx, .txt, or .md
                </span>{" "}
                from your computer. Word headings become chapter breaks; or use{" "}
                <code className="rounded bg-muted px-1 font-mono text-[10px]">
                  ---
                </code>
                ,{" "}
                <code className="rounded bg-muted px-1 font-mono text-[10px]">
                  ## Heading
                </code>
                , or{" "}
                <code className="rounded bg-muted px-1 font-mono text-[10px]">
                  Chapter 1
                </code>
                .
              </p>

              {importStatus ? (
                <p className="mb-3 rounded-md border border-success/30 bg-success/10 px-2.5 py-2 text-xs leading-5 text-foreground">
                  {importStatus}
                </p>
              ) : null}

              <details className="mb-4 rounded-lg border border-sidebar-border bg-card/60 px-3 py-2 text-xs text-muted-foreground">
                <summary className="cursor-pointer font-medium text-foreground">
                  Google Drive, Notion, or Keep
                </summary>
                <p className="mt-2 leading-5">
                  inferStories does not connect to those apps yet. Export or
                  download your notes as{" "}
                  <span className="text-foreground">.docx</span>,{" "}
                  <span className="text-foreground">.txt</span>, or{" "}
                  <span className="text-foreground">.md</span>, then use{" "}
                  <span className="text-foreground">Import from this device</span>
                  . In Notion: ⋯ → Export → Markdown. In Keep: copy into a .txt
                  file. From Drive: download a text or markdown file.
                </p>
              </details>

            </Panel>

            <Panel
                compact
                title="Chapters"
                description="Select a chapter to edit, or write a new one."
              >
                <Button
                  type="button"
                  variant={editingSceneId == null ? "default" : "outline"}
                  size="sm"
                  className="mb-3 w-full"
                  disabled={busy}
                  onClick={() => resetSceneEditor(scenes)}
                >
                  + Write new chapter
                </Button>
                {scenesLoading ? (
                  <p className="text-sm text-muted-foreground">Loading chapters…</p>
                ) : scenes.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No chapters yet — add your first in the editor.
                  </p>
                ) : (
                  <ul className="space-y-1.5">
                    {scenes.map((sc) => (
                      <li key={sc.id}>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void openScene(sc.id)}
                          className={cn(
                            "w-full rounded-md border px-2.5 py-2 text-left transition-colors",
                            editingSceneId === sc.id
                              ? "border-primary/40 bg-accent shadow-sm"
                              : "border-transparent bg-card hover:border-sidebar-border",
                          )}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-semibold text-foreground">
                              Chapter {sc.scene_number}
                            </span>
                            <span className="shrink-0">
                              <Badge variant="secondary">{sc.claim_count}</Badge>
                            </span>
                          </div>
                          <p className="mt-0.5 line-clamp-2 text-[11px] leading-4 text-muted-foreground">
                            {excerpt(sc.text, 80)}
                          </p>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-4 w-full"
                  disabled={busy}
                  onClick={() => void onExportStory()}
                >
                  Download to this device (.md)
                </Button>
              </Panel>
          </div>
            </aside>
            <PanelEdgeCollapse
              edge="left"
              label="chapters"
              onCollapse={() => setLeftOpen(false)}
            />
            <PanelResizeHandle side="left" onResize={resizeLeft} />
          </div>
        ) : null}

        {/* Center — story setup or scene editor */}
        <main
          className={cn(
            "flex min-h-[320px] min-w-0 flex-1 flex-col overflow-y-auto bg-transparent",
            isWritingFocus && "lg:px-2",
          )}
        >
          <div
            className={cn(
              "mx-auto w-full p-4 lg:p-6",
              isWritingFocus ? "max-w-none flex-1" : "max-w-3xl",
            )}
          >
            {storyLoading ? (
              <p className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
                <Spinner /> Loading story…
              </p>
            ) : centerView === "story-form" ? (
              <Panel
                title="Story details"
                description="Update the name and synopsis, then save to return to chapters."
              >
                <form
                  onSubmit={(e) => void onSaveStoryDetails(e)}
                  className="space-y-5 rounded-lg border border-border bg-card p-5 shadow-sm"
                >
                  <label className="flex flex-col gap-1.5">
                    <FieldLabel>Story name</FieldLabel>
                    <Input
                      required
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      disabled={busy}
                      placeholder="The Flammae Bond"
                    />
                  </label>
                  <label className="flex flex-col gap-1.5">
                    <FieldLabel>Description</FieldLabel>
                    <Textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      disabled={busy || generatingDescription}
                      placeholder="Synopsis, genre notes, or story bible summary"
                      className="min-h-[120px] leading-relaxed"
                    />
                  </label>
                  <>
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={
                          busy || generatingDescription || scenes.length === 0
                        }
                        onClick={() => void onGenerateDescriptionClick()}
                      >
                        {generatingDescription ? (
                          <>
                            <Spinner /> Generating…
                          </>
                        ) : (
                          "Generate description with AI"
                        )}
                      </Button>
                      {scenes.length === 0 ? (
                        <p className="text-xs text-muted-foreground">
                          Add at least one chapter to generate a description.
                        </p>
                      ) : null}
                  </>
                  <div className="flex flex-wrap gap-2">
                    <Button type="submit" variant="cta" disabled={busy}>
                      {busy ? (
                        <>
                          <Spinner /> Saving…
                        </>
                      ) : (
                        "Save story details"
                      )}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={busy}
                      onClick={() => setCenterView("scenes")}
                    >
                      Cancel
                    </Button>
                  </div>
                </form>
              </Panel>
            ) : (
              <Panel
                title={isEditingScene ? `Editing chapter ${sceneNumber}` : "New chapter"}
                description={
                  isEditingScene
                    ? "Update your chapter and save — story memory is extracted automatically."
                    : "Write your chapter and submit — we detect characters, relationships, and canon."
                }
              >
                <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-foreground">
                      {title}
                    </p>
                    {description.trim() ? (
                      <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                        {description}
                      </p>
                    ) : (
                      <p className="mt-0.5 text-xs italic text-muted-foreground">
                        No description yet
                      </p>
                    )}
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="shrink-0"
                    disabled={busy}
                    onClick={() => setCenterView("story-form")}
                  >
                    Edit story
                  </Button>
                </div>
                <form
                  onSubmit={onAddScene}
                  className="glass-panel space-y-5 rounded-[var(--radius-card)] p-5"
                >
                  <div className="space-y-4">
                    <div className="flex flex-wrap gap-4">
                      <label className="flex w-full max-w-[8rem] flex-col gap-1.5">
                        <FieldLabel>Chapter #</FieldLabel>
                        <Input
                          type="number"
                          required
                          min={1}
                          value={sceneNumber}
                          onChange={(e) =>
                            setSceneNumber(Number(e.target.value))
                          }
                          disabled={sceneDisabled}
                        />
                      </label>
                      <label className="flex min-w-[12rem] flex-1 flex-col gap-1.5">
                        <FieldLabel>POV character</FieldLabel>
                        <Input
                          type="text"
                          placeholder="e.g. Marcus"
                          value={povCharacter}
                          onChange={(e) => setPovCharacter(e.target.value)}
                          disabled={sceneDisabled}
                        />
                        <span className="text-[11px] text-muted-foreground">
                          Unquoted &quot;I&quot; in this chapter is treated as this
                          character when analyzing memory.
                        </span>
                      </label>
                    </div>
                    <label className="flex flex-col gap-1.5">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <FieldLabel>Chapter text</FieldLabel>
                        <span className="text-[11px] text-muted-foreground">
                          {isEditingScene ? (
                            <>
                              {saveState === "saving"
                                ? "Saving…"
                                : saveState === "saved" && lastSavedAt
                                  ? `Saved ${lastSavedAt.toLocaleTimeString()}`
                                  : saveState === "error"
                                    ? "Autosave failed — use Save & analyze below"
                                    : saveState === "dirty"
                                      ? "Saving soon…"
                                      : "Text autosaves · use Save & analyze for memory"}
                              {grammarChecking
                                ? " · Checking grammar…"
                                : writingIssues.length > 0
                                  ? ` · ${writingIssues.length} grammar issue${writingIssues.length === 1 ? "" : "s"}`
                                  : null}
                            </>
                          ) : sceneText.trim() ? (
                            "Draft kept on this device until you submit"
                          ) : (
                            "Drag the corner to resize · Focus on writing above"
                          )}
                        </span>
                      </div>
                      <p className="text-[11px] text-muted-foreground">
                        Blue underlines are grammar/spelling. Right-click an
                        underline to apply a fix or dismiss (dismissed issues
                        stay hidden after refresh).
                      </p>
                      {grammarCheckError ? (
                        <p className="text-[11px] text-destructive">
                          {grammarCheckError}
                        </p>
                      ) : null}
                      <SceneTextEditor
                        ref={sceneEditorRef}
                        required
                        value={sceneText}
                        claimFocusSpan={claimFocusSpan}
                        onChange={(value) => {
                          const prev = sceneTextRef.current;
                          sceneTextRef.current = value;
                          setSceneText(value);
                          setWritingIssues((current) =>
                            reconcileWritingIssuesAfterEdit(
                              prev,
                              value,
                              current,
                            ),
                          );
                        }}
                        issues={writingIssues}
                        onApplySuggestion={applyWritingSuggestion}
                        onDismissIssue={dismissWritingIssue}
                        suggestionsDisabled={sceneDisabled}
                        disabled={sceneDisabled}
                        placeholder="What happens in this chapter?"
                        className={sceneTextareaClass}
                      />
                    </label>
                  </div>

                  {!isWritingFocus ? (
                  <div className="rounded-lg border border-border/60 bg-muted/15 px-4 py-3">
                    <FieldLabel>Story memory</FieldLabel>
                    {lastExtraction ? (
                      <p
                        className={cn(
                          "mt-1 text-xs leading-5",
                          lastExtraction.error
                            ? "text-destructive"
                            : lastExtraction.claim_count === 0
                              ? "text-amber-200/90"
                              : "text-muted-foreground",
                        )}
                      >
                        {lastExtraction.error ? (
                          <>
                            <strong className="font-medium">Extraction failed:</strong>{" "}
                            {lastExtraction.error}
                          </>
                        ) : lastExtraction.claim_count === 0 ? (
                          <>
                            Analysis ran ({lastExtraction.source}) but found no
                            claims. Try richer prose with clear character facts.
                          </>
                        ) : (
                          <>
                            {lastExtraction.claim_count} claim
                            {lastExtraction.claim_count === 1 ? "" : "s"} detected
                            — review in{" "}
                            <strong className="font-medium text-foreground">
                              New claims
                            </strong>{" "}
                            on the right (
                            {lastExtraction.needs_review_count} to review,{" "}
                            {lastExtraction.suggested_count} suggested,{" "}
                            {lastExtraction.approved_count} auto-approved).
                          </>
                        )}
                      </p>
                    ) : analyzeStatus ? (
                      <p className="mt-1 text-xs text-sky-200/90">{analyzeStatus}</p>
                    ) : (
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">
                        Autosave saves text only. Use{" "}
                        <strong className="font-medium text-foreground">
                          Save &amp; analyze memory
                        </strong>{" "}
                        below, then open{" "}
                        <strong className="font-medium text-foreground">
                          New claims
                        </strong>{" "}
                        in the right panel to approve or reject.
                      </p>
                    )}
                    {claims.length > 0 ? (
                      <p className="mt-2 text-[11px] text-muted-foreground">
                        {(() => {
                          const n = claimBucketCounts(claims);
                          return `${n.new} new · ${n.accepted} accepted · ${n.rejected} rejected`;
                        })()}
                      </p>
                    ) : null}
                    {lastExtraction ? (
                      <div className="mt-3">
                        <ExtractionDebugPanel extraction={lastExtraction} />
                      </div>
                    ) : null}
                  </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      Story memory summary is hidden in focus mode. Open the right
                      panel to review claims.
                    </p>
                  )}

                  <Button
                    type="submit"
                    variant="cta"
                    disabled={sceneDisabled}
                    className="w-full sm:w-auto"
                  >
                    {busy ? (
                      <>
                        <Spinner /> {analyzeStatus ?? "Analyzing chapter…"}
                      </>
                    ) : isEditingScene ? (
                      "Save & analyze memory"
                    ) : (
                      "Submit chapter"
                    )}
                  </Button>
                </form>
              </Panel>
            )}
          </div>
        </main>

        {rightOpen ? (
          <div className="workspace-panel-shell">
            <PanelResizeHandle side="right" onResize={resizeRight} />
            <PanelEdgeCollapse
              edge="right"
              label="checks"
              onCollapse={() => setRightOpen(false)}
            />
            <aside
              className="workspace-side-panel workspace-side-panel--checks flex min-h-0 flex-col overflow-hidden border-t border-border bg-card/45 shadow-[0_18px_55px_rgba(0,0,0,0.06)] backdrop-blur-xl lg:border-l lg:border-l-border lg:border-t-0"
              style={{ ["--panel-w" as string]: `${rightWidth}px` }}
            >
              <WorkspaceRightPanel
                ref={rightPanelRef}
                storyLoading={storyLoading}
                busy={busy}
                chapterDisabled={sceneDisabled}
                claims={claims}
                focusedClaimId={focusedClaimId}
                onClaimSelect={focusClaimInText}
                onClaimApprove={(id) => void onClaimApprove(id)}
                onClaimReject={(id) => void onClaimReject(id)}
                continuityIssues={issues}
                continuityLoading={issuesLoading}
                continuityLoadedAt={issuesLoadedAt}
                onRefreshContinuity={() => void loadIssues()}
              />
            </aside>
          </div>
        ) : null}
      </div>
      </div>
    </div>
  );
}
