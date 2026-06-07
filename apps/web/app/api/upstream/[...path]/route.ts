/**
 * Proxy /api/upstream/* → FastAPI with a long timeout.
 *
 * next.config rewrites use a dev proxy that can drop long chapter saves
 * (OpenAI extraction often takes 15–60s). This route handler uses fetch
 * with an explicit timeout so PATCH /scenes does not socket-hang-up.
 */

const apiTarget =
  process.env.API_PROXY_TARGET?.replace(/\/$/, "") ?? "http://127.0.0.1:8001";

/** Chapter save + OpenAI extraction can exceed 30s. */
const PROXY_TIMEOUT_MS = Number(process.env.API_PROXY_TIMEOUT_MS ?? "180000");

export const maxDuration = 300;

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
]);

async function proxyUpstream(req: Request, path: string[]): Promise<Response> {
  const incoming = new URL(req.url);
  const target = new URL(`${apiTarget}/${path.join("/")}`);
  target.search = incoming.search;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: "manual",
    signal: AbortSignal.timeout(PROXY_TIMEOUT_MS),
  };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
  }

  try {
    return await fetch(target, init);
  } catch (err) {
    const message =
      err instanceof Error && err.name === "TimeoutError"
        ? `FastAPI request timed out after ${PROXY_TIMEOUT_MS}ms (chapter extraction may still be running on the API).`
        : `Cannot reach FastAPI at ${apiTarget}: ${err instanceof Error ? err.message : String(err)}`;
    return new Response(JSON.stringify({ detail: message }), {
      status: 502,
      headers: { "Content-Type": "application/json" },
    });
  }
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(req: Request, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyUpstream(req, path);
}

export async function POST(req: Request, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyUpstream(req, path);
}

export async function PUT(req: Request, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyUpstream(req, path);
}

export async function PATCH(req: Request, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyUpstream(req, path);
}

export async function DELETE(req: Request, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyUpstream(req, path);
}
