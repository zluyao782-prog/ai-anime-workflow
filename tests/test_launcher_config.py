import json
import tempfile
import unittest
from pathlib import Path

from anime_workflow.launcher.config import LauncherConfigStore, effective_comfyui_base_url


class LauncherConfigStoreTest(unittest.TestCase):
    def test_save_and_load_masks_api_key_for_public_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LauncherConfigStore(Path(tmp) / "settings.local.json")
            store.save(
                {
                    "openai_api_key": "sk-test-secret",
                    "openai_image_model": "gpt-image-2",
                    "ollama_text_model": "qwen2.5:0.5b",
                    "comfyui_mode": "remote",
                    "comfyui_base_url": "http://127.0.0.1:8188",
                    "comfyui_remote_base_url": "http://10.0.0.2:8188",
                }
            )

            raw = json.loads((Path(tmp) / "settings.local.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["openai_api_key"], "sk-test-secret")
            public = store.load_public()

            self.assertEqual(public["openai_api_key"], "sk-...cret")
            self.assertTrue(public["openai_api_key_configured"])
            self.assertEqual(public["openai_image_model"], "gpt-image-2")
            self.assertEqual(public["openai_base_url"], "https://aigate.zhixingjidian.cn")
            self.assertEqual(public["openai_text_model"], "gpt-4.1-mini")
            self.assertEqual(public["openai_text_endpoint_mode"], "chat_completions")
            self.assertEqual(public["comfyui_mode"], "remote")
            self.assertEqual(public["comfyui_remote_base_url"], "http://10.0.0.2:8188")
            self.assertEqual(effective_comfyui_base_url(public), "http://10.0.0.2:8188")

    def test_defaults_are_returned_when_config_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LauncherConfigStore(Path(tmp) / "missing.json")
            public = store.load_public()

            self.assertFalse(public["openai_api_key_configured"])
            self.assertEqual(public["openai_image_model"], "gpt-image-2")
            self.assertEqual(public["openai_base_url"], "https://aigate.zhixingjidian.cn")
            self.assertEqual(public["ollama_text_model"], "qwen2.5:0.5b")
            self.assertEqual(public["openai_text_model"], "gpt-4.1-mini")
            self.assertEqual(public["openai_text_endpoint_mode"], "chat_completions")
            self.assertEqual(public["comfyui_mode"], "local")
            self.assertEqual(public["comfyui_base_url"], "http://127.0.0.1:8188")
            self.assertEqual(public["comfyui_remote_base_url"], "")
            self.assertEqual(effective_comfyui_base_url(public), "http://127.0.0.1:8188")

    def test_invalid_comfyui_mode_falls_back_to_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LauncherConfigStore(Path(tmp) / "settings.local.json")
            store.save({"comfyui_mode": "bad", "comfyui_remote_base_url": "http://10.0.0.2:8188"})

            config = store.load()

            self.assertEqual(config["comfyui_mode"], "local")
            self.assertEqual(effective_comfyui_base_url(config), "http://127.0.0.1:8188")


if __name__ == "__main__":
    unittest.main()
