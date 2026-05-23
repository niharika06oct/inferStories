/**
 * Proxy spelling/grammar checks to LanguageTool (free public API).
 * No API key required; rate-limited — use the manual "Review writing" action.
 */
export async function POST(req: Request) {
  let text: string;
  try {
    const body = (await req.json()) as { text?: string };
    text = typeof body.text === "string" ? body.text : "";
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (text.length > 20_000) {
    return Response.json(
      { error: "Text too long for grammar check (max 20,000 characters)" },
      { status: 400 },
    );
  }

  const params = new URLSearchParams({
    text,
    language: "en-US",
  });

  const upstream = await fetch("https://api.languagetool.org/v2/check", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: params,
    signal: AbortSignal.timeout(25_000),
  });

  if (!upstream.ok) {
    const detail = await upstream.text();
    return Response.json(
      { error: "Grammar service unavailable", detail: detail.slice(0, 200) },
      { status: 502 },
    );
  }

  const data = await upstream.json();
  return Response.json(data);
}
