from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


class FFmpegUnavailable(RuntimeError):
    pass


class VideoExporter:
    def __init__(self, ffmpeg_bin: str = "ffmpeg") -> None:
        self.ffmpeg_bin = ffmpeg_bin

    def diagnose(self) -> str:
        if shutil.which(self.ffmpeg_bin) is None:
            return f"{self.ffmpeg_bin} not found on PATH"
        return f"{self.ffmpeg_bin} available"

    def export_slideshow(
        self,
        frame_paths: list[Path],
        output_path: Path,
        seconds_per_frame: int = 2,
        width: int = 1080,
        height: int = 1920,
    ) -> Path:
        if not frame_paths:
            raise ValueError("frame_paths cannot be empty")
        for frame in frame_paths:
            if not Path(frame).exists():
                raise FileNotFoundError(f"frame not found: {frame}")
        if shutil.which(self.ffmpeg_bin) is None:
            raise FFmpegUnavailable(f"{self.ffmpeg_bin} not found on PATH")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp:
            list_file = Path(tmp) / "frames.txt"
            lines: list[str] = []
            for frame in frame_paths:
                lines.append(f"file '{Path(frame).resolve()}'")
                lines.append(f"duration {seconds_per_frame}")
            lines.append(f"file '{Path(frame_paths[-1]).resolve()}'")
            list_file.write_text("\n".join(lines), encoding="utf-8")

            command = [
                self.ffmpeg_bin,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-vf",
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps=30",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ]
            subprocess.run(command, check=True)

        return output_path
