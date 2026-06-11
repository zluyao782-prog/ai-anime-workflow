from __future__ import annotations

import base64
import json
import mimetypes
import os
import subprocess
import sys
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.parse import unquote

from anime_workflow.imports.adaptation import build_episode_drafts, build_import_record, clean_source_text, split_short_video_episodes
from anime_workflow.imports.document_reader import extract_document_text
from anime_workflow.launcher.config import LauncherConfigStore, effective_comfyui_base_url
from anime_workflow.launcher.services import ComfyUIService, PROJECT_ROOT, environment_status, tail_file
from anime_workflow.jobs.runner import JobRunner
from anime_workflow.jobs.store import JobStore
from anime_workflow.projects.models import clamp_int, slug as project_slug
from anime_workflow.projects.store import ProjectStore
from anime_workflow.services.anime_api_adapter import ComfyUIAnimeProvider, MockAnimeProvider, OpenAIImageProvider
from anime_workflow.services.production_readiness import production_readiness
from anime_workflow.services.workflow_templates import list_workflow_templates, workflow_template_by_id
from anime_workflow.story.episode_runner import export_episode_video, generate_episode_images, generate_shot_image
from anime_workflow.story.storyboard import generate_storyboard, load_storyboard, save_storyboard, storyboard_path
from anime_workflow.story.providers import storyboard_provider_from_config
from anime_workflow.story.review import rewrite_storyboard_shot_local, snapshot_storyboard_review, update_storyboard_shot, validate_storyboard_for_review


CONFIG_PATH = PROJECT_ROOT / "config/settings.local.json"
STATIC_DIR = PROJECT_ROOT / "web/launcher"
WINDOWS_CJK_FONT = Path("/mnt/c/Windows/Fonts/msyh.ttc")
STORYBOARD_DIR = PROJECT_ROOT / "data/storyboards"
PROJECTS_DIR = PROJECT_ROOT / "data/projects"
JOBS_DIR = PROJECT_ROOT / "data/jobs"
IMPORTS_DIR = PROJECT_ROOT / "data/imports"
SOURCE_FRAME_DIR = PROJECT_ROOT / "data/assets/source_frames"
ANIME_FRAME_DIR = PROJECT_ROOT / "data/assets/anime_frames"
API_METADATA_DIR = PROJECT_ROOT / "data/assets/api_metadata"


class LauncherRequestHandler(BaseHTTPRequestHandler):
    server_version = "AIAnimeLauncher/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/fonts/msyh.ttc":
            self._serve_file(WINDOWS_CJK_FONT, "font/ttf")
            return
        if parsed.path == "/api/config":
            self._json({"config": self.config_store.load_public()})
            return
        if parsed.path == "/api/status":
            config = self.config_store.load()
            self._json({"status": environment_status(config), "config": self.config_store.load_public()})
            return
        if parsed.path == "/api/logs":
            query = parse_qs(parsed.query)
            service = query.get("service", ["launcher"])[0]
            if service == "comfyui":
                log_path = PROJECT_ROOT / "work/comfyui.log"
            else:
                log_path = PROJECT_ROOT / "work/launcher.log"
            self._json({"log": tail_file(log_path, 160)})
            return
        if parsed.path == "/api/episode":
            query = parse_qs(parsed.query)
            project_id = query.get("project_id", [""])[0]
            episode_id = query.get("episode_id", [""])[0]
            path = storyboard_path(STORYBOARD_DIR, project_id, episode_id)
            if not path.exists():
                self._json({"ok": False, "error": "storyboard not found", "path": str(path)}, HTTPStatus.NOT_FOUND)
                return
            self._json({"ok": True, "storyboard": load_storyboard(path), "storyboard_path": str(path)})
            return
        if parsed.path == "/api/outputs":
            exports_dir = Path(getattr(self.server, "exports_dir", configured_output_dir(self.config_store.load())))
            self._json({"ok": True, "outputs": self.project_store.list_outputs(exports_dir)})
            return
        if parsed.path == "/api/jobs":
            self._handle_job_list()
            return
        if parsed.path == "/api/production/readiness":
            self._json({"ok": True, "readiness": production_readiness(self.config_store.load(), PROJECT_ROOT)})
            return
        if parsed.path == "/api/workflow-templates":
            self._json({"ok": True, "templates": list_workflow_templates()})
            return
        if parsed.path.startswith("/api/jobs/"):
            self._handle_job_get(parsed.path)
            return
        if parsed.path == "/api/projects":
            self._handle_project_list()
            return
        if parsed.path.startswith("/api/projects/"):
            self._handle_project_get(parsed.path)
            return
        static_path = static_file_for_request(parsed.path, STATIC_DIR)
        if static_path:
            self._serve_file(static_path, content_type_for(static_path))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/config":
            body = self._read_json()
            self.config_store.save(body)
            self._json({"config": self.config_store.load_public()})
            return
        if parsed.path == "/api/comfyui/start":
            config = self.config_store.load()
            if str(config.get("comfyui_mode") or "local") == "remote":
                self._json({"status": "remote_configured", "base_url": effective_comfyui_base_url(config)})
                return
            self._json(ComfyUIService().start())
            return
        if parsed.path == "/api/comfyui/stop":
            config = self.config_store.load()
            if str(config.get("comfyui_mode") or "local") == "remote":
                self._json({"status": "remote_configured", "base_url": effective_comfyui_base_url(config)})
                return
            self._json(ComfyUIService().stop())
            return
        if parsed.path == "/api/openai/test":
            self._json(self._run_script("scripts/run_openai_image_workflow.py"))
            return
        if parsed.path == "/api/mock/test":
            self._json(self._run_script("scripts/run_mock_anime_workflow.py"))
            return
        if parsed.path == "/api/projects":
            self._handle_project_save()
            return
        if parsed.path == "/api/jobs":
            self._handle_job_create()
            return
        if parsed.path.startswith("/api/jobs/"):
            self._handle_job_post(parsed.path)
            return
        if parsed.path == "/api/imports/adapt":
            self._handle_import_adapt()
            return
        if parsed.path == "/api/storyboard/generate":
            self._handle_storyboard_generate()
            return
        if parsed.path == "/api/storyboard/save":
            self._handle_storyboard_save()
            return
        if parsed.path == "/api/storyboard/review/snapshot":
            self._handle_storyboard_review_snapshot()
            return
        if parsed.path == "/api/storyboard/shot/update":
            self._handle_storyboard_shot_update()
            return
        if parsed.path == "/api/storyboard/shot/rewrite":
            self._handle_storyboard_shot_rewrite()
            return
        if parsed.path == "/api/storyboard/shot/image":
            self._handle_storyboard_shot_image()
            return
        if parsed.path.startswith("/api/projects/"):
            self._handle_project_post(parsed.path)
            return
        if parsed.path == "/api/episode/storyboard":
            self._handle_episode_storyboard()
            return
        if parsed.path == "/api/episode/images":
            self._handle_episode_images()
            return
        if parsed.path == "/api/episode/video":
            self._handle_episode_video()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    @property
    def config_store(self) -> LauncherConfigStore:
        return LauncherConfigStore(CONFIG_PATH)

    @property
    def project_store(self) -> ProjectStore:
        return ProjectStore(Path(getattr(self.server, "projects_dir", PROJECTS_DIR)))

    @property
    def job_store(self) -> JobStore:
        store = getattr(self.server, "job_store", None)
        if store is None:
            store = JobStore(Path(getattr(self.server, "jobs_dir", JOBS_DIR)))
            self.server.job_store = store
        return store

    @property
    def job_runner(self) -> JobRunner:
        runner = getattr(self.server, "job_runner", None)
        if runner is None:
            runner = JobRunner(
                job_store=self.job_store,
                project_store=self.project_store,
                storyboard_dir=STORYBOARD_DIR,
                source_dir=SOURCE_FRAME_DIR,
                image_dir=ANIME_FRAME_DIR,
                metadata_dir=API_METADATA_DIR,
                output_dir=Path(getattr(self.server, "exports_dir", configured_output_dir(self.config_store.load()))),
                config_loader=self.config_store.load,
            )
            self.server.job_runner = runner
        return runner

    def _run_script(self, script: str) -> dict[str, Any]:
        config = self.config_store.load()
        env = os.environ.copy()
        if config.get("openai_api_key"):
            env["OPENAI_API_KEY"] = config["openai_api_key"]
        env["OPENAI_BASE_URL"] = config.get("openai_base_url", "https://aigate.zhixingjidian.cn")
        env["OPENAI_IMAGE_MODEL"] = config.get("openai_image_model", "gpt-image-2")
        command = [sys.executable, str(PROJECT_ROOT / script)]
        result = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            env=env,
            text=True,
            capture_output=True,
            timeout=180,
        )
        log_path = PROJECT_ROOT / "work/launcher.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"$ {' '.join(command)}\n")
            log.write(result.stdout)
            log.write(result.stderr)
            log.write(f"\nexit={result.returncode}\n")
        return {
            "ok": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def _handle_episode_storyboard(self) -> None:
        try:
            body = self._read_json()
            storyboard = generate_storyboard(body)
            path = save_storyboard(storyboard, STORYBOARD_DIR)
            self._json({"ok": True, "storyboard": storyboard, "storyboard_path": str(path)})
        except Exception as exc:
            self._json_error(exc)

    def _handle_episode_images(self) -> None:
        try:
            body = self._read_json()
            path = storyboard_path(STORYBOARD_DIR, body.get("project_id", ""), body.get("episode_id", ""))
            storyboard = load_storyboard(path)
            provider = self._image_provider_from_body(body)

            updated = generate_episode_images(
                storyboard=storyboard,
                provider=provider,
                source_dir=PROJECT_ROOT / "data/assets/source_frames",
                output_dir=PROJECT_ROOT / "data/assets/anime_frames",
                metadata_dir=PROJECT_ROOT / "data/assets/api_metadata",
            )
            saved = save_storyboard(updated, STORYBOARD_DIR)
            self._json({"ok": True, "storyboard": updated, "storyboard_path": str(saved), "provider": provider.name})
        except Exception as exc:
            self._json_error(exc)

    def _handle_episode_video(self) -> None:
        try:
            body = self._read_json()
            path = storyboard_path(STORYBOARD_DIR, body.get("project_id", ""), body.get("episode_id", ""))
            storyboard = load_storyboard(path)
            video = export_episode_video(storyboard, configured_output_dir(self.config_store.load()))
            storyboard["video_path"] = str(video)
            saved = save_storyboard(storyboard, STORYBOARD_DIR)
            self._json({"ok": True, "video_path": str(video), "storyboard": storyboard, "storyboard_path": str(saved)})
        except Exception as exc:
            self._json_error(exc)

    def _handle_project_list(self) -> None:
        try:
            self._json({"ok": True, "projects": self.project_store.list_projects()})
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._json_error(exc, HTTPStatus.NOT_FOUND)

    def _handle_job_list(self) -> None:
        try:
            if self.job_store.has_queued_jobs():
                self.job_runner.start()
            self._json({"ok": True, "jobs": self.job_store.list_jobs()})
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)

    def _handle_job_create(self) -> None:
        try:
            body = self._read_json()
            self._ensure_comfyui_job_confirmed(body)
            job = self.job_store.create_job(body)
            self.job_runner.start()
            self._json({"ok": True, "job": job})
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._json_error(exc, HTTPStatus.NOT_FOUND)

    def _handle_job_get(self, path: str) -> None:
        try:
            self._json({"ok": True, "job": self.job_store.get_job(job_id_from_api_path(path))})
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._json_error(exc, HTTPStatus.NOT_FOUND)

    def _handle_job_post(self, path: str) -> None:
        try:
            body = self._read_json()
            action = job_action_from_api_path(path)
            job_id = action["job_id"]
            if action["action"] == "cancel":
                self._json({"ok": True, "job": self.job_store.request_cancel(job_id)})
                return
            if action["action"] == "retry":
                self._ensure_comfyui_job_confirmed(self.job_store.get_job(job_id), body)
                job = self.job_store.retry_job(job_id, confirm_openai=body.get("confirm_openai") is True)
                self.job_runner.start()
                self._json({"ok": True, "job": job})
                return
            if action["action"] == "retry_failed":
                self._ensure_comfyui_job_confirmed(self.job_store.get_job(job_id), body)
                job = self.job_store.create_failed_retry_job(job_id, confirm_openai=body.get("confirm_openai") is True)
                self.job_runner.start()
                self._json({"ok": True, "job": job})
                return
            if action["action"] == "retry_episode":
                self._ensure_comfyui_job_confirmed(self.job_store.get_job(job_id), body)
                job = self.job_store.create_episode_retry_job(
                    job_id,
                    action["episode_id"],
                    confirm_openai=body.get("confirm_openai") is True,
                )
                self.job_runner.start()
                self._json({"ok": True, "job": job})
                return
            if action["action"] == "retry_episode_step":
                self._ensure_comfyui_job_confirmed(self.job_store.get_job(job_id), body)
                job = self.job_store.create_episode_step_retry_job(
                    job_id,
                    action["episode_id"],
                    action["step"],
                    confirm_openai=body.get("confirm_openai") is True,
                )
                self.job_runner.start()
                self._json({"ok": True, "job": job})
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._json_error(exc, HTTPStatus.NOT_FOUND)

    def _handle_project_get(self, path: str) -> None:
        try:
            project_id = project_id_from_api_path(path)
            suffix = project_api_suffix(path)
            if suffix == "":
                self._json({"ok": True, "project": self.project_store.get_project(project_id)})
                return
            if suffix == "characters":
                self._json({"ok": True, "characters": self.project_store.list_characters(project_id)})
                return
            if suffix == "styles":
                self._json({"ok": True, "styles": self.project_store.list_styles(project_id)})
                return
            if suffix == "references":
                self._json({"ok": True, "references": self.project_store.list_references(project_id)})
                return
            if suffix == "episodes":
                self._json({"ok": True, "episodes": self.project_store.list_episodes(project_id)})
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._json_error(exc, HTTPStatus.NOT_FOUND)

    def _handle_project_save(self) -> None:
        try:
            self._json({"ok": True, "project": self.project_store.save_project(self._read_json())})
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._json_error(exc, HTTPStatus.NOT_FOUND)

    def _handle_project_post(self, path: str) -> None:
        project_id = ""
        episode_id = ""
        try:
            body = self._read_json()
            project_id = project_id_from_api_path(path)
            suffix = project_api_suffix(path)
            production_route = project_episode_action_from_api_path(path)
            if production_route:
                _, episode_id, action = production_route
                if action == "storyboard":
                    self._handle_project_episode_storyboard(project_id, episode_id, body)
                    return
                if action == "images":
                    self._handle_project_episode_images(project_id, episode_id, body)
                    return
                if action == "video":
                    self._handle_project_episode_video(project_id, episode_id)
                    return
            if suffix == "":
                payload = dict(body)
                payload["project_id"] = project_id
                self._json({"ok": True, "project": self.project_store.save_project(payload)})
                return
            if suffix == "characters":
                self._json({"ok": True, "character": self.project_store.save_character(project_id, body)})
                return
            if suffix == "styles":
                self._json({"ok": True, "style": self.project_store.save_style(project_id, body)})
                return
            if suffix == "references":
                self._json({"ok": True, "reference": self.project_store.save_reference(project_id, body)})
                return
            if suffix == "episodes/batch":
                self._json({"ok": True, "episodes": self.project_store.create_episode_batch(project_id, body)})
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._json_error(exc, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._mark_episode_failed(project_id, episode_id, exc)
            self._json_error(exc, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_project_episode_storyboard(self, project_id: str, episode_id: str, body: dict[str, Any] | None = None) -> None:
        body = body or {}
        values = self.project_store.build_storyboard_values(project_id, episode_id)
        storyboard = self._generate_storyboard_from_values(values, body)
        path = save_storyboard(storyboard, STORYBOARD_DIR)
        episode = self.project_store.update_episode(
            project_id,
            episode_id,
            {"status": "storyboarded", "storyboard_path": str(path), "error": ""},
        )
        self._json({"ok": True, "storyboard": storyboard, "episode": episode, "storyboard_path": str(path)})

    def _handle_storyboard_generate(self) -> None:
        try:
            body = self._read_json()
            project_id = str(body.get("project_id") or "").strip()
            episode_id = str(body.get("episode_id") or "").strip()
            values = self.project_store.build_storyboard_values(project_id, episode_id)
            storyboard = self._generate_storyboard_from_values(values, body)
            path = save_storyboard(storyboard, STORYBOARD_DIR)
            episode = self.project_store.update_episode(
                project_id,
                episode_id,
                {"status": "storyboarded", "storyboard_path": str(path), "error": ""},
            )
            self._json({"ok": True, "storyboard": storyboard, "episode": episode, "storyboard_path": str(path)})
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._json_error(exc, HTTPStatus.NOT_FOUND)

    def _handle_storyboard_save(self) -> None:
        try:
            body = self._read_json()
            project_id = str(body.get("project_id") or "").strip()
            episode_id = str(body.get("episode_id") or "").strip()
            storyboard = validate_storyboard_for_review(dict(body.get("storyboard") or {}))
            storyboard["project_id"] = project_id
            storyboard["episode_id"] = episode_id
            path = save_storyboard(storyboard, STORYBOARD_DIR)
            episode = self.project_store.update_episode(
                project_id,
                episode_id,
                {"status": "storyboarded", "storyboard_path": str(path), "error": ""},
            )
            self._json({"ok": True, "storyboard": storyboard, "episode": episode, "storyboard_path": str(path)})
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._json_error(exc, HTTPStatus.NOT_FOUND)

    def _handle_storyboard_shot_update(self) -> None:
        try:
            body = self._read_json()
            project_id = str(body.get("project_id") or "").strip()
            episode_id = str(body.get("episode_id") or "").strip()
            shot_id = str(body.get("shot_id") or "").strip()
            path = storyboard_path(STORYBOARD_DIR, project_id, episode_id)
            storyboard = update_storyboard_shot(load_storyboard(path), shot_id, dict(body.get("updates") or {}))
            saved = save_storyboard(storyboard, STORYBOARD_DIR)
            self.project_store.update_episode(project_id, episode_id, {"status": "storyboarded", "storyboard_path": str(saved), "error": ""})
            self._json({"ok": True, "storyboard": storyboard, "storyboard_path": str(saved)})
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._json_error(exc, HTTPStatus.NOT_FOUND)

    def _handle_storyboard_review_snapshot(self) -> None:
        try:
            body = self._read_json()
            project_id = str(body.get("project_id") or "").strip()
            episode_id = str(body.get("episode_id") or "").strip()
            path = storyboard_path(STORYBOARD_DIR, project_id, episode_id)
            storyboard = snapshot_storyboard_review(load_storyboard(path), str(body.get("note") or ""))
            saved = save_storyboard(storyboard, STORYBOARD_DIR)
            episode = self.project_store.update_episode(
                project_id,
                episode_id,
                {"status": "storyboarded", "storyboard_path": str(saved), "error": ""},
            )
            self._json({"ok": True, "storyboard": storyboard, "episode": episode, "storyboard_path": str(saved)})
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._json_error(exc, HTTPStatus.NOT_FOUND)

    def _handle_storyboard_shot_rewrite(self) -> None:
        try:
            body = self._read_json()
            project_id = str(body.get("project_id") or "").strip()
            episode_id = str(body.get("episode_id") or "").strip()
            shot_id = str(body.get("shot_id") or "").strip()
            provider = str(body.get("provider") or "local").lower()
            if provider == "openai":
                if body.get("confirm_openai") is not True:
                    raise ValueError("openai storyboard provider requires confirmation")
                self._json_error(ValueError("openai shot rewrite is not implemented yet"), HTTPStatus.NOT_IMPLEMENTED)
                return
            path = storyboard_path(STORYBOARD_DIR, project_id, episode_id)
            storyboard = rewrite_storyboard_shot_local(load_storyboard(path), shot_id, str(body.get("instruction") or ""))
            saved = save_storyboard(storyboard, STORYBOARD_DIR)
            self.project_store.update_episode(project_id, episode_id, {"status": "storyboarded", "storyboard_path": str(saved), "error": ""})
            self._json({"ok": True, "storyboard": storyboard, "storyboard_path": str(saved)})
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._json_error(exc, HTTPStatus.NOT_FOUND)

    def _handle_storyboard_shot_image(self) -> None:
        try:
            body = self._read_json()
            project_id = str(body.get("project_id") or "").strip()
            episode_id = str(body.get("episode_id") or "").strip()
            shot_id = str(body.get("shot_id") or "").strip()
            path = storyboard_path(STORYBOARD_DIR, project_id, episode_id)
            template = workflow_template_by_id(str(body.get("workflow_template") or "mock_image"))
            provider = self._image_provider_from_body(body)
            storyboard = generate_shot_image(
                storyboard=load_storyboard(path),
                shot_id=shot_id,
                provider=provider,
                source_dir=SOURCE_FRAME_DIR,
                output_dir=ANIME_FRAME_DIR,
                metadata_dir=API_METADATA_DIR,
                references=self.project_store.list_references(project_id),
                workflow_template=template["template_id"],
            )
            saved = save_storyboard(storyboard, STORYBOARD_DIR)
            episode = self.project_store.update_episode(
                project_id,
                episode_id,
                {"status": "imaged", "storyboard_path": str(saved), "error": ""},
            )
            self._json({"ok": True, "storyboard": storyboard, "episode": episode, "storyboard_path": str(saved), "provider": provider.name})
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._json_error(exc, HTTPStatus.NOT_FOUND)

    def _handle_import_adapt(self) -> None:
        try:
            body = self._read_json()
            filename = str(body.get("filename") or "source.txt")
            text = self._document_text_from_body(body, filename)
            cleaned = clean_source_text(text)
            duration_seconds = clamp_int(body.get("duration_seconds"), 30, 180, 60)
            shot_count = clamp_int(body.get("shot_count"), 1, 24, 8)
            max_episodes = clamp_int(body.get("max_episodes"), 1, 50, 10)
            storyboard_provider_name = str(body.get("storyboard_provider") or "local").lower()
            provider = storyboard_provider_from_config(
                self.config_store.load(),
                storyboard_provider_name,
                confirm_openai=body.get("confirm_openai") is True,
            )
            project = self.project_store.save_project(
                {
                    "project_id": body.get("project_id") or body.get("project_name") or "adapted_project",
                    "name": body.get("project_name") or body.get("project_id") or "导入改编项目",
                    "genre": body.get("genre") or "悬疑",
                    "platform": body.get("platform") or "douyin",
                    "premise": cleaned[:240],
                    "default_duration_seconds": duration_seconds,
                    "default_shot_count": shot_count,
                    "default_style_id": body.get("style_id") or "clean_anime_drama",
                }
            )
            chunks = split_short_video_episodes(cleaned, duration_seconds, max_episodes)
            drafts = build_episode_drafts(chunks, duration_seconds, shot_count)
            episodes = [self.project_store.save_episode(project["project_id"], draft) for draft in drafts]
            storyboarded = []
            for episode in episodes:
                values = self.project_store.build_storyboard_values(project["project_id"], episode["episode_id"])
                if episode.get("source_excerpt"):
                    values["premise"] = f"{values.get('premise', '')}。原文片段：{episode['source_excerpt']}".strip("。")
                storyboard = provider.generate(values)
                path = save_storyboard(storyboard, STORYBOARD_DIR)
                storyboarded.append(
                    self.project_store.update_episode(
                        project["project_id"],
                        episode["episode_id"],
                        {"status": "storyboarded", "storyboard_path": str(path), "error": ""},
                    )
                )
            import_id = f"import_{uuid.uuid4().hex[:12]}"
            imports_dir = Path(getattr(self.server, "imports_dir", IMPORTS_DIR))
            cleaned_path = imports_dir / f"{import_id}.txt"
            cleaned_path.parent.mkdir(parents=True, exist_ok=True)
            cleaned_path.write_text(cleaned, encoding="utf-8")
            record = build_import_record(
                import_id=import_id,
                project_id=project["project_id"],
                filename=filename,
                content_type=content_type_for_filename(filename),
                cleaned_text_path=str(cleaned_path),
                text_length=len(cleaned),
                episode_ids=[episode["episode_id"] for episode in storyboarded],
                settings={
                    "platform": project["platform"],
                    "duration_seconds": duration_seconds,
                    "shot_count": shot_count,
                    "max_episodes": max_episodes,
                    "segmentation_mode": "short_video",
                    "storyboard_provider": storyboard_provider_name,
                },
            )
            (imports_dir / f"{record['import_id']}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            self._json({"ok": True, "import": record, "project": project, "episodes": storyboarded})
        except ValueError as exc:
            self._json_error(exc, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._json_error(exc, HTTPStatus.NOT_FOUND)

    def _document_text_from_body(self, body: dict[str, Any], filename: str) -> str:
        if body.get("text"):
            return extract_document_text(filename, str(body["text"]).encode("utf-8"))
        encoded = str(body.get("content_base64") or "")
        if not encoded:
            raise ValueError("document text is empty")
        return extract_document_text(filename, base64.b64decode(encoded))

    def _generate_storyboard_from_values(self, values: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
        provider = storyboard_provider_from_config(
            self.config_store.load(),
            str(body.get("provider") or body.get("storyboard_provider") or "local"),
            confirm_openai=body.get("confirm_openai") is True,
        )
        return provider.generate(values)

    def _handle_project_episode_images(self, project_id: str, episode_id: str, body: dict[str, Any]) -> None:
        storyboard_file = storyboard_path(STORYBOARD_DIR, project_id, episode_id)
        storyboard = load_storyboard(storyboard_file)
        provider = self._image_provider_from_body(body)

        updated = generate_episode_images(
            storyboard=storyboard,
            provider=provider,
            source_dir=SOURCE_FRAME_DIR,
            output_dir=ANIME_FRAME_DIR,
            metadata_dir=API_METADATA_DIR,
            references=self.project_store.list_references(project_id),
        )
        saved = save_storyboard(updated, STORYBOARD_DIR)
        episode = self.project_store.update_episode(
            project_id,
            episode_id,
            {"status": "imaged", "storyboard_path": str(saved), "error": ""},
        )
        self._json({"ok": True, "storyboard": updated, "episode": episode, "storyboard_path": str(saved), "provider": provider.name})

    def _image_provider_from_body(self, body: dict[str, Any]):
        config = self.config_store.load()
        provider_name = str(body.get("provider") or "mock").lower()
        if provider_name == "comfyui":
            template = workflow_template_by_id(str(body.get("workflow_template") or "comfyui_external_anime"))
            return self._comfyui_image_provider(config, template, confirm_openai=body.get("confirm_openai") is True)
        if provider_name == "openai":
            if body.get("confirm_openai") is not True:
                raise ValueError("openai provider requires confirmation")
            api_key = config.get("openai_api_key", "")
            if not api_key:
                raise ValueError("OpenAI API Key is not configured")
            return OpenAIImageProvider(
                api_key=api_key,
                model=config.get("openai_image_model", "gpt-image-2"),
                endpoint=config.get("openai_base_url", "https://aigate.zhixingjidian.cn"),
            )
        return MockAnimeProvider()

    def _ensure_comfyui_job_confirmed(self, job: dict[str, Any], body: dict[str, Any] | None = None) -> None:
        if str(job.get("provider") or "").lower() != "comfyui":
            return
        config = self.config_store.load()
        if not str(config.get("openai_api_key") or ""):
            return
        confirm_openai = (body if body is not None else job).get("confirm_openai") is True
        if not confirm_openai:
            raise ValueError("comfyui openai route requires confirmation")

    def _comfyui_image_provider(
        self,
        config: dict[str, Any],
        template: dict[str, Any],
        confirm_openai: bool = False,
    ) -> ComfyUIAnimeProvider:
        api_key = str(config.get("openai_api_key") or "")
        external_provider = "openai" if api_key else "mock"
        if external_provider == "openai" and confirm_openai is not True:
            raise ValueError("comfyui openai route requires confirmation")
        endpoint = str(config.get("openai_base_url") or "mock")
        if external_provider == "openai" and not endpoint.rstrip("/").endswith("/images/edits"):
            endpoint = f"{endpoint.rstrip('/')}/v1/images/edits"
        return ComfyUIAnimeProvider(
            base_url=effective_comfyui_base_url(config),
            api_endpoint=endpoint if external_provider == "openai" else "mock",
            api_key=api_key,
            provider_name=external_provider,
            model_version=str(config.get("openai_image_model") or "gpt-image-2"),
            workflow_template=template,
        )

    def _handle_project_episode_video(self, project_id: str, episode_id: str) -> None:
        storyboard = load_storyboard(storyboard_path(STORYBOARD_DIR, project_id, episode_id))
        video = export_episode_video(storyboard, configured_output_dir(self.config_store.load()))
        storyboard["video_path"] = str(video)
        save_storyboard(storyboard, STORYBOARD_DIR)
        episode = self.project_store.update_episode(
            project_id,
            episode_id,
            {"status": "exported", "video_path": str(video), "error": ""},
        )
        self._json({"ok": True, "video_path": str(video), "storyboard": storyboard, "episode": episode})

    def _mark_episode_failed(self, project_id: str, episode_id: str, exc: Exception) -> None:
        if not project_id or not episode_id:
            return
        try:
            self.project_store.update_episode(project_id, episode_id, {"status": "failed", "error": str(exc)})
        except Exception:
            return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _json(self, data: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _json_error(self, exc: Exception, status: HTTPStatus = HTTPStatus.BAD_REQUEST) -> None:
        self._json({"ok": False, "error": str(exc)}, status)

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        payload = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        log_path = PROJECT_ROOT / "work/launcher.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(format % args + "\n")


def run(host: str = "127.0.0.1", port: int = 7860) -> None:
    server = ThreadingHTTPServer((host, port), LauncherRequestHandler)
    server.job_store = JobStore(JOBS_DIR)
    server.job_store.recover_interrupted_jobs()
    server.job_runner = JobRunner(
        job_store=server.job_store,
        project_store=ProjectStore(PROJECTS_DIR),
        storyboard_dir=STORYBOARD_DIR,
        source_dir=SOURCE_FRAME_DIR,
        image_dir=ANIME_FRAME_DIR,
        metadata_dir=API_METADATA_DIR,
        output_dir=configured_output_dir(LauncherConfigStore(CONFIG_PATH).load()),
        config_loader=LauncherConfigStore(CONFIG_PATH).load,
    )
    if server.job_store.has_queued_jobs():
        server.job_runner.start()
    print(f"AI Anime Launcher running at http://{host}:{port}")
    server.serve_forever()


def static_file_for_request(path: str, static_dir: Path = STATIC_DIR) -> Path | None:
    if path.startswith("/api/") or path.startswith("/fonts/"):
        return None
    relative = unquote(path).lstrip("/")
    if not relative:
        relative = "index.html"
    candidate = (static_dir / relative).resolve()
    root = static_dir.resolve()
    if not candidate.is_relative_to(root):
        return None
    if not candidate.is_file():
        return None
    return candidate


def project_api_parts(path: str) -> list[str]:
    return [unquote(part) for part in path.split("/") if part]


def project_id_from_api_path(path: str) -> str:
    parts = project_api_parts(path)
    if len(parts) < 3 or parts[0] != "api" or parts[1] != "projects":
        raise ValueError("project_id is required")
    project_id = parts[2].strip()
    if not project_id:
        raise ValueError("project_id is required")
    if project_id != project_slug(project_id, ""):
        raise ValueError("project_id is invalid")
    return project_id


def project_api_suffix(path: str) -> str:
    parts = project_api_parts(path)
    if len(parts) <= 3:
        return ""
    return "/".join(part.strip() for part in parts[3:])


def project_episode_action_from_api_path(path: str) -> tuple[str, str, str] | None:
    raw_parts = path.split("/")
    if raw_parts and raw_parts[0] == "":
        raw_parts = raw_parts[1:]
    parts = [unquote(part) for part in raw_parts]
    if len(parts) != 6:
        return None
    if parts[0] != "api" or parts[1] != "projects" or parts[3] != "episodes":
        return None
    if any(not part.strip() for part in parts):
        return None
    episode_id = parts[4].strip()
    if episode_id != project_slug(episode_id, ""):
        raise ValueError("episode_id is invalid")
    action = parts[5].strip()
    if action not in {"storyboard", "images", "video"}:
        return None
    return parts[2].strip(), episode_id, action


def job_id_from_api_path(path: str) -> str:
    parts = project_api_parts(path)
    if len(parts) != 3 or parts[0] != "api" or parts[1] != "jobs":
        raise ValueError("job path is invalid")
    job_id = parts[2].strip()
    if not job_id:
        raise ValueError("job_id is required")
    return job_id


def job_action_from_api_path(path: str) -> dict[str, str]:
    parts = project_api_parts(path)
    if len(parts) < 4 or parts[0] != "api" or parts[1] != "jobs":
        raise ValueError("job path is invalid")
    job_id = parts[2].strip()
    if not job_id:
        raise ValueError("job_id is required")

    if len(parts) == 4:
        action = parts[3].strip()
        if action == "cancel":
            return {"job_id": job_id, "action": "cancel"}
        if action == "retry":
            return {"job_id": job_id, "action": "retry"}
        if action == "retry-failed":
            return {"job_id": job_id, "action": "retry_failed"}
        raise ValueError("job action is invalid")

    if len(parts) == 6 and parts[3] == "episodes" and parts[5] == "retry":
        episode_id = parts[4].strip()
        if not episode_id:
            raise ValueError("episode_id is required")
        return {"job_id": job_id, "action": "retry_episode", "episode_id": episode_id}

    if len(parts) == 8 and parts[3] == "episodes" and parts[5] == "steps" and parts[7] == "retry":
        episode_id = parts[4].strip()
        step = parts[6].strip()
        if not episode_id:
            raise ValueError("episode_id is required")
        if step not in {"storyboard", "images", "video"}:
            raise ValueError("invalid step")
        return {"job_id": job_id, "action": "retry_episode_step", "episode_id": episode_id, "step": step}

    raise ValueError("job action is invalid")


def content_type_for(path: Path) -> str:
    if path.suffix == ".js":
        return "application/javascript; charset=utf-8"
    if path.suffix == ".css":
        return "text/css; charset=utf-8"
    if path.suffix == ".html":
        return "text/html; charset=utf-8"
    guessed = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return guessed


def content_type_for_filename(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def configured_output_dir(config: dict[str, Any]) -> Path:
    path = Path(str(config.get("output_dir") or "data/exports"))
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


if __name__ == "__main__":
    run()
