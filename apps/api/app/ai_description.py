"""Generate a short story synopsis from scene prose (OpenAI or local fallback)."""

from __future__ import annotations

import os

import httpx

MAX_SCENE_EXCERPT = 1200
MAX_SCENES_IN_PROMPT = 12


def _scene_excerpt(text: str, limit: int = 400) -> str:
    t = " ".join(text.split())
    if len(t) <= limit:
        return t
    return t[: limit - 1] + "…"


def _heuristic_description(title: str, scenes: list[tuple[int, str]]) -> str:
    if not scenes:
        return f"A work in progress titled “{title}.”"
    parts = []
    for num, text in scenes[:5]:
        parts.append(_scene_excerpt(text, 220))
    joined = " ".join(parts)
    if len(scenes) == 1:
        return (
            f"“{title}” opens with: {_scene_excerpt(scenes[0][1], 300)}"
        )
    return (
        f"“{title}” follows {len(scenes)} scenes. "
        f"It begins: {parts[0]} "
        + (f"Later threads include: {_scene_excerpt(scenes[-1][1], 180)}" if len(scenes) > 1 else "")
    ).strip()


def generate_story_description(
    title: str,
    scenes: list[tuple[int, str]],
) -> tuple[str, str]:
    """
    Returns (description, source) where source is 'openai' or 'heuristic'.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _heuristic_description(title, scenes), "heuristic"

    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    scene_blocks = []
    for num, text in scenes[:MAX_SCENES_IN_PROMPT]:
        scene_blocks.append(f"Scene {num}:\n{_scene_excerpt(text, 500)}")
    scenes_text = "\n\n".join(scene_blocks) or "(No scenes yet.)"

    prompt = (
        "You are helping a fiction writer. Write a concise story description "
        "(2–4 sentences, under 80 words) for their manuscript metadata. "
        "Capture tone, central conflict, and key relationships implied by the scenes. "
        "Do not use bullet points. Do not invent major plot twists absent from the text.\n\n"
        f"Title: {title}\n\n{scenes_text}"
    )

    try:
        with httpx.Client(timeout=45.0) as client:
            r = client.post(
                f"{base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You write vivid, accurate fiction synopses.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 200,
                    "temperature": 0.6,
                },
            )
            r.raise_for_status()
            data = r.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            if content:
                return content, "openai"
    except (httpx.HTTPError, KeyError, IndexError):
        pass

    return _heuristic_description(title, scenes), "heuristic"
