#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from anime_workflow.services.anime_api_adapter import AnimeApiAdapter, AnimeApiRequest, OpenAIImageProvider


def create_demo_frame(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=#202236:s=1024x1024:d=1",
            "-vf",
            "drawbox=x=260:y=260:w=504:h=504:color=#d6c2a3:t=fill,drawbox=x=360:y=460:w=304:h=80:color=#141827:t=fill",
            "-frames:v",
            "1",
            str(path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not set. Export it before running this script.")
        return 2

    source_frame = ROOT / "data/assets/source_frames/openai-demo-source.png"
    create_demo_frame(source_frame)

    adapter = AnimeApiAdapter(
        provider=OpenAIImageProvider(
            api_key=api_key,
            model=os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2"),
            endpoint=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com"),
        ),
        output_dir=ROOT / "data/assets/anime_frames",
        metadata_dir=ROOT / "data/assets/api_metadata",
    )
    result = adapter.stylize(
        AnimeApiRequest(
            project_id="openai_demo",
            episode_id="episode_001",
            shot_id="shot_001",
            source_image=source_frame,
            style_preset="clean_anime_drama",
            prompt=(
                "把这张基础分镜改成适合抖音动漫短剧的画面。"
                "保持中心人物构图，增强日系动漫线条、电影感光影、清晰角色轮廓。"
            ),
        )
    )

    print(f"source_frame={source_frame}")
    print(f"anime_frame={result.output_image}")
    print(f"metadata={result.metadata_path}")
    print(f"cache_hit={result.cache_hit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
