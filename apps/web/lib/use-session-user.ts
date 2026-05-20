"use client";

import { useMemo } from "react";
import { authClient } from "./auth-client";
import { clearAuthToken } from "./auth-token";
import type { SessionUser } from "./session-user";

function mapSessionUser(
  user: { name?: string; email?: string } | null | undefined,
): SessionUser | null {
  if (!user?.email) return null;
  return {
    name: user.name?.trim() || user.email.split("@")[0] || "Writer",
    email: user.email,
  };
}

/** Reactive session — updates immediately after sign-in / sign-out. */
export function useSessionUser() {
  const { data, isPending } = authClient.useSession();

  const user = useMemo(() => mapSessionUser(data?.user), [data?.user]);
  const signedIn = Boolean(data?.session ?? user);

  return {
    user,
    signedIn,
    isPending,
  };
}

export async function signOutUser(): Promise<void> {
  try {
    await authClient.signOut();
  } finally {
    clearAuthToken();
  }
}
