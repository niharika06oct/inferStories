"use client";

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
  createStory,
  fetchScene,
  fetchScenes,
  fetchStories,
  fetchStory,
  fetchValidationIssues,
  generateStoryDescription,
  updateScene,
  updateStory,
  type ClaimIn,
  type SceneSummaryOut,
  type StoryListOut,
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

const emptyClaim = (): ClaimIn => ({
  subject: "",
  predicate: "",
  object: "",
  is_major_plotline: false,
});

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

export default function StoryWorkspace() {
  const [stories, setStories] = useState<StoryListOut[]>([]);
  const [storiesLoading, setStoriesLoading] = useState(true);
  const [scenes, setScenes] = useState<SceneSummaryOut[]>([]);
  const [scenesLoading, setScenesLoading] = useState(false);
  type CenterView = "empty" | "story-form" | "scenes";
  const [centerView, setCenterView] = useState<CenterView>("empty");

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [storyId, setStoryId] = useState<number | null>(null);

  const [editingSceneId, setEditingSceneId] = useState<number | null>(null);
  const [sceneNumber, setSceneNumber] = useState(1);
  const [sceneText, setSceneText] = useState("");
  const [claims, setClaims] = useState<ClaimIn[]>([emptyClaim()]);

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
  const [importStoryTitle, setImportStoryTitle] = useState("");
  const [importTarget, setImportTarget] = useState<"new" | "existing">("new");
  const [importExistingStoryId, setImportExistingStoryId] = useState<
    number | null
  >(null);
  const [importSceneTitles, setImportSceneTitles] = useState<string[]>([]);
  const [importStoryDescription, setImportStoryDescription] = useState("");
  const [generatingDescription, setGeneratingDescription] = useState(false);
  const errorBoxRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadStories = useCallback(async () => {
    setStoriesLoading(true);
    try {
      const data = await fetchStories();
      setStories(data);
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setStoriesLoading(false);
    }
  }, []);

  const loadScenes = useCallback(async () => {
    if (storyId == null) {
      setScenes([]);
      return;
    }
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
    setClaims([emptyClaim()]);
  }, []);

  const openStory = useCallback(
    async (id: number) => {
      setBusy(true);
      setError(null);
      try {
        const s = await fetchStory(id);
        setStoryId(s.id);
        setTitle(s.title);
        setDescription(s.description ?? "");
        setEditingSceneId(null);
        setCenterView("scenes");
        const sceneList = await fetchScenes(id);
        setScenes(sceneList);
        resetSceneEditor(sceneList);
      } catch (err) {
        setError(formatErr(err));
      } finally {
        setBusy(false);
      }
    },
    [resetSceneEditor],
  );

  const openScene = useCallback(
    async (sceneId: number) => {
      if (storyId == null) return;
      setBusy(true);
      setError(null);
      try {
        const scene = await fetchScene(storyId, sceneId);
        setEditingSceneId(scene.id);
        setSceneNumber(scene.scene_number);
        setSceneText(scene.text);
        setClaims(
          scene.claims.length > 0
            ? scene.claims.map((c) => ({
                subject: c.subject,
                predicate: c.predicate,
                object: c.object,
                is_major_plotline: c.is_major_plotline,
              }))
            : [emptyClaim()],
        );
      } catch (err) {
        setError(formatErr(err));
      } finally {
        setBusy(false);
      }
    },
    [storyId],
  );

  useEffect(() => {
    void loadStories();
  }, [loadStories]);

  useEffect(() => {
    if (storyId == null) return;
    void loadScenes();
  }, [storyId, loadScenes]);

  const loadIssues = useCallback(async () => {
    if (storyId == null) return;
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
    if (storyId == null) return;
    const kickoff = window.setTimeout(() => void loadIssues(), 0);
    const id = window.setInterval(() => void loadIssues(), 4000);
    return () => {
      window.clearTimeout(kickoff);
      window.clearInterval(id);
    };
  }, [storyId, loadIssues]);

  useEffect(() => {
    if (error && errorBoxRef.current) {
      errorBoxRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [error]);

  async function onCreateStory(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const s = await createStory({
        title: title.trim(),
        description: description.trim() || undefined,
      });
      setStoryId(s.id);
      setCenterView("scenes");
      await loadStories();
      const sceneList = await fetchScenes(s.id);
      setScenes(sceneList);
      resetSceneEditor(sceneList);
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  function startNewStory() {
    setStoryId(null);
    setTitle("");
    setDescription("");
    setScenes([]);
    setEditingSceneId(null);
    setCenterView("story-form");
    cancelImport();
  }

  function cancelImport() {
    setImportDraft(null);
    setImportSceneTitles([]);
    setImportStoryTitle("");
    setImportStoryDescription("");
    setImportTarget("new");
    setImportExistingStoryId(null);
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
    if (storyId == null) return;
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
      await loadStories();
      setImportStatus("Story details saved.");
      setCenterView("scenes");
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  async function onGenerateDescriptionClick() {
    if (storyId == null) return;
    setGeneratingDescription(true);
    setError(null);
    try {
      const result = await generateStoryDescription(storyId);
      setDescription(result.description);
      await updateStory(storyId, { description: result.description });
      await loadStories();
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
      setImportStoryTitle(manuscript.title);
      setImportSceneTitles(
        manuscript.scenes.map((s) => s.title ?? ""),
      );
      if (storyId != null) {
        setImportTarget("existing");
        setImportExistingStoryId(storyId);
      } else {
        setImportTarget("new");
        setImportExistingStoryId(null);
      }
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  async function onConfirmImport(e: React.FormEvent) {
    e.preventDefault();
    if (!importDraft) return;

    const storyTitle = importStoryTitle.trim();
    if (importTarget === "new" && !storyTitle) {
      setError("Enter a story name for the import.");
      return;
    }
    if (importTarget === "existing" && importExistingStoryId == null) {
      setError("Choose which story to add scenes to.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      let targetId: number;
      if (importTarget === "new") {
        const desc =
          importStoryDescription.trim() ||
          undefined;
        const story = await createStory({
          title: storyTitle,
          description: desc,
        });
        targetId = story.id;
      } else {
        targetId = importExistingStoryId!;
      }

      const existingScenes =
        importTarget === "existing"
          ? await fetchScenes(targetId)
          : [];
      let sceneNum = nextSceneNumber(existingScenes);

      for (let i = 0; i < importDraft.manuscript.scenes.length; i++) {
        const scene = importDraft.manuscript.scenes[i];
        const label = importSceneTitles[i]?.trim() || scene.title;
        await addScene(targetId, {
          scene_number: sceneNum,
          text: formatSceneText(label, scene.text),
          claims: [],
        });
        sceneNum += 1;
      }

      await loadStories();
      await openStory(targetId);

      const meta = await fetchStory(targetId);
      const aiSource = meta.description?.trim()
        ? null
        : await maybeGenerateDescription(targetId, false);

      const dest =
        importTarget === "new"
          ? `new story “${storyTitle}”`
          : `existing story`;
      let status = `Imported ${importDraft.manuscript.scenes.length} scene${importDraft.manuscript.scenes.length === 1 ? "" : "s"} into ${dest}. Add claims in the editor.`;
      if (aiSource) {
        status +=
          aiSource === "openai"
            ? " AI wrote the story description from your scenes."
            : " A short description was drafted from your scenes (set OPENAI_API_KEY for full AI).";
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
    if (storyId == null) return;
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
        lines.push(`## Scene ${full.scene_number}`, "", full.text, "");
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

  function updateClaim(i: number, patch: Partial<ClaimIn>) {
    setClaims((prev) =>
      prev.map((c, j) => (j === i ? { ...c, ...patch } : c)),
    );
  }

  async function onAddScene(e: React.FormEvent) {
    e.preventDefault();
    if (storyId == null) return;
    const trimmed = claims.map((c) => ({
      ...c,
      subject: c.subject.trim(),
      predicate: c.predicate.trim(),
      object: c.object.trim(),
    }));
    if (trimmed.some((c) => !c.subject || !c.predicate || !c.object)) {
      setError("Each claim needs subject, predicate, and object.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body = {
        scene_number: sceneNumber,
        text: sceneText.trim(),
        claims: trimmed,
      };
      if (editingSceneId != null) {
        await updateScene(storyId, editingSceneId, body);
      } else {
        await addScene(storyId, body);
      }
      const sceneList = (await loadScenes()) ?? [];
      if (editingSceneId != null) {
        await openScene(editingSceneId);
      } else {
        resetSceneEditor(sceneList);
      }
      await loadIssues();
      await loadStories();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  const sceneDisabled = storyId == null || busy || centerView !== "scenes";
  const isEditingScene = editingSceneId != null;
  const isCreatingStory = centerView === "story-form" && storyId == null;
  const isEditingStory = centerView === "story-form" && storyId != null;

  return (
    <div className="workspace-canvas flex min-h-screen flex-col">
      <div className="workspace-content flex min-h-screen flex-col">
      <header className="glass-panel flex h-14 shrink-0 items-center justify-between border-b border-border/60 px-4 lg:px-6">
        <div className="flex items-center gap-3">
          <div className="brand-mark flex size-8 items-center justify-center rounded-md text-sm font-bold">
            IS
          </div>
          <div>
            <p className="soft-heading text-sm font-semibold leading-none text-foreground">
              inferStories
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Continuity memory for fiction
            </p>
          </div>
        </div>
        {storyId != null ? (
          <Badge variant="default">Story #{storyId}</Badge>
        ) : (
          <Badge variant="outline">No story loaded</Badge>
        )}
      </header>

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

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {/* Left — stories & scene navigation */}
        <aside className="flex w-full shrink-0 flex-col border-b border-sidebar-border bg-sidebar text-xs shadow-[0_18px_55px_rgba(0,0,0,0.06)] backdrop-blur-xl lg:w-80 lg:border-b-0 lg:border-r">
          <div className="flex-1 space-y-5 overflow-y-auto p-3 lg:p-4">
            <Panel
              compact
              title="Your stories"
              description="Open a story, import a file, or start fresh."
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
                      {importDraft.manuscript.scenes.length} scene
                      {importDraft.manuscript.scenes.length === 1 ? "" : "s"}
                    </p>
                  </div>

                  <fieldset className="space-y-2">
                    <legend className="text-sm font-medium text-foreground">
                      Add to
                    </legend>
                    <label className="flex cursor-pointer items-center gap-2 text-sm">
                      <input
                        type="radio"
                        name="importTarget"
                        className="accent-primary"
                        checked={importTarget === "new"}
                        onChange={() => {
                          setImportTarget("new");
                          setImportExistingStoryId(null);
                        }}
                        disabled={busy}
                      />
                      <span>New story</span>
                    </label>
                    <label className="flex cursor-pointer items-center gap-2 text-sm">
                      <input
                        type="radio"
                        name="importTarget"
                        className="accent-primary"
                        checked={importTarget === "existing"}
                        onChange={() => {
                          setImportTarget("existing");
                          if (importExistingStoryId == null && stories.length > 0) {
                            setImportExistingStoryId(stories[0].id);
                          }
                        }}
                        disabled={busy || stories.length === 0}
                      />
                      <span>Existing story</span>
                    </label>
                  </fieldset>

                  {importTarget === "new" ? (
                    <>
                      <label className="flex flex-col gap-1.5">
                        <FieldLabel>Story name</FieldLabel>
                        <Input
                          required
                          value={importStoryTitle}
                          onChange={(e) => setImportStoryTitle(e.target.value)}
                          disabled={busy}
                          placeholder="Name for this manuscript"
                        />
                      </label>
                      <label className="flex flex-col gap-1.5">
                        <FieldLabel>Description (optional)</FieldLabel>
                        <Textarea
                          value={importStoryDescription}
                          onChange={(e) =>
                            setImportStoryDescription(e.target.value)
                          }
                          disabled={busy}
                          placeholder="Leave blank to auto-generate from scenes after import"
                          className="min-h-[64px]"
                        />
                      </label>
                    </>
                  ) : (
                    <label className="flex flex-col gap-1.5">
                      <FieldLabel>Choose story</FieldLabel>
                      <select
                        required
                        value={importExistingStoryId ?? ""}
                        onChange={(e) =>
                          setImportExistingStoryId(Number(e.target.value))
                        }
                        disabled={busy}
                        className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30"
                      >
                        <option value="" disabled>
                          Select a story…
                        </option>
                        {stories.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.title} ({s.scene_count} scenes)
                          </option>
                        ))}
                      </select>
                    </label>
                  )}

                  <div className="space-y-2">
                    <FieldLabel>Chapter / scene names</FieldLabel>
                    <ul className="max-h-48 space-y-2 overflow-y-auto">
                      {importDraft.manuscript.scenes.map((sc, i) => (
                        <li
                          key={sc.scene_number}
                          className="rounded-md border border-border bg-muted/20 p-2"
                        >
                          <span className="text-xs font-medium text-muted-foreground">
                            Scene {sc.scene_number}
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
                        "Import scenes"
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
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="w-full"
                    onClick={() => {
                      if (centerView === "story-form" && storyId == null) {
                        setCenterView("empty");
                      } else {
                        startNewStory();
                      }
                    }}
                    disabled={busy}
                  >
                    {centerView === "story-form" && storyId == null
                      ? "Cancel"
                      : "+ New story"}
                  </Button>
                </div>
              )}

              <p className="mb-3 text-xs leading-5 text-muted-foreground">
                <span className="font-medium text-foreground">
                  .docx, .txt, or .md
                </span>{" "}
                from your computer. Word headings become scene breaks; or use{" "}
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

              {storiesLoading ? (
                <p className="text-xs text-muted-foreground">Loading stories…</p>
              ) : stories.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No stories yet. Click &ldquo;New story&rdquo; to begin.
                </p>
              ) : (
                <ul className="space-y-1">
                  {stories.map((s) => (
                    <li key={s.id}>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void openStory(s.id)}
                        className={cn(
                          "w-full rounded-md border px-2.5 py-2 text-left transition-colors",
                          storyId === s.id
                            ? "border-primary/40 bg-primary/10 shadow-sm"
                            : "border-transparent bg-card hover:border-sidebar-border",
                        )}
                      >
                        <p className="text-xs font-semibold leading-snug text-foreground">
                          {s.title}
                        </p>
                        <p className="mt-0.5 text-[11px] text-muted-foreground">
                          {s.scene_count} scene{s.scene_count === 1 ? "" : "s"}
                        </p>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            {storyId != null ? (
              <Panel
                compact
                title="Scenes & chapters"
                description="Select a scene to edit, or write a new one."
              >
                <Button
                  type="button"
                  variant={editingSceneId == null ? "default" : "outline"}
                  size="sm"
                  className="mb-3 w-full"
                  disabled={busy}
                  onClick={() => resetSceneEditor(scenes)}
                >
                  + Write new scene
                </Button>
                {scenesLoading ? (
                  <p className="text-sm text-muted-foreground">Loading scenes…</p>
                ) : scenes.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No scenes yet — add your first in the editor.
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
                              Scene {sc.scene_number}
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
            ) : null}
          </div>
        </aside>

        {/* Center — story setup or scene editor */}
      <main className="min-h-[320px] min-w-0 flex-1 overflow-y-auto bg-background/40">
          <div className="mx-auto max-w-3xl p-4 lg:p-6">
            {centerView === "story-form" ? (
              <Panel
                title={isCreatingStory ? "New story" : "Story details"}
                description={
                  isCreatingStory
                    ? "Name your manuscript, then save to start adding scenes."
                    : "Update the name and synopsis, then save to return to scenes."
                }
              >
                <form
                  onSubmit={(e) =>
                    void (isCreatingStory
                      ? onCreateStory(e)
                      : onSaveStoryDetails(e))
                  }
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
                      placeholder={
                        isCreatingStory
                          ? "Optional synopsis"
                          : "Synopsis, genre notes, or story bible summary"
                      }
                      className="min-h-[120px] leading-relaxed"
                    />
                  </label>
                  {isEditingStory ? (
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
                          Add at least one scene to generate a description.
                        </p>
                      ) : null}
                    </>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    <Button type="submit" variant="cta" disabled={busy}>
                      {busy ? (
                        <>
                          <Spinner />{" "}
                          {isCreatingStory ? "Creating…" : "Saving…"}
                        </>
                      ) : isCreatingStory ? (
                        "Save & start writing scenes"
                      ) : (
                        "Save story details"
                      )}
                    </Button>
                    {isEditingStory ? (
                      <Button
                        type="button"
                        variant="outline"
                        disabled={busy}
                        onClick={() => setCenterView("scenes")}
                      >
                        Cancel
                      </Button>
                    ) : null}
                  </div>
                </form>
              </Panel>
            ) : centerView === "empty" ? (
              <div className="rounded-lg border border-dashed border-border bg-muted/40 px-6 py-16 text-center">
                <p className="text-sm font-medium text-foreground">
                  Select or create a story
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Pick a story from the left, import a file, or click
                  &ldquo;New story&rdquo;.
                </p>
              </div>
            ) : (
              <Panel
                title={isEditingScene ? `Editing scene ${sceneNumber}` : "New scene"}
                description={
                  isEditingScene
                    ? "Update prose and claims, then save. Validation runs on save."
                    : "Write prose and attach structured claims. Validation runs when you submit."
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
                  <div className="grid gap-4 sm:grid-cols-[120px_1fr]">
                    <label className="flex flex-col gap-1.5">
                      <FieldLabel>Scene #</FieldLabel>
                      <Input
                        type="number"
                        required
                        min={1}
                        value={sceneNumber}
                        onChange={(e) =>
                          setSceneNumber(Number(e.target.value))
                        }
                        disabled={sceneDisabled}
                        className="w-full sm:w-24"
                      />
                    </label>
                    <label className="flex flex-col gap-1.5 sm:col-span-1">
                      <FieldLabel>Scene text</FieldLabel>
                      <Textarea
                        required
                        value={sceneText}
                        onChange={(e) => setSceneText(e.target.value)}
                        disabled={sceneDisabled}
                        placeholder="What happens in this scene?"
                        className={cn(
                          "min-h-[160px] leading-relaxed",
                          "bg-[#0f172a]/92 text-slate-50 placeholder:text-slate-300",
                          "border-white/10 focus-visible:ring-2 focus-visible:ring-sky-200/30",
                        )}
                      />
                    </label>
                  </div>

                  <div>
                    <div className="mb-3 flex items-center justify-between">
                      <FieldLabel>Claims</FieldLabel>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={sceneDisabled}
                        onClick={() => setClaims((c) => [...c, emptyClaim()])}
                      >
                        Add claim
                      </Button>
                    </div>
                    <div className="space-y-3">
                      {claims.map((c, i) => (
                        <div
                          key={i}
                          className="rounded-md border border-border bg-muted/30 p-3"
                        >
                          <div className="grid gap-2 sm:grid-cols-3">
                            <label className="flex flex-col gap-1">
                              <span className="text-xs text-muted-foreground">
                                Subject
                              </span>
                              <Input
                                value={c.subject}
                                onChange={(e) =>
                                  updateClaim(i, { subject: e.target.value })
                                }
                                disabled={sceneDisabled}
                                placeholder="Nahira"
                              />
                            </label>
                            <label className="flex flex-col gap-1">
                              <span className="text-xs text-muted-foreground">
                                Predicate
                              </span>
                              <Input
                                value={c.predicate}
                                onChange={(e) =>
                                  updateClaim(i, { predicate: e.target.value })
                                }
                                disabled={sceneDisabled}
                                placeholder="trusts"
                              />
                            </label>
                            <label className="flex flex-col gap-1">
                              <span className="text-xs text-muted-foreground">
                                Object
                              </span>
                              <Input
                                value={c.object}
                                onChange={(e) =>
                                  updateClaim(i, { object: e.target.value })
                                }
                                disabled={sceneDisabled}
                                placeholder="Ashan"
                              />
                            </label>
                          </div>
                          <label className="mt-3 flex cursor-pointer items-center gap-2 text-sm">
                            <input
                              type="checkbox"
                              className="size-4 rounded border-input accent-primary"
                              checked={c.is_major_plotline}
                              onChange={(e) =>
                                updateClaim(i, {
                                  is_major_plotline: e.target.checked,
                                })
                              }
                              disabled={sceneDisabled}
                            />
                            <span className="text-muted-foreground">
                              Major plotline
                            </span>
                          </label>
                          {claims.length > 1 ? (
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="mt-2 text-destructive hover:text-destructive"
                              disabled={sceneDisabled}
                              onClick={() =>
                                setClaims((prev) =>
                                  prev.filter((_, j) => j !== i),
                                )
                              }
                            >
                              Remove claim
                            </Button>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>

                  <Button
                    type="submit"
                    variant="cta"
                    disabled={sceneDisabled}
                    className="w-full sm:w-auto"
                  >
                    {busy ? (
                      <>
                        <Spinner /> Submitting scene…
                      </>
                    ) : (
                      isEditingScene ? "Save changes" : "Submit scene"
                    )}
                  </Button>
                </form>
              </Panel>
            )}
          </div>
        </main>

        {/* Right — validation issues */}
        <aside className="flex w-full shrink-0 flex-col border-t border-border bg-card/60 shadow-[0_18px_55px_rgba(0,0,0,0.06)] backdrop-blur-xl lg:w-80 lg:border-l lg:border-l-border lg:border-t-0">
          <div className="flex items-center justify-between border-b border-border bg-secondary/40 px-4 py-3">
            <div>
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
              disabled={storyId == null || busy}
              onClick={() => void loadIssues()}
            >
              Refresh
            </Button>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {storyId == null ? (
              <p className="text-sm text-muted-foreground">
                Issues appear here after you create a story and add scenes.
              </p>
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
                  Contradictions show up when a new scene conflicts with earlier
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
                        Scene {iss.scene_number}
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
      </div>
    </div>
  );
}
