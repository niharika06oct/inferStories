/**
 * Proxy /api/auth/* to auth-service.
 *
 * - Strips `X-Forwarded-Host` so the tenant guard does not block local dev.
 * - Rewrites `Origin` to the auth-service public URL: better-auth rejects
 *   server-side fetches when Origin is the Next app (e.g. localhost:3000) but
 *   the request is forwarded to 127.0.0.1:4000.
 */

const authTarget =
  process.env.AUTH_PROXY_TARGET?.replace(/\/$/, "") ?? "http://127.0.0.1:4000";

/** Must match auth-service BETTER_AUTH_URL / ALLOWED_HOSTS for CSRF checks. */
const authOrigin =
  process.env.AUTH_PROXY_ORIGIN?.replace(/\/$/, "") ?? "http://localhost:4000";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
  "origin",
  "referer",
  "x-forwarded-host",
  "x-forwarded-proto",
  "x-forwarded-for",
  "sec-fetch-site",
  "sec-fetch-mode",
  "sec-fetch-dest",
  "sec-fetch-user",
]);

async function proxyAuth(req: Request, path: string[]): Promise<Response> {
  const incoming = new URL(req.url);
  const target = new URL(
    `${authTarget}/api/auth/${path.join("/")}`,
  );
  target.search = incoming.search;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });
  headers.set("Origin", authOrigin);

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: "manual",
  };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
  }

  return fetch(target, init);
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(req: Request, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyAuth(req, path);
}

export async function POST(req: Request, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyAuth(req, path);
}

export async function PUT(req: Request, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyAuth(req, path);
}

export async function PATCH(req: Request, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyAuth(req, path);
}

export async function DELETE(req: Request, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyAuth(req, path);
}
