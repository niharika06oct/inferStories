import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      // /api/auth/* → app/api/auth/[...path]/route.ts
      // /api/upstream/* → app/api/upstream/[...path]/route.ts (long-timeout proxy; do not rewrite here)
    ];
  },
};

export default nextConfig;
