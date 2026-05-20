import { authClient } from "./auth-client";
import { getAuthToken } from "./auth-token";

export type SessionUser = {
  name: string;
  email: string;
};

export function firstNameInitial(name: string): string {
  const first = name.trim().split(/\s+/)[0] ?? "";
  const ch = first[0] ?? name.trim()[0] ?? "?";
  return ch.toUpperCase();
}

export async function fetchSessionUser(): Promise<SessionUser | null> {
  const token = await getAuthToken();
  const { data } = await authClient.getSession();
  if (!token && !data?.session) return null;

  const user = data?.user as { name?: string; email?: string } | undefined;
  if (!user?.email) {
    if (token) {
      return { name: "Writer", email: "" };
    }
    return null;
  }

  return {
    name: user.name?.trim() || user.email.split("@")[0] || "Writer",
    email: user.email,
  };
}
