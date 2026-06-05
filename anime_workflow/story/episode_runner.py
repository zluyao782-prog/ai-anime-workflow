from __future__ import annotations

import subprocess
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
) -> dict[str, Any]:
    updated = dict(storyboard)
    updated["shots"] = [dict(shot) for shot in storyboard["shots"]]
    adapter = AnimeApiAdapter(provider=provider, output_dir=output_dir, metadata_dir=metadata_dir)

    for index, shot in enumerate(updated["shots"]):
        source = Path(source_dir) / updated["project_id"] / updated["episode_id"] / f"{shot['shot_id']}.png"
        create_source_frame(source, index=index)
        result = adapter.stylize(
            AnimeApiRequest(
                project_id=updated["project_id"],
                episode_id=updated["episode_id"],
                shot_id=shot["shot_id"],
                source_image=source,
                style_preset=updated.get("style_preset", "clean_anime_drama"),
                prompt=shot["image_prompt"],
            )
        )
        shot["source_image"] = str(source)
        shot["anime_image"] = str(result.output_image)
        shot["metadata_path"] = str(result.metadata_path)
        shot["cache_hit"] = result.cache_hit

    return updated


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
