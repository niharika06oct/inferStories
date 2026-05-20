"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { UserAccountMenuGate } from "../../../components/UserAccountMenu";
import {
  Alert,
  Button,
  FieldLabel,
  Input,
  Panel,
  Spinner,
  Textarea,
} from "../../../components/ui";
import { createStory } from "../../../lib/api";

function formatErr(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "Something went wrong";
}

export default function NewStoryPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const story = await createStory({
        title: title.trim(),
        description: description.trim() || undefined,
      });
      router.push(`/stories/${story.id}`);
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="workspace-canvas flex min-h-screen flex-col">
      <div className="workspace-content flex min-h-screen flex-col">
        <header className="glass-panel flex h-14 shrink-0 items-center justify-between border-b border-border/60 px-4 lg:px-6">
          <Link
            href="/library"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            ← Library
          </Link>
          <UserAccountMenuGate />
        </header>

        <main className="mx-auto w-full max-w-xl flex-1 p-4 lg:p-8">
          {error ? (
            <div className="mb-4">
              <Alert title="Could not create story">
                <p>{error}</p>
              </Alert>
            </div>
          ) : null}

          <Panel
            title="New story"
            description="Name your manuscript, then continue to chapters and continuity."
          >
            <form
              onSubmit={(e) => void onSubmit(e)}
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
                  autoFocus
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <FieldLabel>Description (optional)</FieldLabel>
                <Textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  disabled={busy}
                  placeholder="Synopsis, genre notes, or story bible summary"
                  className="min-h-[120px] leading-relaxed"
                />
              </label>
              <div className="flex flex-wrap gap-2">
                <Button type="submit" variant="cta" disabled={busy}>
                  {busy ? (
                    <>
                      <Spinner /> Creating…
                    </>
                  ) : (
                    "Create & open story"
                  )}
                </Button>
                <Link href="/">
                  <Button type="button" variant="outline" disabled={busy}>
                    Cancel
                  </Button>
                </Link>
              </div>
            </form>
          </Panel>
        </main>
      </div>
    </div>
  );
}
