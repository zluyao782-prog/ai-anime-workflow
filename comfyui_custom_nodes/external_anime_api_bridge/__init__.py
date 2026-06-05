from __future__ import annotations

import json
import mimetypes
import shutil
import uuid
from base64 import b64decode, b64encode
from pathlib import Path
from urllib import request as urllib_request


class ExternalAnimeStylize:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "source_image_path": ("STRING", {"default": "data/assets/source_frames/demo.png"}),
                "output_path": ("STRING", {"default": "data/assets/anime_frames/demo-anime.png"}),
                "style_preset": ("STRING", {"default": "clean_anime_drama"}),
                "prompt": ("STRING", {"default": "clean anime drama style", "multiline": True}),
                "api_endpoint": ("STRING", {"default": "https://aigate.zhixingjidian.cn/v1/images/edits"}),
                "api_key": ("STRING", {"default": ""}),
                "provider_name": ("STRING", {"default": "openai"}),
                "model_version": ("STRING", {"default": "gpt-image-2"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("anime_image_path",)
    FUNCTION = "stylize"
    CATEGORY = "AI Anime Workflow"
    OUTPUT_NODE = True

    def stylize(
        self,
        source_image_path: str,
        output_path: str,
        style_preset: str,
        prompt: str,
        api_endpoint: str,
        api_key: str,
        provider_name: str,
        model_version: str,
    ):
        source = Path(source_image_path)
        output = Path(output_path)
        if not source.exists():
            raise FileNotFoundError(f"source image not found: {source}")
        output.parent.mkdir(parents=True, exist_ok=True)

        if api_endpoint == "mock":
            shutil.copyfile(source, output)
            return (str(output),)

        if provider_name.lower() == "openai":
            body, content_type = self._openai_multipart_body(
                source=source,
                model=model_version,
                prompt=self._openai_prompt(prompt, style_preset),
            )
            http_request = urllib_request.Request(
                api_endpoint,
                data=body,
                headers={
                    "Content-Type": content_type,
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib_request.urlopen(http_request) as response:
                data = json.loads(response.read().decode("utf-8"))
            output.write_bytes(b64decode(data["data"][0]["b64_json"]))
            return (str(output),)

        payload = {
            "image_base64": b64encode(source.read_bytes()).decode("ascii"),
            "style_preset": style_preset,
            "prompt": prompt,
            "provider_name": provider_name,
            "model_version": model_version,
        }
        http_request = urllib_request.Request(
            api_endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib_request.urlopen(http_request) as response:
            data = json.loads(response.read().decode("utf-8"))
        output.write_bytes(b64decode(data["image_base64"]))
        return (str(output),)

    @staticmethod
    def _openai_prompt(prompt: str, style_preset: str) -> str:
        return "\n".join(
            [
                prompt,
                f"Style preset: {style_preset}.",
                "Transform the input frame into a consistent anime short-drama frame.",
                "Preserve composition and character identity while improving cinematic anime linework and lighting.",
            ]
        )

    @staticmethod
    def _openai_multipart_body(source: Path, model: str, prompt: str):
        boundary = f"----comfy-openai-{uuid.uuid4().hex}"
        mime_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        chunks = [
            f"--{boundary}\r\n".encode("ascii"),
            b'Content-Disposition: form-data; name="model"\r\n\r\n',
            model.encode("utf-8"),
            b"\r\n",
            f"--{boundary}\r\n".encode("ascii"),
            b'Content-Disposition: form-data; name="prompt"\r\n\r\n',
            prompt.encode("utf-8"),
            b"\r\n",
            f"--{boundary}\r\n".encode("ascii"),
            f'Content-Disposition: form-data; name="image"; filename="{source.name}"\r\n'.encode("ascii"),
            f"Content-Type: {mime_type}\r\n\r\n".encode("ascii"),
            source.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ]
        return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


NODE_CLASS_MAPPINGS = {
    "ExternalAnimeStylize": ExternalAnimeStylize,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ExternalAnimeStylize": "External Anime Stylize API",
}
