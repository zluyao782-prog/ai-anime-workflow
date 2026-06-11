from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from anime_workflow.services.anime_api_adapter import AnimeApiAdapter, AnimeApiRequest, AnimeProvider
from anime_workflow.services.exporter import VideoExporter


def generate_episode_images(
    storyboard: dict[str, Any],
    provider: AnimeProvider,
    source_dir: Path,
    output_dir: Path,
    metadata_dir: Path,
    references: list[dict[str, Any]] | None = None,
    workflow_template: str = "",
) -> dict[str, Any]:
    updated = dict(storyboard)
    updated["shots"] = [dict(shot) for shot in storyboard["shots"]]
    adapter = AnimeApiAdapter(provider=provider, output_dir=output_dir, metadata_dir=metadata_dir)

    for index, shot in enumerate(updated["shots"]):
        if workflow_template:
            shot["workflow_template"] = workflow_template
        _generate_shot_image(updated, shot, index, adapter, source_dir, references or [])

    return updated


def generate_shot_image(
    storyboard: dict[str, Any],
    shot_id: str,
    provider: AnimeProvider,
    source_dir: Path,
    output_dir: Path,
    metadata_dir: Path,
    references: list[dict[str, Any]] | None = None,
    workflow_template: str = "",
) -> dict[str, Any]:
    updated = dict(storyboard)
    updated["shots"] = [dict(shot) for shot in storyboard["shots"]]
    adapter = AnimeApiAdapter(provider=provider, output_dir=output_dir, metadata_dir=metadata_dir)

    for index, shot in enumerate(updated["shots"]):
        if shot.get("shot_id") != shot_id:
            continue
        template = workflow_template or str(shot.get("workflow_template") or provider.name)
        shot["workflow_template"] = template
        _generate_shot_image(updated, shot, index, adapter, source_dir, references or [])
        append_rerun_history(shot, provider, template)
        return updated

    raise FileNotFoundError("shot not found")


def _generate_shot_image(
    storyboard: dict[str, Any],
    shot: dict[str, Any],
    index: int,
    adapter: AnimeApiAdapter,
    source_dir: Path,
    references: list[dict[str, Any]],
) -> None:
    source = Path(source_dir) / storyboard["project_id"] / storyboard["episode_id"] / f"{shot['shot_id']}.png"
    create_source_frame(source, index=index)
    workflow_template = str(shot.get("workflow_template") or "mock_image")
    reference_bindings = tuple(normalized_reference_bindings(shot.get("reference_bindings")))
    result = adapter.stylize(
        AnimeApiRequest(
            project_id=storyboard["project_id"],
            episode_id=storyboard["episode_id"],
            shot_id=shot["shot_id"],
            source_image=source,
            style_preset=storyboard.get("style_preset", "clean_anime_drama"),
            prompt=prompt_with_references(shot, references),
            reference_images=reference_images_for_shot(shot, references),
            workflow_template=workflow_template,
            reference_bindings=reference_bindings,
        )
    )
    shot["source_image"] = str(source)
    shot["anime_image"] = str(result.output_image)
    shot["metadata_path"] = str(result.metadata_path)
    shot["cache_hit"] = result.cache_hit


def prompt_with_references(shot: dict[str, Any], references: list[dict[str, Any]]) -> str:
    base_prompt = str(shot.get("image_prompt") or "")
    bindings = normalized_reference_bindings(shot.get("reference_bindings"))
    if not bindings:
        return base_prompt
    by_id = {str(reference.get("reference_id") or ""): reference for reference in references}
    fragments: list[str] = []
    for reference_id in bindings:
        reference = by_id.get(reference_id)
        if not reference:
            continue
        fragment = str(reference.get("prompt_fragment") or reference.get("description") or reference.get("name") or "").strip()
        if fragment:
            fragments.append(f"{reference.get('reference_type', 'reference')}: {fragment}")
    if not fragments:
        return base_prompt
    return f"{base_prompt}\nContinuity references: {'; '.join(fragments)}"


def reference_images_for_shot(shot: dict[str, Any], references: list[dict[str, Any]]) -> tuple[Path, ...]:
    bindings = normalized_reference_bindings(shot.get("reference_bindings"))
    if not bindings:
        return ()
    by_id = {str(reference.get("reference_id") or ""): reference for reference in references}
    result: list[Path] = []
    for reference_id in bindings:
        reference = by_id.get(reference_id)
        if not reference:
            continue
        image = str(reference.get("reference_image") or "").strip()
        if image and not image.startswith(("http://", "https://", "data:")):
            result.append(Path(image))
    return tuple(result)


def normalized_reference_bindings(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        reference_id = str(item or "").strip()
        if reference_id and reference_id not in seen:
            seen.add(reference_id)
            result.append(reference_id)
    return result


def append_rerun_history(shot: dict[str, Any], provider: AnimeProvider, workflow_template: str) -> None:
    history = shot.get("rerun_history") if isinstance(shot.get("rerun_history"), list) else []
    history.append(
        {
            "provider": provider.name,
            "model_version": provider.model_version,
            "workflow_template": workflow_template,
            "prompt": shot.get("image_prompt", ""),
            "reference_bindings": normalized_reference_bindings(shot.get("reference_bindings")),
            "source_image": shot.get("source_image", ""),
            "anime_image": shot.get("anime_image", ""),
            "metadata_path": shot.get("metadata_path", ""),
            "cache_hit": bool(shot.get("cache_hit", False)),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    shot["rerun_history"] = history


def export_episode_video(storyboard: dict[str, Any], output_dir: Path) -> Path:
    frames = [Path(shot["anime_image"]) for shot in storyboard["shots"] if shot.get("anime_image")]
    seconds_per_frame = max(1, round(storyboard.get("duration_seconds", len(frames) * 3) / max(1, len(frames))))
    output = Path(output_dir) / f"{storyboard['project_id']}-{storyboard['episode_id']}.mp4"
    return VideoExporter().export_slideshow(frames, output, seconds_per_frame=seconds_per_frame, width=1080, height=1920)


def create_source_frame(path: Path, index: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    palette = ["#202236", "#243047", "#2c2540", "#1f3340", "#382b35", "#263126"]
    color = palette[index % len(palette)]
    accent = "#d6c2a3" if index % 2 == 0 else "#c6d5e8"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=1080x1920:d=1",
            "-vf",
            f"drawbox=x=270:y=500:w=540:h=620:color={accent}:t=fill,drawbox=x=390:y=720:w=300:h=90:color=#141827:t=fill",
            "-frames:v",
            "1",
            str(path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
