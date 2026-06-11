from __future__ import annotations

from typing import Any


BUILTIN_WORKFLOW_TEMPLATES = [
    {
        "template_id": "mock_image",
        "name": "Mock Image",
        "provider": "mock",
        "description": "Use the local mock provider for fast review without API cost.",
    },
    {
        "template_id": "openai_image",
        "name": "OpenAI Image",
        "provider": "openai",
        "description": "Route the shot through the configured OpenAI-compatible image endpoint.",
    },
    {
        "template_id": "comfyui_external_anime",
        "name": "ComfyUI External Anime",
        "provider": "comfyui",
        "description": "Route the shot through the configured local or remote ComfyUI ExternalAnimeStylize workflow.",
        "comfyui": {
            "node_id": "1",
            "class_type": "ExternalAnimeStylize",
            "return_image_base64": True,
            "inputs": {
                "source_image_path": "",
                "source_image_base64": "{{source_image_base64}}",
                "reference_image_base64": "{{reference_image_base64}}",
                "output_path": "{{remote_output_path}}",
                "style_preset": "{{style_preset}}",
                "prompt": "{{prompt}}",
                "api_endpoint": "{{api_endpoint}}",
                "api_key": "{{api_key}}",
                "provider_name": "{{provider_name}}",
                "model_version": "{{model_version}}",
                "return_image_base64": "{{return_image_base64}}",
            },
        },
    },
]


def list_workflow_templates() -> list[dict[str, Any]]:
    return [dict(template) for template in BUILTIN_WORKFLOW_TEMPLATES]


def workflow_template_by_id(template_id: str) -> dict[str, Any]:
    clean = str(template_id or "mock_image").strip()
    for template in BUILTIN_WORKFLOW_TEMPLATES:
        if template["template_id"] == clean:
            return dict(template)
    raise ValueError("workflow_template is invalid")
