export type ImportedScene = {
  scene_number: number;
  /** Chapter / scene label from headings, if detected */
  title?: string;
  text: string;
};

export type ImportedManuscript = {
  title: string;
  description: string;
  scenes: ImportedScene[];
};

/** Derive a readable title from a file name like `my-novel.md`. */
export function titleFromFileName(fileName: string): string {
  const base = fileName.replace(/\.(md|txt|markdown|docx)$/i, "").trim();
  if (!base) return "Imported story";
  return base.replace(/[-_]+/g, " ").replace(/\s+/g, " ").trim();
}

/**
 * Split plain-text / markdown into scenes.
 * Supports: `---` dividers, `##` headings, `Chapter N` lines, or long blank gaps.
 */
export function parseManuscriptText(
  fileName: string,
  content: string,
): ImportedManuscript {
  const normalized = content.replace(/\r\n/g, "\n").trim();
  const title = titleFromFileName(fileName);

  let parts: string[] = [];

  if (/\n---\n/.test(normalized)) {
    parts = normalized.split(/\n---\n/).map((s) => s.trim()).filter(Boolean);
  } else if (/^##\s+/m.test(normalized)) {
    parts = normalized.split(/(?=^##\s+)/m).map((s) => s.trim()).filter(Boolean);
  } else if (/^Chapter\s+\d+/im.test(normalized)) {
    parts = normalized
      .split(/(?=^Chapter\s+\d+)/im)
      .map((s) => s.trim())
      .filter(Boolean);
  } else if (/\n\n\n+/.test(normalized)) {
    const chunks = normalized
      .split(/\n\n\n+/)
      .map((s) => s.trim())
      .filter((s) => s.length >= 80);
    if (chunks.length > 1) parts = chunks;
  }

  if (parts.length === 0) {
    parts = [normalized];
  }

  const scenes = parts.map((block, index) => parseSceneBlock(block, index));

  return {
    title,
    description: `Imported from ${fileName}`,
    scenes,
  };
}

function parseSceneBlock(block: string, index: number): ImportedScene {
  const heading = block.match(/^##\s+(.+?)(?:\n|$)/m);
  const chapter = block.match(/^(Chapter\s+\d+[^\n]*)/im);
  const title = heading?.[1]?.trim() ?? chapter?.[1]?.trim();
  return {
    scene_number: index + 1,
    title,
    text: stripSceneHeading(block),
  };
}

function stripSceneHeading(block: string): string {
  return block
    .replace(/^##\s+[^\n]*\n?/m, "")
    .replace(/^Chapter\s+\d+[^\n]*\n?/im, "")
    .trim();
}

/** Combine optional chapter title with scene body for storage. */
export function formatSceneText(title: string | undefined, body: string): string {
  const name = title?.trim();
  const prose = body.trim();
  if (!name) return prose;
  if (!prose) return name;
  return `${name}\n\n${prose}`;
}
