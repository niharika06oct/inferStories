"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  addScene,
  createStory,
  fetchValidationIssues,
  type ClaimIn,
  type ValidationIssueOut,
} from "../lib/api";

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

export default function StoryWorkspace() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [storyId, setStoryId] = useState<number | null>(null);

  const [sceneNumber, setSceneNumber] = useState(1);
  const [sceneText, setSceneText] = useState("");
  const [claims, setClaims] = useState<ClaimIn[]>([emptyClaim()]);

  const [issues, setIssues] = useState<ValidationIssueOut[]>([]);
  const [issuesLoadedAt, setIssuesLoadedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const errorBoxRef = useRef<HTMLDivElement>(null);

  const loadIssues = useCallback(async () => {
    if (storyId == null) return;
    setError(null);
    try {
      const data = await fetchValidationIssues(storyId);
      setIssues(data);
      setIssuesLoadedAt(new Date().toISOString());
    } catch (e) {
      setError(formatErr(e));
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
      setSceneNumber(1);
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
      await addScene(storyId, {
        scene_number: sceneNumber,
        text: sceneText.trim(),
        claims: trimmed,
      });
      setSceneNumber((n) => n + 1);
      setSceneText("");
      setClaims([emptyClaim()]);
      await loadIssues();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-10 px-4 py-10">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          inferStories
        </h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Create a story, add scenes with structured claims, and watch continuity
          issues appear (polls every 4s while a story is loaded).
        </p>
      </header>

      {error ? (
        <div
          ref={errorBoxRef}
          className="rounded-lg border border-red-300 bg-red-100 px-3 py-2 text-sm text-red-900 dark:border-red-800 dark:bg-red-950 dark:text-red-100"
          role="alert"
        >
          <p className="font-medium">Request failed</p>
          <p className="mt-1 whitespace-pre-wrap">{error}</p>
          <p className="mt-2 text-xs opacity-90">
            Check that the API is running (e.g.{" "}
            <code className="rounded bg-red-200/80 px-1 dark:bg-red-900">
              uvicorn app.main:app --port 8000
            </code>
            ). The UI calls the backend via the Next.js proxy at{" "}
            <code className="rounded bg-red-200/80 px-1 dark:bg-red-900">
              /api/upstream
            </code>
            .
          </p>
        </div>
      ) : null}

      <section className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
        <h2 className="text-lg font-medium text-zinc-900 dark:text-zinc-50">
          1. Story
        </h2>
        <form onSubmit={onCreateStory} className="mt-4 flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-zinc-600 dark:text-zinc-400">Title</span>
            <input
              required
              className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={storyId != null || busy}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-zinc-600 dark:text-zinc-400">
              Description (optional)
            </span>
            <textarea
              className="min-h-[72px] rounded-md border border-zinc-300 bg-white px-3 py-2 text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={storyId != null || busy}
            />
          </label>
          <button
            type="submit"
            disabled={storyId != null || busy}
            className="w-fit rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
          >
            {storyId != null
              ? `Story #${storyId} created`
              : busy
                ? "Creating…"
                : "Create story"}
          </button>
        </form>
      </section>

      <section className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
        <h2 className="text-lg font-medium text-zinc-900 dark:text-zinc-50">
          2. Scene + claims
        </h2>
        <form onSubmit={onAddScene} className="mt-4 flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-zinc-600 dark:text-zinc-400">
              Scene number
            </span>
            <input
              type="number"
              required
              min={1}
              className="w-32 rounded-md border border-zinc-300 bg-white px-3 py-2 text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
              value={sceneNumber}
              onChange={(e) => setSceneNumber(Number(e.target.value))}
              disabled={storyId == null || busy}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-zinc-600 dark:text-zinc-400">Scene text</span>
            <textarea
              required
              className="min-h-[100px] rounded-md border border-zinc-300 bg-white px-3 py-2 text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
              value={sceneText}
              onChange={(e) => setSceneText(e.target.value)}
              disabled={storyId == null || busy}
            />
          </label>

          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                Claims
              </span>
              <button
                type="button"
                className="text-sm text-zinc-600 underline dark:text-zinc-400"
                disabled={storyId == null || busy}
                onClick={() => setClaims((c) => [...c, emptyClaim()])}
              >
                Add claim row
              </button>
            </div>
            {claims.map((c, i) => (
              <div
                key={i}
                className="grid gap-2 rounded-lg border border-zinc-100 p-3 dark:border-zinc-800 sm:grid-cols-2 lg:grid-cols-4"
              >
                <input
                  placeholder="subject"
                  className="rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  value={c.subject}
                  onChange={(e) => updateClaim(i, { subject: e.target.value })}
                  disabled={storyId == null || busy}
                />
                <input
                  placeholder="predicate"
                  className="rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  value={c.predicate}
                  onChange={(e) => updateClaim(i, { predicate: e.target.value })}
                  disabled={storyId == null || busy}
                />
                <input
                  placeholder="object"
                  className="rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  value={c.object}
                  onChange={(e) => updateClaim(i, { object: e.target.value })}
                  disabled={storyId == null || busy}
                />
                <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
                  <input
                    type="checkbox"
                    checked={c.is_major_plotline}
                    onChange={(e) =>
                      updateClaim(i, { is_major_plotline: e.target.checked })
                    }
                    disabled={storyId == null || busy}
                  />
                  Major plotline
                </label>
                {claims.length > 1 ? (
                  <button
                    type="button"
                    className="text-left text-sm text-red-600 sm:col-span-2 lg:col-span-4"
                    disabled={storyId == null || busy}
                    onClick={() =>
                      setClaims((prev) => prev.filter((_, j) => j !== i))
                    }
                  >
                    Remove row
                  </button>
                ) : null}
              </div>
            ))}
          </div>

          <button
            type="submit"
            disabled={storyId == null || busy}
            className="w-fit rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
          >
            Submit scene
          </button>
        </form>
      </section>

      <section className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-medium text-zinc-900 dark:text-zinc-50">
            3. Validation issues
          </h2>
          <div className="flex items-center gap-2">
            {issuesLoadedAt ? (
              <span className="text-xs text-zinc-500">
                Last updated: {new Date(issuesLoadedAt).toLocaleString()}
              </span>
            ) : null}
            <button
              type="button"
              className="rounded border border-zinc-300 px-3 py-1 text-sm dark:border-zinc-600"
              disabled={storyId == null || busy}
              onClick={() => void loadIssues()}
            >
              Refresh now
            </button>
          </div>
        </div>
        {storyId == null ? (
          <p className="mt-3 text-sm text-zinc-500">
            Create a story to load issues.
          </p>
        ) : issues.length === 0 ? (
          <p className="mt-3 text-sm text-zinc-500">No issues recorded yet.</p>
        ) : (
          <ul className="mt-4 flex flex-col gap-3">
            {issues.map((iss) => (
              <li
                key={iss.id}
                className="rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-800 dark:bg-zinc-900"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={
                      iss.severity === "high"
                        ? "font-semibold text-red-700 dark:text-red-400"
                        : "font-medium text-amber-800 dark:text-amber-300"
                    }
                  >
                    {iss.severity}
                  </span>
                  <span className="text-zinc-500">
                    scene {iss.scene_number} · issue #{iss.id}
                  </span>
                </div>
                <p className="mt-1 text-zinc-800 dark:text-zinc-200">
                  {iss.message}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
