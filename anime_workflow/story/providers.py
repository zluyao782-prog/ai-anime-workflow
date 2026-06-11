from __future__ import annotations

import json
from typing import Any
from urllib import request
from urllib.parse import urlparse

from anime_workflow.story.storyboard import generate_storyboard


class LocalStoryboardProvider:
    name = "local"

    def generate(self, values: dict[str, Any]) -> dict[str, Any]:
        return generate_storyboard(values)


class OpenAICompatibleStoryboardProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        endpoint_mode: str = "chat_completions",
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.endpoint_mode = endpoint_mode
        self.timeout = timeout

    def generate(self, values: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise ValueError("OpenAI API Key is not configured")
        if self.endpoint_mode == "responses":
            content = self._post_responses(values)
        else:
            content = self._post_chat_completions(values)
        return parse_storyboard_content(content)

    def _post_chat_completions(self, values: dict[str, Any]) -> str:
        response = self._post_json(
            f"{self.base_url}/v1/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": storyboard_system_prompt()},
                    {"role": "user", "content": storyboard_user_prompt(values)},
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
            },
        )
        try:
            return str(response["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("storyboard API returned invalid JSON") from exc

    def _post_responses(self, values: dict[str, Any]) -> str:
        response = self._post_json(
            f"{self.base_url}/v1/responses",
            {
                "model": self.model,
                "input": f"{storyboard_system_prompt()}\n\n{storyboard_user_prompt(values)}",
                "temperature": 0.7,
            },
        )
        if response.get("output_text"):
            return str(response["output_text"])
        try:
            return str(response["output"][0]["content"][0]["text"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("storyboard API returned invalid JSON") from exc

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        http_request = request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        if is_local_url(url):
            context = request.build_opener(request.ProxyHandler({})).open(http_request, timeout=self.timeout)
        else:
            context = request.urlopen(http_request, timeout=self.timeout)
        with context as response:
            return json.loads(response.read().decode("utf-8"))


def is_local_url(url: str) -> bool:
    hostname = urlparse(url).hostname or ""
    return hostname == "localhost" or hostname == "127.0.0.1" or hostname.startswith("127.")


def storyboard_system_prompt() -> str:
    return (
        "你是短视频动漫分镜编剧。只返回一个 JSON object，不要 Markdown。"
        "JSON 必须包含 title, genre, premise, protagonist, style_preset, platform, "
        "duration_seconds, shot_count, shots。每个 shot 必须包含 shot_id, duration, "
        "scene, dialogue, image_prompt, camera, emotion, source_image, anime_image。"
    )


def storyboard_user_prompt(values: dict[str, Any]) -> str:
    return json.dumps(
        {
            "task": "把本集内容改编成适合抖音/B站的动漫短剧分镜",
            "requirements": {
                "opening_hook": True,
                "ending_hook": True,
                "consistent_character": True,
                "vertical_video": True,
            },
            "episode": values,
        },
        ensure_ascii=False,
    )


def parse_storyboard_content(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("storyboard API returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("storyboard API returned invalid storyboard")
    return validate_storyboard(parsed)


def validate_storyboard(storyboard: dict[str, Any]) -> dict[str, Any]:
    required = {
        "title",
        "genre",
        "premise",
        "protagonist",
        "style_preset",
        "platform",
        "duration_seconds",
        "shot_count",
        "shots",
    }
    if any(key not in storyboard for key in required) or not isinstance(storyboard.get("shots"), list):
        raise ValueError("storyboard API returned invalid storyboard")
    shot_required = {"shot_id", "duration", "scene", "dialogue", "image_prompt", "camera", "emotion", "source_image", "anime_image"}
    for shot in storyboard["shots"]:
        if not isinstance(shot, dict) or any(key not in shot for key in shot_required):
            raise ValueError("storyboard API returned invalid storyboard")
    return storyboard


def storyboard_provider_from_config(config: dict[str, Any], provider_name: str, confirm_openai: bool = False):
    provider_name = str(provider_name or "local").lower()
    if provider_name in {"local", "mock"}:
        return LocalStoryboardProvider()
    if provider_name == "openai":
        if not confirm_openai:
            raise ValueError("openai storyboard provider requires confirmation")
        api_key = str(config.get("openai_api_key") or "")
        if not api_key:
            raise ValueError("OpenAI API Key is not configured")
        return OpenAICompatibleStoryboardProvider(
            api_key=api_key,
            base_url=str(config.get("openai_base_url") or ""),
            model=str(config.get("openai_text_model") or config.get("ollama_text_model") or "gpt-4.1-mini"),
            endpoint_mode=str(config.get("openai_text_endpoint_mode") or "chat_completions"),
        )
    raise ValueError("invalid storyboard provider")
