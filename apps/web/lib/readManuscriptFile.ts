import mammoth from "mammoth";

const TEXT_EXTENSIONS = /\.(txt|md|markdown)$/i;
const DOCX_EXTENSION = /\.docx$/i;

export function isSupportedManuscriptFile(file: File): boolean {
  if (TEXT_EXTENSIONS.test(file.name) || DOCX_EXTENSION.test(file.name)) {
    return true;
  }
  if (file.type.startsWith("text/")) return true;
  return (
    file.type ===
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
    file.type === "application/msword"
  );
}

/** Read plain text from .txt, .md, or .docx (Word) files in the browser. */
export async function readManuscriptFile(file: File): Promise<string> {
  if (DOCX_EXTENSION.test(file.name) || isWordMime(file.type)) {
    return readDocxAsText(file);
  }
  if (!TEXT_EXTENSIONS.test(file.name) && !file.type.startsWith("text/")) {
    throw new Error("Unsupported file type. Use .docx, .txt, or .md.");
  }
  return file.text();
}

function isWordMime(type: string): boolean {
  return (
    type ===
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
    type === "application/msword"
  );
}

async function readDocxAsText(file: File): Promise<string> {
  const arrayBuffer = await file.arrayBuffer();
  const { value: html, messages } = await mammoth.convertToHtml({ arrayBuffer });
  if (messages.length > 0) {
    const warnings = messages
      .filter((m) => m.type === "warning")
      .map((m) => m.message);
    if (warnings.length > 0 && !html.trim()) {
      console.warn("[docx import]", warnings.join("; "));
    }
  }
  const text = htmlToStructuredText(html);
  if (!text.trim()) {
    throw new Error(
      "Could not read text from this Word file. Try Save As .txt or export from Word.",
    );
  }
  return text;
}

/** Turn Word HTML into text with ## headings so scene splitting works. */
function htmlToStructuredText(html: string): string {
  let s = html;
  s = s.replace(/<h1[^>]*>([\s\S]*?)<\/h1>/gi, "\n\n## $1\n\n");
  s = s.replace(/<h2[^>]*>([\s\S]*?)<\/h2>/gi, "\n\n## $1\n\n");
  s = s.replace(/<h3[^>]*>([\s\S]*?)<\/h3>/gi, "\n\n## $1\n\n");
  s = s.replace(/<br\s*\/?>/gi, "\n");
  s = s.replace(/<\/p>/gi, "\n\n");
  s = s.replace(/<\/li>/gi, "\n");
  s = s.replace(/<[^>]+>/g, "");
  s = s
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
  return s.replace(/\n{3,}/g, "\n\n").trim();
}
