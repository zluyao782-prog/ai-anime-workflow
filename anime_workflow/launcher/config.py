from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = {
    "openai_api_key": "",
    "openai_base_url": "https://aigate.zhixingjidian.cn",
    "openai_image_model": "gpt-image-2",
    "openai_text_model": "gpt-4.1-mini",
    "openai_text_endpoint_mode": "chat_completions",
    "ollama_text_model": "qwen2.5:0.5b",
    "comfyui_mode": "local",
    "comfyui_base_url": "http://127.0.0.1:8188",
    "comfyui_remote_base_url": "",
    "output_dir": "data/exports",
}


class LauncherConfigStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return dict(DEFAULT_CONFIG)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        return merged

    def load_public(self) -> dict[str, Any]:
        config = self.load()
        key = config.get("openai_api_key", "")
        public = dict(config)
        public["openai_api_key_configured"] = bool(key)
        public["openai_api_key"] = self._mask_key(key)
        return public

    def save(self, values: dict[str, Any]) -> dict[str, Any]:
        config = self.load()
        allowed = set(DEFAULT_CONFIG)
        for key, value in values.items():
            if key in allowed:
                config[key] = normalize_config_value(key, value)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        return config

    @staticmethod
    def _mask_key(key: str) -> str:
        if not key:
            return ""
        if len(key) <= 8:
            return "****"
        return f"{key[:3]}...{key[-4:]}"


def normalize_config_value(key: str, value: Any) -> str:
    text = str(value).strip()
    if key == "comfyui_mode" and text not in {"local", "remote"}:
        return "local"
    return text


def effective_comfyui_base_url(config: dict[str, Any]) -> str:
    mode = str(config.get("comfyui_mode") or "local").strip()
    if mode == "remote":
        remote = str(config.get("comfyui_remote_base_url") or "").strip()
        if remote:
            return remote
    return str(config.get("comfyui_base_url") or DEFAULT_CONFIG["comfyui_base_url"]).strip()
