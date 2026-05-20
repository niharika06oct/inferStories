"use client";

import Link from "next/link";
import { useSessionUser } from "../lib/use-session-user";
import { UserAccountMenu } from "./UserAccountMenu";
import { Badge } from "./ui";

type SiteHeaderProps = {
  active?: "home" | "library" | "login";
  showMarketingNav?: boolean;
  workspaceHref?: string;
};

export function SiteHeader({
  active,
  showMarketingNav = false,
  workspaceHref = "/login",
}: SiteHeaderProps) {
  const { user, signedIn, isPending } = useSessionUser();
  const checked = !isPending;

  return (
    <header className="glass-panel flex h-14 shrink-0 items-center justify-between border-b border-border/60 px-4 lg:px-6">
      <Link href="/" className="flex items-center gap-3">
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
      </Link>

      {showMarketingNav ? (
        <nav className="hidden items-center gap-6 md:flex">
          <a
            href="#pain"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            The problem
          </a>
          <a
            href="#how"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            How it works
          </a>
          <a
            href="#features"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Features
          </a>
        </nav>
      ) : null}

      <div className="flex items-center gap-3">
        {active === "library" ? (
          <>
            <Link
              href="/"
              className="text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              Home
            </Link>
            <Badge variant="outline">Your library</Badge>
          </>
        ) : active === "login" && !signedIn ? (
          <Link
            href="/"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            ← Home
          </Link>
        ) : null}

        {signedIn && user ? <UserAccountMenu user={user} /> : null}

        {checked && !signedIn && active !== "library" ? (
          <Link
            href="/login"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Log in
          </Link>
        ) : null}

        {active !== "library" && active !== "login" ? (
          <Link
            href={workspaceHref}
            className="inline-flex h-9 items-center justify-center rounded-md bg-cta px-3 text-sm font-medium text-cta-foreground shadow-sm transition-opacity hover:opacity-95"
          >
            Start writing
          </Link>
        ) : null}

        {signedIn && active === "login" ? (
          <Link
            href="/library"
            className="inline-flex h-9 items-center justify-center rounded-md bg-cta px-3 text-sm font-medium text-cta-foreground shadow-sm transition-opacity hover:opacity-95"
          >
            Open library
          </Link>
        ) : null}
      </div>
    </header>
  );
}
