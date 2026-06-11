#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import urllib.error
import urllib.request
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from anime_workflow.jobs.models import DEFAULT_WORKFLOW_TEMPLATES

BASE_URL = "http://127.0.0.1:7860"
TIMEOUT_SECONDS = 30


def get_json(path: str) -> dict[str, Any]:
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def print_json(label: str, payload: dict[str, Any]) -> None:
    print(f"{label}:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a guarded production loop smoke against the local launcher API.")
    parser.add_argument("--provider", choices=("mock", "openai", "comfyui"), default="mock")
    parser.add_argument(
        "--workflow-template",
        default=None,
        help="Workflow template to send. Defaults to the selected provider's template.",
    )
    parser.add_argument("--confirm-openai", action="store_true")
    parser.add_argument("--project-id", default="smoke_production")
    parser.add_argument("--episode-id", default="episode_001")
    args = parser.parse_args(argv)
    if args.workflow_template is None:
        args.workflow_template = DEFAULT_WORKFLOW_TEMPLATES[args.provider]
    return args


def main() -> int:
    args = parse_args()
    if args.provider in {"openai", "comfyui"} and not args.confirm_openai:
        print("--confirm-openai is required for openai or comfyui smoke runs", file=sys.stderr)
        return 2

    project_payload = {
        "project_id": args.project_id,
        "name": "Production Smoke Project",
        "genre": "smoke",
        "premise": "Guarded smoke test for the local production loop.",
        "default_shot_count": 1,
        "default_duration_seconds": 3,
    }

    try:
        readiness = get_json("/api/production/readiness")
        print_json("readiness", readiness)

        project = post_json("/api/projects", project_payload)
        print_json("project", project)

        batch = post_json(f"/api/projects/{args.project_id}/episodes/batch", {"count": 1})
        print_json("episode_batch", batch)

        storyboard = post_json(f"/api/projects/{args.project_id}/episodes/{args.episode_id}/storyboard", {})
        print_json("storyboard", storyboard)

        images = post_json(
            f"/api/projects/{args.project_id}/episodes/{args.episode_id}/images",
            {
                "provider": args.provider,
                "workflow_template": args.workflow_template,
                "confirm_openai": args.confirm_openai,
            },
        )
        print_json("images", images)

        video = post_json(f"/api/projects/{args.project_id}/episodes/{args.episode_id}/video", {})
        print_json("video", video)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code} for {exc.url}: {body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"launcher request failed: {exc.reason}", file=sys.stderr)
        return 1

    print(f"storyboard_path={storyboard.get('storyboard_path', '')}")
    print(f"provider={images.get('provider', args.provider)}")
    print(f"video_path={video.get('video_path', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
