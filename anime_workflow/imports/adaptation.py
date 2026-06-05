from __future__ import annotations

import re
from typing import Any

from anime_workflow.jobs.models import now_iso
from anime_workflow.projects.models import slug


BUDGETS = {
    30: 550,
    60: 1000,
    90: 1500,
    180: 3000,
}


def clean_source_text(text: str) -> str:
    lines: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if stripped.startswith(">"):
            continue
        stripped = re.sub(r"^#{1,6}\s*", "", stripped)
        stripped = re.sub(r"#\s*(第[一二三四五六七八九十百千万0-9]+[章节集])", r"\1", stripped)
        stripped = re.sub(r"^\s*[-*_]{3,}\s*$", "", stripped)
        if stripped:
            lines.append(stripped)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def split_short_video_episodes(text: str, duration_seconds: int, max_episodes: int) -> list[str]:
    cleaned = clean_source_text(text)
    if not cleaned:
        raise ValueError("document text is empty")
    budget = BUDGETS.get(duration_seconds, max(400, duration_seconds * 16))
    paragraphs = [item.strip() for item in re.split(r"\n{2,}", cleaned) if item.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        next_value = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if current and len(next_value) > budget:
            chunks.append(current)
            current = paragraph
            if len(chunks) >= max_episodes:
                break
        else:
            current = next_value
    if current and len(chunks) < max_episodes:
        chunks.append(current)
    if not chunks:
        chunks = [cleaned[:budget]]
    return chunks[:max_episodes]


def build_episode_drafts(chunks: list[str], duration_seconds: int, shot_count: int) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, start=1):
        excerpt = chunk.strip()
        title_seed = re.split(r"[。！？!?\n]", excerpt, maxsplit=1)[0].strip() or f"第{index}集"
        episodes.append(
            {
                "episode_id": f"episode_{index:03d}",
                "episode_no": index,
                "title": f"第{index}集：{title_seed[:18]}",
                "premise": build_short_video_premise(excerpt),
                "duration_seconds": duration_seconds,
                "shot_count": shot_count,
                "source_excerpt": excerpt,
                "status": "draft",
            }
        )
    return episodes


def build_short_video_premise(excerpt: str) -> str:
    compact = re.sub(r"\s+", " ", excerpt).strip()
    if len(compact) <= 140:
        return compact
    return f"{compact[:120]}... 结尾留下下一集钩子。"


def build_import_record(
    import_id: str,
    project_id: str,
    filename: str,
    content_type: str,
    cleaned_text_path: str,
    text_length: int,
    episode_ids: list[str],
    settings: dict[str, Any],
) -> dict[str, Any]:
    return {
        "import_id": slug(import_id, "import"),
        "project_id": slug(project_id, "project"),
        "filename": filename,
        "content_type": content_type,
        "text_length": text_length,
        "cleaned_text_path": cleaned_text_path,
        "episode_ids": episode_ids,
        "settings": dict(settings),
        "created_at": now_iso(),
    }
