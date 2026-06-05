import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from anime_workflow.launcher.services import ComfyUIService, tail_file


class ComfyUIServiceTest(unittest.TestCase):
    def test_start_uses_d_drive_paths_and_writes_pid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            popen = Mock()
            popen.pid = 12345
            service = ComfyUIService(
                project_root=root,
                comfyui_dir=Path("/mnt/d/Codex/ai-anime-workflow/ComfyUI"),
                comfyui_venv=Path("/mnt/d/Codex/ai-anime-workflow/comfyui-venv"),
                popen_factory=Mock(return_value=popen),
            )

            result = service.start()

            self.assertEqual(result["status"], "started")
            self.assertEqual((root / "work/comfyui.pid").read_text(encoding="utf-8"), "12345")
            args = service.popen_factory.call_args.args[0]
            self.assertEqual(args[0], "/mnt/d/Codex/ai-anime-workflow/comfyui-venv/bin/python")
            self.assertIn("--cpu", args)
            self.assertEqual(service.popen_factory.call_args.kwargs["cwd"], "/mnt/d/Codex/ai-anime-workflow/ComfyUI")

    def test_tail_file_returns_last_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "service.log"
            path.write_text("\n".join(f"line {i}" for i in range(10)), encoding="utf-8")

            self.assertEqual(tail_file(path, 3), "line 7\nline 8\nline 9")

    def test_stop_removes_pid_file_after_kill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pid_file = root / "work/comfyui.pid"
            pid_file.parent.mkdir(parents=True)
            pid_file.write_text("12345", encoding="utf-8")
            service = ComfyUIService(project_root=root)

            with patch("os.kill") as kill:
                result = service.stop()

            kill.assert_called()
            self.assertEqual(result["status"], "stopped")
            self.assertFalse(pid_file.exists())


if __name__ == "__main__":
    unittest.main()
