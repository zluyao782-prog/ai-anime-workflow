import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from anime_workflow.services.exporter import FFmpegUnavailable, VideoExporter


class VideoExporterTest(unittest.TestCase):
    def test_diagnose_reports_missing_ffmpeg(self):
        with patch.object(shutil, "which", return_value=None):
            self.assertEqual(VideoExporter().diagnose(), "ffmpeg not found on PATH")

    def test_export_requires_existing_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exporter = VideoExporter(ffmpeg_bin="ffmpeg")

            with self.assertRaises(FileNotFoundError):
                exporter.export_slideshow(
                    frame_paths=[root / "missing.png"],
                    output_path=root / "out.mp4",
                    seconds_per_frame=2,
                )

    def test_export_raises_clear_error_when_ffmpeg_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frame = root / "frame.png"
            frame.write_bytes(b"fake-image")
            exporter = VideoExporter(ffmpeg_bin="missing-ffmpeg")

            with self.assertRaises(FFmpegUnavailable):
                exporter.export_slideshow(
                    frame_paths=[frame],
                    output_path=root / "out.mp4",
                    seconds_per_frame=2,
                )


if __name__ == "__main__":
    unittest.main()
