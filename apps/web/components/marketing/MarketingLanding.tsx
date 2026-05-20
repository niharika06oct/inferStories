"use client";

import Link from "next/link";
import { SiteHeader } from "../SiteHeader";
import { Button } from "../ui";
import { useSessionUser } from "../../lib/use-session-user";

export default function MarketingLanding() {
  const { signedIn } = useSessionUser();
  const workspaceHref = signedIn ? "/library" : "/login?next=/stories/new";

  return (
    <div className="workspace-canvas flex min-h-screen flex-col">
      <div className="workspace-content flex min-h-screen flex-col">
        <SiteHeader
          active="home"
          showMarketingNav
          workspaceHref={workspaceHref}
        />

        <main className="flex-1">
          <section className="site-section site-hero text-center">
            <p className="text-xs font-medium uppercase tracking-widest text-primary">
              Story intelligence for fiction writers
            </p>
            <h1 className="soft-heading mt-3 text-4xl font-semibold text-foreground md:text-5xl lg:text-6xl">
              Your story finally has memory.
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-muted-foreground md:text-lg">
              AI-powered continuity, character intelligence, and canon
              validation — so every relationship, promise, and scar stays
              remembered as your manuscript grows.
            </p>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
              <Link href={workspaceHref}>
                <Button type="button" variant="cta" className="h-10 px-6">
                  Start writing
                </Button>
              </Link>
              <a href="#how">
                <Button type="button" variant="outline" className="h-10 px-6">
                  See how it works
                </Button>
              </a>
            </div>
            <p className="mt-6 text-sm text-muted-foreground">
              Not another ghostwriter — a writing room that remembers your world.
            </p>
          </section>

          <section id="pain" className="site-section">
            <div className="site-section-head">
              <h2 className="soft-heading text-2xl font-semibold text-foreground md:text-3xl">
                Writers don&apos;t forget ideas. They forget details.
              </h2>
              <p className="mt-3 text-muted-foreground">
                Long-form fiction breaks quietly. inferStories catches what your
                brain cannot hold alone.
              </p>
            </div>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {[
                { bad: "Forgot a character detail", good: "Automatically remembered" },
                { bad: "Relationship inconsistencies", good: "Living character network" },
                { bad: "Timeline contradictions", good: "Continuously validated" },
                { bad: "Broken emotional arcs", good: "Arc-aware intelligence" },
                { bad: "Lost track of lore", good: "Instantly searchable" },
                { bad: "Canon breaks at publish", good: "Caught before readers do" },
              ].map((item) => (
                <div key={item.bad} className="glass-panel site-card rounded-[var(--radius-card)] p-5">
                  <p className="text-sm text-destructive/90">{item.bad}</p>
                  <p className="mt-2 text-sm font-medium text-foreground">{item.good}</p>
                </div>
              ))}
            </div>
          </section>

          <section id="how" className="site-section">
            <div className="glass-panel site-section-band mx-auto max-w-3xl rounded-[var(--radius-card)] p-8 md:p-10">
              <div className="site-section-head">
                <h2 className="soft-heading text-2xl font-semibold text-foreground">
                  From chapter to living memory
                </h2>
                <p className="mt-3 text-muted-foreground">
                  Paste a chapter. Watch your world become structured intelligence.
                </p>
              </div>
              <ol className="mt-8 space-y-6">
                {[
                  ["Import your chapter", "Paste prose or upload a manuscript."],
                  ["Track key facts", "Optional claims (relationships, plotlines) become continuity memory."],
                  ["Continuity checks", "Contradictions surface before readers see them."],
                  ["Canon stays intact", "Write the next chapter with confidence."],
                ].map(([title, body], i) => (
                  <li key={title} className="flex gap-4">
                    <span className="flex size-8 shrink-0 items-center justify-center rounded-full border border-border bg-card/50 text-sm font-semibold text-primary">
                      {i + 1}
                    </span>
                    <div>
                      <h3 className="font-semibold text-foreground">{title}</h3>
                      <p className="mt-1 text-sm text-muted-foreground">{body}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </section>

          <section id="features" className="site-section">
            <div className="site-section-head">
              <h2 className="soft-heading text-2xl font-semibold text-foreground md:text-3xl">
                Protect and understand your world
              </h2>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {[
                {
                  title: "Continuity memory",
                  tagline: "Never lose your world again.",
                  body: "Every detail persists across chapters and books.",
                },
                {
                  title: "Relationship intelligence",
                  tagline: "A living character network.",
                  body: "Love, rivalry, betrayal — tracked as you write.",
                },
                {
                  title: "Real-time validation",
                  tagline: "Catch contradictions before readers do.",
                  body: "Timeline and canon slips surface as you draft.",
                },
                {
                  title: "Story intelligence",
                  tagline: "Think like a showrunner.",
                  body: "Themes, arcs, and plotlines — searchable and coherent.",
                },
                {
                  title: "Character evolution",
                  tagline: "See change across chapters.",
                  body: "Growth, loyalties, and scars over time.",
                },
                {
                  title: "Reader mode",
                  tagline: "Explore any story's world.",
                  body: "Coming soon: lore maps for fans and communities.",
                  soon: true,
                },
              ].map((f) => (
                <article
                  key={f.title}
                  className="glass-panel site-card relative rounded-[var(--radius-card)] p-6"
                >
                  {f.soon ? (
                    <span className="absolute right-4 top-4 text-[10px] font-medium uppercase tracking-wide text-primary">
                      Soon
                    </span>
                  ) : null}
                  <h3 className="font-semibold text-foreground">{f.title}</h3>
                  <p className="mt-1 text-sm font-medium text-primary">{f.tagline}</p>
                  <p className="mt-2 text-sm text-muted-foreground">{f.body}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="site-section">
            <div className="glass-panel site-cta-band rounded-[var(--radius-card)] p-8 text-center md:p-12">
              <h2 className="soft-heading text-2xl font-semibold text-foreground md:text-3xl">
                Built for worlds too large to forget
              </h2>
              <p className="mx-auto mt-4 max-w-lg text-muted-foreground">
                Fantasy epics, series, and cinematic universes — if your story
                has memory problems, inferStories was built for you.
              </p>
              <Link href={workspaceHref} className="mt-8 inline-block">
                <Button type="button" variant="cta" className="h-10 px-6">
                  {signedIn ? "Open your library" : "Start writing"}
                </Button>
              </Link>
            </div>
          </section>

          <section className="site-section pb-16 text-center">
            <h2 className="soft-heading text-xl font-semibold text-foreground">
              Preserve meaning — not just words.
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              The writing room that remembers everything.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <Link href={workspaceHref}>
                <Button type="button" variant="cta">
                  Start writing
                </Button>
              </Link>
              <Link href="/login">
                <Button type="button" variant="ghost">
                  Log in
                </Button>
              </Link>
            </div>
          </section>
        </main>

        <footer className="glass-panel border-t border-border/60 px-4 py-6 text-center text-sm text-muted-foreground">
          inferStories — AI continuity and story intelligence for fiction writers.
        </footer>
      </div>
    </div>
  );
}

