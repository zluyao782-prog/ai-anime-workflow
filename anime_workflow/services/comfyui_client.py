from __future__ import annotations

import json
from typing import Any, Callable
from urllib import request as urllib_request


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

