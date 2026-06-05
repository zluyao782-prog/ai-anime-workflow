import json
import tempfile
import unittest
from pathlib import Path

from anime_workflow.launcher.config import LauncherConfigStore


class LauncherConfigStoreTest(unittest.TestCase):
    def test_save_and_load_masks_api_key_for_public_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LauncherConfigStore(Path(tmp) / "settings.local.json")
            store.save(
                {
                    "openai_api_key": "sk-test-secret",
                    "openai_image_model": "gpt-image-2",
                    "ollama_text_model": "qwen2.5:0.5b",
                    "comfyui_base_url": "http://127.0.0.1:8188",
                }
            )

            raw = json.loads((Path(tmp) / "settings.local.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["openai_api_key"], "sk-test-secret")
            public = store.load_public()

            self.assertEqual(public["openai_api_key"], "sk-...cret")
            self.assertTrue(public["openai_api_key_configured"])
            self.assertEqual(public["openai_image_model"], "gpt-image-2")
            self.assertEqual(public["openai_base_url"], "https://aigate.zhixingjidian.cn")

    def test_defaults_are_returned_when_config_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LauncherConfigStore(Path(tmp) / "missing.json")
            public = store.load_public()

            self.assertFalse(public["openai_api_key_configured"])
            self.assertEqual(public["openai_image_model"], "gpt-image-2")
            self.assertEqual(public["openai_base_url"], "https://aigate.zhixingjidian.cn")
            self.assertEqual(public["ollama_text_model"], "qwen2.5:0.5b")


if __name__ == "__main__":
    unittest.main()
