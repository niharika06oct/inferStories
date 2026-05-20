"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CURRENT_ACCOUNT_FEATURES } from "../lib/account-features";
import {
  firstNameInitial,
  type SessionUser,
} from "../lib/session-user";
import { authClient } from "../lib/auth-client";
import { signOutUser, useSessionUser } from "../lib/use-session-user";
import { cn } from "./ui";

type UserAccountMenuProps = {
  user: SessionUser;
  className?: string;
};

type Anchor = { top: number; right: number };

function AccountMenuCard({
  user,
  anchor,
  onClose,
  onSignOut,
}: {
  user: SessionUser;
  anchor: Anchor;
  onClose: () => void;
  onSignOut: () => Promise<void>;
}) {
  const [signingOut, setSigningOut] = useState(false);
  const initial = firstNameInitial(user.name);

  async function handleSignOut() {
    setSigningOut(true);
    await onSignOut();
  }

  const maxHeight = `min(26rem, calc(100vh - ${anchor.top}px - 1rem))`;

  return (
    <div className="fixed inset-0 z-[200]" role="presentation">
      <button
        type="button"
        className="absolute inset-0 cursor-default bg-transparent"
        aria-label="Close account menu"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="account-panel-title"
        className="account-panel glass-panel absolute flex w-[min(19rem,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-[var(--radius-card)] border border-border/70 shadow-lg"
        style={{
          top: anchor.top,
          right: anchor.right,
          maxHeight,
        }}
      >
        <div className="flex items-start gap-3 border-b border-border/60 p-4">
          <div
            className="flex size-11 shrink-0 items-center justify-center rounded-full border border-border/80 bg-muted/50 text-base font-semibold text-foreground"
            aria-hidden
          >
            {initial}
          </div>
          <div className="min-w-0 flex-1 pt-0.5">
            <h2
              id="account-panel-title"
              className="soft-heading truncate text-base font-semibold text-foreground"
            >
              {user.name}
            </h2>
            {user.email ? (
              <p className="mt-0.5 truncate text-xs text-muted-foreground">{user.email}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-1.5 py-0.5 text-lg leading-none text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="overflow-y-auto px-4 py-3" style={{ maxHeight: `calc(${maxHeight} - 7.5rem)` }}>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Current features
          </p>
          <ul className="mt-2 space-y-2">
            {CURRENT_ACCOUNT_FEATURES.map((feature) => (
              <li
                key={feature}
                className="flex gap-2 text-sm leading-snug text-foreground/90"
              >
                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary/70" />
                <span>{feature}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="border-t border-border/60 p-2">
          <button
            type="button"
            disabled={signingOut}
            onClick={() => void handleSignOut()}
            className="w-full rounded-md px-3 py-2 text-left text-sm text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground disabled:opacity-50"
          >
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function UserAccountMenu({ user, className }: UserAccountMenuProps) {
  const router = useRouter();
  const { refetch } = authClient.useSession();
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [anchor, setAnchor] = useState<Anchor>({ top: 56, right: 16 });
  const triggerRef = useRef<HTMLButtonElement>(null);

  const updateAnchor = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    setAnchor({
      top: rect.bottom + 8,
      right: Math.max(12, window.innerWidth - rect.right),
    });
  }, []);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) return;
    updateAnchor();
    const onReposition = () => updateAnchor();
    window.addEventListener("resize", onReposition);
    window.addEventListener("scroll", onReposition, true);
    return () => {
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("scroll", onReposition, true);
    };
  }, [open, updateAnchor]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const panel =
    open && mounted
      ? createPortal(
          <AccountMenuCard
            user={user}
            anchor={anchor}
            onClose={() => setOpen(false)}
            onSignOut={async () => {
              await signOutUser();
              await refetch();
              setOpen(false);
              router.replace("/");
            }}
          />,
          document.body,
        )
      : null;

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => {
          updateAnchor();
          setOpen((v) => !v);
        }}
        className={cn(
          "flex size-9 shrink-0 items-center justify-center rounded-full",
          "border border-border/80 bg-card/80 text-sm font-semibold text-foreground shadow-sm",
          "backdrop-blur-sm transition-colors hover:bg-muted/60",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          open && "bg-muted/70 ring-1 ring-border/80",
          className,
        )}
        aria-label="Open account menu"
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        {firstNameInitial(user.name)}
      </button>
      {panel}
    </>
  );
}

/** Fetches session once; renders avatar + panel when signed in. */
export function UserAccountMenuGate({ className }: { className?: string }) {
  const { user } = useSessionUser();

  if (!user) return null;
  return <UserAccountMenu user={user} className={className} />;
}
