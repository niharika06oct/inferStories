/** Center `element` inside a scrollable `container` (uses live layout). */
export function scrollElementIntoContainer(
  container: HTMLElement,
  element: HTMLElement,
): void {
  const containerRect = container.getBoundingClientRect();
  const elementRect = element.getBoundingClientRect();
  const relativeTop =
    elementRect.top - containerRect.top + container.scrollTop;
  const target =
    relativeTop - container.clientHeight / 2 + elementRect.height / 2;

  container.scrollTop = Math.max(
    0,
    Math.min(target, container.scrollHeight - container.clientHeight),
  );
}

function copyTextareaStyles(
  textarea: HTMLTextAreaElement,
  mirror: HTMLDivElement,
): void {
  const cs = window.getComputedStyle(textarea);
  mirror.style.font = cs.font;
  mirror.style.fontFamily = cs.fontFamily;
  mirror.style.fontSize = cs.fontSize;
  mirror.style.fontWeight = cs.fontWeight;
  mirror.style.lineHeight = cs.lineHeight;
  mirror.style.letterSpacing = cs.letterSpacing;
  mirror.style.wordSpacing = cs.wordSpacing;
  mirror.style.padding = cs.padding;
  mirror.style.border = cs.border;
  mirror.style.boxSizing = cs.boxSizing;
  mirror.style.whiteSpace = "pre-wrap";
  mirror.style.wordWrap = "break-word";
  mirror.style.overflowWrap = "break-word";
  mirror.style.width = `${textarea.offsetWidth}px`;
}

/** Fallback scroll using a hidden mirror when no backdrop anchor exists. */
export function scrollTextareaToRange(
  textarea: HTMLTextAreaElement,
  start: number,
  end: number,
): void {
  const value = textarea.value;
  const safeStart = Math.max(0, Math.min(start, value.length));
  const safeEnd = Math.max(safeStart, Math.min(end, value.length));

  textarea.focus();
  textarea.setSelectionRange(safeStart, safeEnd);

  const mirror = document.createElement("div");
  mirror.setAttribute("aria-hidden", "true");
  copyTextareaStyles(textarea, mirror);
  mirror.style.position = "absolute";
  mirror.style.left = "-9999px";
  mirror.style.top = "0";
  mirror.style.visibility = "hidden";
  mirror.style.pointerEvents = "none";

  const before = document.createTextNode(value.slice(0, safeStart));
  const marker = document.createElement("span");
  marker.textContent = value.slice(safeStart, safeEnd) || "\u200b";
  const after = document.createTextNode(value.slice(safeEnd));
  mirror.append(before, marker, after);

  document.body.appendChild(mirror);
  const markerTop = marker.offsetTop;
  const markerHeight = marker.offsetHeight;
  document.body.removeChild(mirror);

  const paddingTop = Number.parseFloat(
    window.getComputedStyle(textarea).paddingTop,
  );
  const target =
    markerTop + paddingTop - textarea.clientHeight / 2 + markerHeight / 2;
  textarea.scrollTop = Math.max(0, target);
}

/** Copy scroll position from backdrop overlay onto the textarea. */
export function syncTextareaScrollFromContainer(
  textarea: HTMLTextAreaElement,
  container: HTMLElement,
): void {
  textarea.scrollTop = container.scrollTop;
  textarea.scrollLeft = container.scrollLeft;
}

/** Copy scroll position from textarea onto the backdrop overlay. */
export function syncContainerScrollFromTextarea(
  container: HTMLElement,
  textarea: HTMLTextAreaElement,
): void {
  container.scrollTop = textarea.scrollTop;
  container.scrollLeft = textarea.scrollLeft;
}
