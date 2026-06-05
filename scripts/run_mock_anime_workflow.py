#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from anime_workflow.services.anime_api_adapter import AnimeApiAdapter, AnimeApiRequest, MockAnimeProvider
from anime_workflow.services.exporter import VideoExporter


def create_demo_frame(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=#1b1d2a:s=1080x1920:d=1",
            "-vf",
            "drawbox=x=270:y=520:w=540:h=540:color=#d8c6a3:t=fill,drawbox=x=390:y=720:w=300:h=90:color=#202338:t=fill",
            "-frames:v",
            "1",
            str(path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    source_frame = ROOT / "data/assets/source_frames/demo-shot-001.png"
    create_demo_frame(source_frame)

    adapter = AnimeApiAdapter(
        provider=MockAnimeProvider(),
        output_dir=ROOT / "data/assets/anime_frames",
        metadata_dir=ROOT / "data/assets/api_metadata",
    )
    result = adapter.stylize(
        AnimeApiRequest(
            project_id="demo_project",
            episode_id="episode_001",
            shot_id="shot_001",
            source_image=source_frame,
            style_preset="clean_anime_drama",
            prompt="young detective, moonlit village, clean anime drama style",
        )
    )

    output_video = ROOT / "data/exports/demo-douyin-workflow.mp4"
    VideoExporter().export_slideshow(
        frame_paths=[result.output_image],
        output_path=output_video,
        seconds_per_frame=3,
        width=1080,
        height=1920,
    )

    print(f"source_frame={source_frame}")
    print(f"anime_frame={result.output_image}")
    print(f"metadata={result.metadata_path}")
    print(f"video={output_video}")
    print(f"cache_hit={result.cache_hit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
