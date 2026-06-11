from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
import uuid
from base64 import b64decode, b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib import request as urllib_request

from anime_workflow.services.comfyui_client import ComfyUIClient, extract_output_value


@dataclass(frozen=True)
class AnimeApiRequest:
    project_id: str
    episode_id: str
    shot_id: str
    source_image: Path
    style_preset: str
    prompt: str = ""
    character_reference: Path | None = None
    reference_images: tuple[Path, ...] = ()


@dataclass(frozen=True)
class AnimeApiResult:
    output_image: Path
    metadata_path: Path
    cache_hit: bool


class AnimeProvider(Protocol):
    name: str
    model_version: str

    def stylize(self, request: AnimeApiRequest, output_image: Path) -> None:
        """Write an anime-stylized image to output_image."""


class MockAnimeProvider:
    name = "mock"
    model_version = "mock-v1"

    def __init__(self) -> None:
        self.call_count = 0

    def stylize(self, request: AnimeApiRequest, output_image: Path) -> None:
        self.call_count += 1
        output_image.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(request.source_image, output_image)


class HttpAnimeProvider:
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        provider_name: str,
        model_version: str,
        opener: Callable[[urllib_request.Request], Any] | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.name = provider_name
        self.model_version = model_version
        self._opener = opener or urllib_request.urlopen

    def stylize(self, request: AnimeApiRequest, output_image: Path) -> None:
        payload = {
            "image_base64": b64encode(Path(request.source_image).read_bytes()).decode("ascii"),
            "style_preset": request.style_preset,
            "prompt": request.prompt,
            "project_id": request.project_id,
            "episode_id": request.episode_id,
            "shot_id": request.shot_id,
        }
        if request.character_reference:
            payload["character_reference_base64"] = b64encode(Path(request.character_reference).read_bytes()).decode("ascii")

        http_request = urllib_request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with self._opener(http_request) as response:
            data = json.loads(response.read().decode("utf-8"))

        output_image.parent.mkdir(parents=True, exist_ok=True)
        output_image.write_bytes(b64decode(data["image_base64"]))


class OpenAIImageProvider:
    name = "openai"
    DEFAULT_ENDPOINT_PATH = "/v1/images/edits"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-image-2",
        endpoint: str = "https://api.openai.com",
        opener: Callable[[urllib_request.Request], Any] | None = None,
    ) -> None:
        self.api_key = api_key
        self.model_version = model
        self.endpoint = self._normalize_endpoint(endpoint)
        self._opener = opener or urllib_request.urlopen

    def stylize(self, request: AnimeApiRequest, output_image: Path) -> None:
        fields = {
            "model": self.model_version,
            "prompt": self._build_prompt(request),
        }
        files = {
            "image": Path(request.source_image),
        }
        if request.character_reference:
            files["character_reference"] = Path(request.character_reference)

        body, content_type = self._multipart_body(fields, files)
        http_request = urllib_request.Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": content_type,
            },
            method="POST",
        )
        with self._opener(http_request) as response:
            data = json.loads(response.read().decode("utf-8"))

        output_image.parent.mkdir(parents=True, exist_ok=True)
        output_image.write_bytes(b64decode(data["data"][0]["b64_json"]))

    @staticmethod
    def _build_prompt(request: AnimeApiRequest) -> str:
        parts = [
            request.prompt,
            f"Style preset: {request.style_preset}.",
            "Transform the input frame into a consistent anime short-drama frame.",
            "Preserve the composition and character identity while improving linework, lighting, and cinematic clarity.",
        ]
        return "\n".join(part for part in parts if part)

    @staticmethod
    def _multipart_body(fields: dict[str, str], files: dict[str, Path]) -> tuple[bytes, str]:
        boundary = f"----ai-anime-{uuid.uuid4().hex}"
        chunks: list[bytes] = []

        for name, value in fields.items():
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode("ascii"),
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
                    str(value).encode("utf-8"),
                    b"\r\n",
                ]
            )

        for name, path in files.items():
            mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode("ascii"),
                    f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'.encode("ascii"),
                    f"Content-Type: {mime_type}\r\n\r\n".encode("ascii"),
                    path.read_bytes(),
                    b"\r\n",
                ]
            )

        chunks.append(f"--{boundary}--\r\n".encode("ascii"))
        return b"".join(chunks), f"multipart/form-data; boundary={boundary}"

    @classmethod
    def _normalize_endpoint(cls, endpoint: str) -> str:
        clean = endpoint.strip().rstrip("/")
        if clean.endswith("/images/edits"):
            return clean
        return f"{clean}{cls.DEFAULT_ENDPOINT_PATH}"


class ComfyUIAnimeProvider:
    name = "comfyui"
    model_version = "external-anime-stylize-v1"

    def __init__(
        self,
        base_url: str,
        api_endpoint: str = "mock",
        api_key: str = "",
        provider_name: str = "mock",
        model_version: str = "mock-v1",
        workflow_template: dict[str, Any] | None = None,
        timeout_seconds: int = 180,
        client: ComfyUIClient | None = None,
    ) -> None:
        self.base_url = base_url
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.external_provider_name = provider_name
        self.external_model_version = model_version
        self.workflow_template = workflow_template or {}
        self.model_version = f"comfyui:{provider_name}:{model_version}"
        self.timeout_seconds = timeout_seconds
        self.client = client or ComfyUIClient(base_url=base_url)

    def stylize(self, request: AnimeApiRequest, output_image: Path) -> None:
        workflow = self._workflow(request, output_image)
        prompt_id = self.client.submit_prompt(workflow)
        history = self.client.wait_for_history(prompt_id, timeout_seconds=self.timeout_seconds)
        value = extract_output_value(history)
        image_bytes = self._image_bytes(value)
        output_image.parent.mkdir(parents=True, exist_ok=True)
        output_image.write_bytes(image_bytes)

    def _workflow(self, request: AnimeApiRequest, output_image: Path) -> dict[str, Any]:
        remote_output = f"ai_anime_workflow_outputs/{request.project_id}/{request.episode_id}/{output_image.name}"
        comfyui = self.workflow_template.get("comfyui") if isinstance(self.workflow_template, dict) else None
        if isinstance(comfyui, dict):
            node_id = str(comfyui.get("node_id") or "1")
            class_type = str(comfyui.get("class_type") or "ExternalAnimeStylize")
            raw_inputs = comfyui.get("inputs") if isinstance(comfyui.get("inputs"), dict) else {}
            values = self._workflow_values(request, output_image, remote_output)
            inputs = {str(key): self._resolve_template_value(value, values) for key, value in raw_inputs.items()}
            return {node_id: {"class_type": class_type, "inputs": inputs}}
        return {
            "1": {
                "class_type": "ExternalAnimeStylize",
                "inputs": self._workflow_values(request, output_image, remote_output),
            }
        }

    def _workflow_values(self, request: AnimeApiRequest, output_image: Path, remote_output: str) -> dict[str, str]:
        return {
            "source_image_path": "",
            "source_image_base64": b64encode(Path(request.source_image).read_bytes()).decode("ascii"),
            "reference_image_base64": self._reference_image_base64(request),
            "output_path": remote_output,
            "remote_output_path": remote_output,
            "style_preset": request.style_preset,
            "prompt": request.prompt,
            "api_endpoint": self.api_endpoint,
            "api_key": self.api_key,
            "provider_name": self.external_provider_name,
            "model_version": self.external_model_version,
            "return_image_base64": "true",
            "local_output_path": str(output_image),
        }

    @staticmethod
    def _resolve_template_value(value: Any, values: dict[str, str]) -> Any:
        if not isinstance(value, str):
            return value
        result = value
        for key, replacement in values.items():
            result = result.replace(f"{{{{{key}}}}}", replacement)
        return result

    @staticmethod
    def _reference_image_base64(request: AnimeApiRequest) -> str:
        images = list(request.reference_images)
        if request.character_reference:
            images.insert(0, request.character_reference)
        for image in images:
            path = Path(image)
            if path.exists():
                return b64encode(path.read_bytes()).decode("ascii")
        return ""

    def _image_bytes(self, value: str) -> bytes:
        clean = value.strip()
        try:
            payload = json.loads(clean)
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            if payload.get("image_base64"):
                return b64decode(str(payload["image_base64"]))
            if payload.get("filename"):
                return self.client.view_image(
                    str(payload.get("filename") or ""),
                    subfolder=str(payload.get("subfolder") or ""),
                    image_type=str(payload.get("type") or "output"),
                )
        if clean.startswith("data:") and "," in clean:
            return b64decode(clean.split(",", 1)[1])
        path = Path(clean)
        if path.exists():
            return path.read_bytes()
        raise ValueError("ComfyUI output did not include image data")


class AnimeApiAdapter:
    def __init__(
        self,
        provider: AnimeProvider,
        output_dir: Path,
        metadata_dir: Path,
    ) -> None:
        self.provider = provider
        self.output_dir = Path(output_dir)
        self.metadata_dir = Path(metadata_dir)

    def stylize(self, request: AnimeApiRequest) -> AnimeApiResult:
        source = Path(request.source_image)
        if not source.exists():
            raise FileNotFoundError(f"source image not found: {source}")

        key = self._cache_key(request)
        suffix = source.suffix if source.suffix else ".png"
        output_image = self.output_dir / request.project_id / request.episode_id / f"{request.shot_id}-{key[:12]}{suffix}"
        metadata_path = self.metadata_dir / request.project_id / request.episode_id / f"{request.shot_id}-{key[:12]}.json"

        if output_image.exists() and metadata_path.exists():
            return AnimeApiResult(output_image=output_image, metadata_path=metadata_path, cache_hit=True)

        output_image.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self.provider.stylize(request, output_image)
        self._write_metadata(request, output_image, metadata_path, key, "succeeded")
        return AnimeApiResult(output_image=output_image, metadata_path=metadata_path, cache_hit=False)

    def _cache_key(self, request: AnimeApiRequest) -> str:
        payload = {
            "source_hash": self._sha256(Path(request.source_image)),
            "character_reference_hash": self._sha256(request.character_reference) if request.character_reference else "",
            "reference_image_hashes": [self._sha256(path) for path in request.reference_images if Path(path).exists()],
            "style_preset": request.style_preset,
            "prompt": request.prompt,
            "provider": self.provider.name,
            "model_version": self.provider.model_version,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _write_metadata(
        self,
        request: AnimeApiRequest,
        output_image: Path,
        metadata_path: Path,
        cache_key: str,
        status: str,
    ) -> None:
        metadata = {
            "provider": self.provider.name,
            "model_version": self.provider.model_version,
            "project_id": request.project_id,
            "episode_id": request.episode_id,
            "shot_id": request.shot_id,
            "source_image": str(Path(request.source_image)),
            "source_hash": self._sha256(Path(request.source_image)),
            "character_reference": str(request.character_reference) if request.character_reference else "",
            "reference_images": [str(path) for path in request.reference_images],
            "style_preset": request.style_preset,
            "prompt": request.prompt,
            "output_image": str(output_image),
            "cache_key": cache_key,
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "estimated_cost": 0,
        }
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
