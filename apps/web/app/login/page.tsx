"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";
import { SiteHeader } from "../../components/SiteHeader";
import { Button, Panel } from "../../components/ui";
import { authClient } from "../../lib/auth-client";
import { setAuthToken } from "../../lib/auth-token";

type Mode = "signin" | "signup";

function formatAuthError(err: unknown): string {
  if (err && typeof err === "object") {
    const e = err as { message?: string; statusText?: string; code?: string };
    if (e.message) return e.message;
    if (e.statusText) return e.statusText;
    if (e.code) return e.code;
  }
  return "Authentication failed. Check your email and password.";
}

function safeNextPath(raw: string | null): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return "/library";
  if (raw.startsWith("/login") || raw.startsWith("/api")) return "/library";
  return raw;
}

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const afterLogin = safeNextPath(searchParams.get("next"));
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === "signup") {
        const { error: signUpErr } = await authClient.signUp.email({
          email,
          password,
          name: name.trim() || email.split("@")[0] || "Writer",
        });
        if (signUpErr) throw signUpErr;
        const { data, error: signInErr } = await authClient.signIn.email({
          email,
          password,
        });
        if (signInErr) throw signInErr;
        if (data?.token) setAuthToken(data.token);
      } else {
        const { data, error: signInErr } = await authClient.signIn.email({
          email,
          password,
        });
        if (signInErr) throw signInErr;
        if (data?.token) setAuthToken(data.token);
      }
      router.replace(afterLogin);
      router.refresh();
    } catch (err) {
      setError(formatAuthError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="workspace-canvas flex min-h-screen flex-col">
      <div className="workspace-content flex min-h-screen flex-col">
        <SiteHeader active="login" workspaceHref="/library" />

        <main className="mx-auto flex w-full max-w-lg flex-1 flex-col justify-center p-4 py-10 lg:p-8">
          <div className="mb-6 text-center">
            <p className="text-xs font-medium uppercase tracking-widest text-primary">
              Welcome back
            </p>
            <h1 className="soft-heading mt-2 text-2xl font-semibold text-foreground">
              Your story remembers everything
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Sign in to open your library, chapters, and continuity checks.
            </p>
          </div>

          <div className="glass-panel rounded-[var(--radius-card)] p-6 shadow-sm md:p-8">
            <Panel
              title={mode === "signin" ? "Sign in" : "Create account"}
              description="Phone and Google sign-in are coming later."
              compact
            >
              <form onSubmit={onSubmit} className="space-y-4">
                {mode === "signup" ? (
                  <label className="block text-sm">
                    <span className="mb-1 block text-muted-foreground">Name</span>
                    <input
                      type="text"
                      autoComplete="name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="flex h-9 w-full rounded-md border border-input bg-card/40 px-3 py-1 text-sm text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      placeholder="Your name"
                    />
                  </label>
                ) : null}

                <label className="block text-sm">
                  <span className="mb-1 block text-muted-foreground">Email</span>
                  <input
                    type="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="flex h-9 w-full rounded-md border border-input bg-card/40 px-3 py-1 text-sm text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    placeholder="you@example.com"
                  />
                </label>

                <label className="block text-sm">
                  <span className="mb-1 block text-muted-foreground">Password</span>
                  <input
                    type="password"
                    required
                    minLength={12}
                    autoComplete={
                      mode === "signup" ? "new-password" : "current-password"
                    }
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="flex h-9 w-full rounded-md border border-input bg-card/40 px-3 py-1 text-sm text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    placeholder="At least 12 characters"
                  />
                  <span className="mt-1 block text-xs text-muted-foreground">
                    Length, upper, lower, number, and symbol required.
                  </span>
                </label>

                {error ? (
                  <p
                    className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
                    role="alert"
                  >
                    {error}
                  </p>
                ) : null}

                <Button type="submit" disabled={loading} variant="cta" className="w-full">
                  {loading
                    ? "Please wait…"
                    : mode === "signin"
                      ? "Sign in"
                      : "Create account"}
                </Button>
              </form>

              <p className="mt-4 text-center text-sm text-muted-foreground">
                {mode === "signin" ? (
                  <>
                    New here?{" "}
                    <button
                      type="button"
                      className="font-medium text-primary hover:underline"
                      onClick={() => setMode("signup")}
                    >
                      Create an account
                    </button>
                  </>
                ) : (
                  <>
                    Already have an account?{" "}
                    <button
                      type="button"
                      className="font-medium text-primary hover:underline"
                      onClick={() => setMode("signin")}
                    >
                      Sign in
                    </button>
                  </>
                )}
              </p>
            </Panel>
          </div>

          <p className="mt-4 text-center text-xs text-muted-foreground">
            <Link href="/" className="hover:text-foreground hover:underline">
              ← Back to home
            </Link>
          </p>
        </main>
      </div>
    </div>
  );
}
