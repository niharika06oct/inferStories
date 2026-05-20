"use client";

import { AuthGate } from "./AuthGate";

export function AppShell({ children }: { children: React.ReactNode }) {
  return <AuthGate>{children}</AuthGate>;
}
