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
import { DetectedStoryMemory } from "../components/DetectedStoryMemory";
import { PanelEdgeCollapse } from "../components/PanelEdgeCollapse";
import { PanelResizeHandle } from "../components/PanelResizeHandle";
import { UserAccountMenuGate } from "../components/UserAccountMenu";

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
  const [importStatus, setImportStatus] = useState<string | null>(null);
  const [importDraft, setImportDraft] = useState<{
    fileName: string;
    manuscript: ImportedManuscript;
  } | null>(null);
  const [importSceneTitles, setImportSceneTitles] = useState<string[]>([]);
  const [generatingDescription, setGeneratingDescription] = useState(false);
  const errorBoxRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
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

  const resetSceneEditor = useCallback((sceneList: SceneSummaryOut[]) => {
    setEditingSceneId(null);
    setSceneNumber(nextSceneNumber(sceneList));
    setSceneText("");
    setClaims([]);
    setLastExtraction(null);
  }, []);

  const openScene = useCallback(
    async (sceneId: number) => {
      setBusy(true);
      setError(null);
      try {
        const scene = await fetchScene(storyId, sceneId);
        setEditingSceneId(scene.id);
        setSceneNumber(scene.scene_number);
        setSceneText(scene.text);
        setClaims(scene.claims);
        setLastExtraction(null);
      } catch (err) {
        setError(formatErr(err));
      } finally {
        setBusy(false);
      }
    },
    [storyId],
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
    const kickoff = window.setTimeout(() => void loadIssues(), 0);
    const id = window.setInterval(() => void loadIssues(), 4000);
    return () => {
      window.clearTimeout(kickoff);
      window.clearInterval(id);
    };
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
        claims: [] as { subject: string; predicate: string; object: string; is_major_plotline: boolean }[],
      };
      let savedId = editingSceneId;
      let extraction: SceneExtractionOut | null = null;
      if (editingSceneId != null) {
        const res = await updateScene(storyId, editingSceneId, body);
        extraction = res.extraction ?? null;
      } else {
        const res = await addScene(storyId, body);
        savedId = res.id;
        extraction = res.extraction ?? null;
      }
      setLastExtraction(extraction);
      const sceneList = (await loadScenes()) ?? [];
      if (savedId != null) {
        await openScene(savedId);
      } else {
        resetSceneEditor(sceneList);
      }
      await loadIssues();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  const sceneDisabled = busy || centerView !== "scenes" || storyLoading;
  const isEditingScene = editingSceneId != null;

  const sceneTextareaClass = cn(
    "w-full resize-y text-[15px] leading-7",
    "bg-[#0f172a]/92 text-slate-50 placeholder:text-slate-300",
    "border-white/10 focus-visible:ring-2 focus-visible:ring-sky-200/30",
    sceneEditorHeight === "default" && "scene-textarea--default",
    sceneEditorHeight === "large" && "scene-textarea--large",
    sceneEditorHeight === "focus" && "scene-textarea--focus",
  );

  return (
    <div className="workspace-canvas flex min-h-screen flex-col">
      <div className="workspace-content flex min-h-screen flex-col">
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

      <div className="relative flex min-h-0 flex-1 flex-col lg:flex-row">
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
            aria-label="Show continuity panel"
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
                    <label className="flex flex-col gap-1.5">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <FieldLabel>Chapter text</FieldLabel>
                        <span className="text-[11px] text-muted-foreground">
                          Drag the corner to resize · use Focus on writing above
                        </span>
                      </div>
                      <Textarea
                        required
                        value={sceneText}
                        onChange={(e) => setSceneText(e.target.value)}
                        disabled={sceneDisabled}
                        placeholder="What happens in this chapter?"
                        className={sceneTextareaClass}
                      />
                    </label>
                  </div>

                  {!isWritingFocus ? (
                  <div>
                    <FieldLabel>Detected story memory</FieldLabel>
                    {lastExtraction ? (
                      <p className="mb-3 mt-1 text-xs text-muted-foreground">
                        Found {lastExtraction.claim_count} claim
                        {lastExtraction.claim_count === 1 ? "" : "s"} (
                        {lastExtraction.approved_count} in canon,{" "}
                        {lastExtraction.needs_review_count} to review) via{" "}
                        {lastExtraction.source}.
                        {lastExtraction.word_count > 3000
                          ? " Long chapter — processed in multiple sections."
                          : null}
                      </p>
                    ) : (
                      <p className="mb-3 mt-1 text-xs leading-5 text-muted-foreground">
                        High-confidence facts enter canon automatically. Medium
                        confidence appears for your review.
                      </p>
                    )}
                    <DetectedStoryMemory
                      claims={claims.filter((c) => c.status !== "rejected")}
                      disabled={sceneDisabled}
                      onApprove={(id) => void onClaimApprove(id)}
                      onReject={(id) => void onClaimReject(id)}
                    />
                  </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      Story memory is hidden in focus mode. Exit focus to review
                      detected claims.
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
                        <Spinner /> Saving chapter…
                      </>
                    ) : (
                      isEditingScene ? "Save changes" : "Submit chapter"
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
              label="continuity"
              onCollapse={() => setRightOpen(false)}
            />
            <aside
              className="workspace-side-panel flex flex-col overflow-hidden border-t border-border bg-card/45 shadow-[0_18px_55px_rgba(0,0,0,0.06)] backdrop-blur-xl lg:border-l lg:border-l-border lg:border-t-0"
              style={{ ["--panel-w" as string]: `${rightWidth}px` }}
            >
          <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border bg-secondary/40 px-4 py-3">
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-secondary-foreground">
                Continuity
              </h2>
              <p className="text-xs text-muted-foreground">
                Auto-refreshes every 4s
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={storyLoading || busy}
              onClick={() => void loadIssues()}
            >
              Refresh
            </Button>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {storyLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : issuesLoading && issues.length === 0 ? (
              <div className="space-y-3">
                {[1, 2, 3].map((n) => (
                  <div
                    key={n}
                    className="h-16 animate-pulse rounded-lg bg-muted"
                  />
                ))}
              </div>
            ) : issues.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border bg-muted/30 px-4 py-8 text-center">
                <p className="text-sm font-medium text-foreground">
                  No issues yet
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Contradictions show up when a new chapter conflicts with earlier
                  claims.
                </p>
              </div>
            ) : (
              <ul className="space-y-3">
                {issues.map((iss) => (
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
            {issuesLoadedAt ? (
              <p className="mt-4 text-center text-xs text-muted-foreground">
                Updated {new Date(issuesLoadedAt).toLocaleTimeString()}
              </p>
            ) : null}
          </div>
            </aside>
          </div>
        ) : null}
      </div>
      </div>
    </div>
  );
}
