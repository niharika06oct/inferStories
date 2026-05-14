import type { NextConfig } from "next";

/**
 * Dev proxy target — avoids browser CORS when the UI calls `/api/upstream/...`.
 * Override with API_PROXY_TARGET if port 8000 is taken (e.g. Docker publishing 8000).
 */
const apiProxyTarget =
  process.env.API_PROXY_TARGET?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/upstream/:path*",
        destination: `${apiProxyTarget}/:path*`,
      },
    ];
  },
};

export default nextConfig;
