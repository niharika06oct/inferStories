import { authClient } from "./auth-client";

const TOKEN_KEY = "infer_auth_session_token";

export function setAuthToken(token: string): void {
  if (typeof window !== "undefined") {
    sessionStorage.setItem(TOKEN_KEY, token);
  }
}

export function clearAuthToken(): void {
  if (typeof window !== "undefined") {
    sessionStorage.removeItem(TOKEN_KEY);
  }
}

export async function getAuthToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;

  const stored = sessionStorage.getItem(TOKEN_KEY);
  if (stored) return stored;

  const { data } = await authClient.getSession();
  const session = data?.session as { token?: string } | undefined;
  const token = session?.token;
  if (token) {
    sessionStorage.setItem(TOKEN_KEY, token);
    return token;
  }
  return null;
}

export async function authHeaders(
  extra?: HeadersInit,
): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const token = await getAuthToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (extra) {
    const h = new Headers(extra);
    h.forEach((v, k) => {
      headers[k] = v;
    });
  }
  return headers;
}
