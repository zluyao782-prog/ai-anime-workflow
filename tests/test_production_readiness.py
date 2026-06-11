import tempfile
import unittest
from pathlib import Path
from unittest import mock

from anime_workflow.services.production_readiness import production_readiness


class ProductionReadinessTest(unittest.TestCase):
    def test_ready_with_openai_remote_comfyui_and_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "exports"
            config = {
                "openai_api_key": "sk-test",
                "openai_image_model": "gpt-image-2",
                "openai_base_url": "https://api.example.test",
                "comfyui_mode": "remote",
                "comfyui_remote_base_url": "http://10.0.0.2:8188",
                "output_dir": str(output_dir),
            }

            with (
                mock.patch("anime_workflow.services.production_readiness.check_http_json", return_value={"ok": True, "detail": "{}"}),
                mock.patch("anime_workflow.services.production_readiness.shutil.which", return_value="/usr/bin/ffmpeg"),
            ):
                readiness = production_readiness(config, Path(tmp))

            self.assertTrue(readiness["ok"])
            self.assertTrue(readiness["checks"]["openai"]["ok"])
            self.assertEqual(readiness["checks"]["openai"]["model"], "gpt-image-2")
            self.assertTrue(readiness["checks"]["comfyui"]["ok"])
            self.assertEqual(readiness["checks"]["comfyui"]["base_url"], "http://10.0.0.2:8188")
            self.assertTrue(readiness["checks"]["ffmpeg"]["ok"])
            self.assertEqual(readiness["checks"]["output_dir"]["path"], str(output_dir))

    def test_not_ready_without_openai_unreachable_comfyui_and_missing_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "openai_api_key": "",
                "comfyui_mode": "remote",
                "comfyui_remote_base_url": "http://10.0.0.2:8188",
            }

            with (
                mock.patch("anime_workflow.services.production_readiness.check_http_json", return_value={"ok": False, "detail": "unreachable"}),
                mock.patch("anime_workflow.services.production_readiness.shutil.which", return_value=None),
            ):
                readiness = production_readiness(config, Path(tmp))

            self.assertFalse(readiness["ok"])
            self.assertFalse(readiness["checks"]["openai"]["ok"])
            self.assertEqual(readiness["checks"]["openai"]["detail"], "OpenAI API Key is not configured")
            self.assertFalse(readiness["checks"]["comfyui"]["ok"])
            self.assertFalse(readiness["checks"]["ffmpeg"]["ok"])


if __name__ == "__main__":
    unittest.main()
