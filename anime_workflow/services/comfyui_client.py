from __future__ import annotations

import json
import time
from typing import Any, Callable
from urllib import request as urllib_request
from urllib.parse import urlencode


class ComfyUIClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8188",
        opener: Callable[[urllib_request.Request], Any] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._opener = opener or urllib_request.urlopen

    def submit_prompt(self, prompt: dict[str, Any], client_id: str = "anime-workflow") -> str:
        payload = json.dumps({"prompt": prompt, "client_id": client_id}).encode("utf-8")
        request = urllib_request.Request(
            f"{self.base_url}/prompt",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self._opener(request) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["prompt_id"]

    def history(self, prompt_id: str) -> dict[str, Any]:
        request = urllib_request.Request(f"{self.base_url}/history/{prompt_id}", method="GET")
        with self._opener(request) as response:
            return json.loads(response.read().decode("utf-8"))

    def wait_for_history(self, prompt_id: str, timeout_seconds: int = 180, interval_seconds: float = 1.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            data = self.history(prompt_id)
            if prompt_id in data:
                return data[prompt_id]
            if data.get("outputs"):
                return data
            time.sleep(interval_seconds)
        raise TimeoutError(f"ComfyUI prompt timed out: {prompt_id}")

    def view_image(self, filename: str, subfolder: str = "", image_type: str = "output") -> bytes:
        query = urlencode({"filename": filename, "subfolder": subfolder, "type": image_type})
        request = urllib_request.Request(f"{self.base_url}/view?{query}", method="GET")
        with self._opener(request) as response:
            return response.read()


def extract_output_value(history: dict[str, Any]) -> str:
    outputs = history.get("outputs") if isinstance(history, dict) else None
    if not isinstance(outputs, dict):
        raise ValueError("ComfyUI history has no outputs")
    for output in outputs.values():
        if not isinstance(output, dict):
            continue
        for key in ("string", "text"):
            values = output.get(key)
            if isinstance(values, list) and values:
                return str(values[0])
            if isinstance(values, str):
                return values
        images = output.get("images")
        if isinstance(images, list) and images:
            first = images[0]
            if isinstance(first, dict) and first.get("filename"):
                return json.dumps(
                    {
                        "filename": first.get("filename", ""),
                        "subfolder": first.get("subfolder", ""),
                        "type": first.get("type", "output"),
                    }
                )
    raise ValueError("ComfyUI history has no readable output")
