"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { authClient } from "../lib/auth-client";
import { getAuthToken } from "../lib/auth-token";
import { isPublicPath } from "../lib/public-routes";
import { Spinner } from "./ui";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const isPublic = isPublicPath(pathname);

  useEffect(() => {
    if (isPublic) {
      setReady(true);
      return;
    }

    let cancelled = false;

    async function check() {
      const token = await getAuthToken();
      const { data } = await authClient.getSession();
      if (cancelled) return;

      if (!token && !data?.session) {
        const next =
          pathname && !isPublicPath(pathname)
            ? `?next=${encodeURIComponent(pathname)}`
            : "";
        router.replace(`/login${next}`);
        return;
      }
      setReady(true);
    }

    void check();
    return () => {
      cancelled = true;
    };
  }, [isPublic, pathname, router]);

  if (isPublic) {
    return <>{children}</>;
  }

  if (!ready) {
    return (
      <div className="workspace-canvas flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return <>{children}</>;
}
