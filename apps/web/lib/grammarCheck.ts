export type WritingIssue = {
  message: string;
  shortMessage: string;
  offset: number;
  length: number;
  /** Substring that was flagged when the issue was created. */
  matchedText: string;
  replacements: string[];
  type: string;
};

type LanguageToolMatch = {
  message: string;
  shortMessage?: string;
  offset: number;
  length: number;
  replacements?: { value: string }[];
  rule?: { issueType?: string };
};

export async function checkWriting(text: string): Promise<WritingIssue[]> {
  if (text.trim().length < 2) return [];

  const res = await fetch("/api/writing/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || "Grammar check failed");
  }
  const data = (await res.json()) as { matches?: LanguageToolMatch[] };
  return (data.matches ?? []).map((m) => ({
    message: m.message,
    shortMessage: m.shortMessage ?? m.message,
    offset: m.offset,
    length: m.length,
    matchedText: text.slice(m.offset, m.offset + m.length),
    replacements: (m.replacements ?? []).map((r) => r.value).slice(0, 5),
    type: m.rule?.issueType ?? "issue",
  }));
}

export function excerptAround(
  text: string,
  offset: number,
  length: number,
  context = 24,
): string {
  const start = Math.max(0, offset - context);
  const end = Math.min(text.length, offset + length + context);
  const slice = text.slice(start, end);
  const mark = text.slice(offset, offset + length);
  if (!mark) return slice;
  const idx = slice.indexOf(mark);
  if (idx < 0) return `…${slice}…`;
  return `…${slice.slice(0, idx)}【${mark}】${slice.slice(idx + mark.length)}…`;
}
