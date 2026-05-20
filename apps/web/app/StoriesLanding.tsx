"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { SiteHeader } from "../components/SiteHeader";
import { Button, Panel, Spinner } from "../components/ui";
import { fetchStories, type StoryListOut } from "../lib/api";

function formatErr(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "Something went wrong";
}

export default function StoriesLanding() {
  const [stories, setStories] = useState<StoryListOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setStories(await fetchStories());
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="workspace-canvas flex min-h-screen flex-col">
      <div className="workspace-content flex min-h-screen flex-col">
        <SiteHeader active="library" />

        <main className="mx-auto w-full max-w-2xl flex-1 p-4 lg:p-8">
          <Panel
            title="Your stories"
            description="Open a manuscript to write chapters and check continuity, or start a new one."
          >
            <div className="mb-5 flex flex-wrap gap-2">
              <Link href="/stories/new">
                <Button type="button" variant="cta">
                  + New story
                </Button>
              </Link>
            </div>

            {error ? (
              <p className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-foreground">
                {error}
              </p>
            ) : null}

            {loading ? (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Spinner /> Loading stories…
              </p>
            ) : stories.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border bg-muted/30 px-6 py-12 text-center">
                <p className="text-sm font-medium text-foreground">No stories yet</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Create your first story to add chapters, claims, and continuity checks.
                </p>
                <Link href="/stories/new" className="mt-4 inline-block">
                  <Button type="button" variant="cta">
                    Create a story
                  </Button>
                </Link>
              </div>
            ) : (
              <ul className="space-y-2">
                {stories.map((s) => (
                  <li key={s.id}>
                    <Link
                      href={`/stories/${s.id}`}
                      className="block rounded-lg border border-border bg-card px-4 py-3 shadow-sm transition-colors hover:border-primary/40 hover:bg-primary/5"
                    >
                      <p className="font-semibold text-foreground">{s.title}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {s.scene_count} chapter{s.scene_count === 1 ? "" : "s"}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </main>
      </div>
    </div>
  );
}
