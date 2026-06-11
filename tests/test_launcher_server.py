import unittest
import tempfile
import base64
import json
import os
import threading
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib import error, request

import anime_workflow.launcher.server as launcher_server
from anime_workflow.launcher.server import LauncherRequestHandler, project_id_from_api_path, static_file_for_request
from anime_workflow.services.workflow_templates import workflow_template_by_id
from anime_workflow.story.storyboard import generate_storyboard, save_storyboard


class NoopRunner:
    def __init__(self) -> None:
        self.started = 0

    def start(self) -> bool:
        self.started += 1
        return True


class LauncherServerTest(unittest.TestCase):
    def request_json(self, server: ThreadingHTTPServer, path: str, body: dict | None = None) -> tuple[int, dict]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        http_request = request.Request(
            f"http://127.0.0.1:{server.server_port}{path}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST" if body is not None else "GET",
        )
        opener = request.build_opener(request.ProxyHandler({}))
        try:
            with opener.open(http_request, timeout=3) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            payload = exc.read().decode("utf-8")
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                data = {"error": payload}
            return exc.code, data

    def with_server(
        self,
        projects_dir: Path,
        exports_dir: Path | None = None,
        jobs_dir: Path | None = None,
        job_runner: NoopRunner | None = None,
    ) -> tuple[ThreadingHTTPServer, threading.Thread]:
        server = ThreadingHTTPServer(("127.0.0.1", 0), LauncherRequestHandler)
        server.projects_dir = projects_dir
        if exports_dir is not None:
            server.exports_dir = exports_dir
        if jobs_dir is not None:
            server.jobs_dir = jobs_dir
        if job_runner is not None:
            server.job_runner = job_runner
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def stop_server(self, server: ThreadingHTTPServer, thread: threading.Thread) -> None:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    def stop_server_with_paths(
        self,
        server: ThreadingHTTPServer,
        thread: threading.Thread,
        previous_storyboard_dir: Path,
        previous_config_path: Path,
    ) -> None:
        self.stop_server(server, thread)
        launcher_server.STORYBOARD_DIR = previous_storyboard_dir
        launcher_server.CONFIG_PATH = previous_config_path

    def test_static_file_for_request_resolves_vite_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            static_dir = Path(tmp)
            asset = static_dir / "assets/index-abc123.js"
            asset.parent.mkdir()
            asset.write_text("console.log('ok')", encoding="utf-8")

            path = static_file_for_request("/assets/index-abc123.js", static_dir)

            self.assertEqual(path, asset.resolve())

    def test_static_file_for_request_blocks_path_traversal(self):
        static_dir = Path("/project/web/launcher")

        self.assertIsNone(static_file_for_request("/../config/settings.local.json", static_dir))

    def test_project_id_from_api_path_extracts_nested_resource(self):
        self.assertEqual(project_id_from_api_path("/api/projects/demo/characters"), "demo")
        self.assertEqual(project_id_from_api_path("/api/projects/demo/episodes/episode_001/video"), "demo")
        self.assertEqual(project_id_from_api_path("/api/projects/rain_detective/styles"), "rain_detective")

    def test_project_id_from_api_path_rejects_invalid_project_id(self):
        invalid_paths = [
            "/api/projects/%20/characters",
            "/api/projects/rain%20detective/styles",
            "/api/projects/%2F/characters",
            "/api/projects/../characters",
            "/api/projects/!!!/characters",
        ]
        for path in invalid_paths:
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "project_id is"):
                project_id_from_api_path(path)

    def test_project_api_creates_lists_and_reads_project_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                status, created = self.request_json(
                    server,
                    "/api/projects",
                    {
                        "project_id": "demo",
                        "name": "示例项目",
                        "genre": "悬疑",
                        "platform": "douyin",
                        "premise": "雨夜匿名信",
                        "default_shot_count": 4,
                    },
                )
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(created["ok"])
                self.assertEqual(created["project"]["project_id"], "demo")

                status, updated = self.request_json(server, "/api/projects/demo", {"name": "示例项目更新"})
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(updated["ok"])
                self.assertEqual(updated["project"]["name"], "示例项目更新")

                status, projects = self.request_json(server, "/api/projects")
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(projects["ok"])
                self.assertEqual([item["project_id"] for item in projects["projects"]], ["demo"])

                status, detail = self.request_json(server, "/api/projects/demo")
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(detail["ok"])
                self.assertEqual(detail["project"]["name"], "示例项目更新")

                status, character = self.request_json(
                    server,
                    "/api/projects/demo/characters",
                    {"character_id": "hero", "name": "林夏", "role": "侦探"},
                )
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(character["ok"])
                self.assertEqual(character["character"]["character_id"], "hero")

                status, style = self.request_json(
                    server,
                    "/api/projects/demo/styles",
                    {"style_id": "dark", "name": "暗色悬疑", "base_prompt": "cinematic anime"},
                )
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(style["ok"])
                self.assertEqual(style["style"]["style_id"], "dark")

                status, characters = self.request_json(server, "/api/projects/demo/characters")
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(characters["ok"])
                self.assertEqual([item["character_id"] for item in characters["characters"]], ["hero"])

                status, styles = self.request_json(server, "/api/projects/demo/styles")
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(styles["ok"])
                self.assertEqual([item["style_id"] for item in styles["styles"]], ["dark"])

                status, reference = self.request_json(
                    server,
                    "/api/projects/demo/references",
                    {
                        "reference_id": "rain_alley",
                        "reference_type": "location",
                        "name": "雨夜小巷",
                        "prompt_fragment": "rainy narrow alley",
                    },
                )
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(reference["ok"])
                self.assertEqual(reference["reference"]["reference_id"], "rain_alley")

                status, references = self.request_json(server, "/api/projects/demo/references")
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(references["ok"])
                self.assertEqual([item["reference_id"] for item in references["references"]], ["rain_alley"])

                status, batch = self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 2})
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(batch["ok"])
                self.assertEqual([item["episode_no"] for item in batch["episodes"]], [1, 2])

                status, episodes = self.request_json(server, "/api/projects/demo/episodes")
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(episodes["ok"])
                self.assertEqual([item["episode_id"] for item in episodes["episodes"]], ["episode_001", "episode_002"])
            finally:
                self.stop_server(server, thread)

    def test_workflow_templates_api_lists_builtin_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                status, payload = self.request_json(server, "/api/workflow-templates")
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(payload["ok"])
                self.assertIn("comfyui_external_anime", [item["template_id"] for item in payload["templates"]])
            finally:
                self.stop_server(server, thread)

    def test_workflow_templates_include_cost_and_route_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                status, response = self.request_json(server, "/api/workflow-templates")
                self.assertEqual(status, HTTPStatus.OK)
                templates = {template["template_id"]: template for template in response["templates"]}

                comfyui = templates["comfyui_external_anime"]
                self.assertEqual(comfyui["provider"], "comfyui")
                self.assertEqual(comfyui["external_provider"], "openai")
                self.assertTrue(comfyui["consumes_api"])
                self.assertTrue(comfyui["requires_openai_confirmation"])
                self.assertEqual(comfyui["route"], "comfyui_openai_image")
                self.assertIn("ComfyUI", comfyui["route_summary"])
            finally:
                self.stop_server(server, thread)

    def test_workflow_template_by_id_returns_deep_copy(self):
        template = workflow_template_by_id("comfyui_external_anime")
        template["comfyui"]["inputs"]["api_key"] = "mutated"

        fresh = workflow_template_by_id("comfyui_external_anime")

        self.assertEqual(fresh["comfyui"]["inputs"]["api_key"], "{{api_key}}")

    def test_production_readiness_api_reports_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_config_path = launcher_server.CONFIG_PATH
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                self.request_json(server, "/api/config", {"openai_api_key": "sk-test"})

                readiness = {"ok": True, "checks": {"openai": {"ok": True}}}
                with mock.patch("anime_workflow.launcher.server.production_readiness", return_value=readiness):
                    status, payload = self.request_json(server, "/api/production/readiness")

                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(payload["ok"])
                self.assertTrue(payload["readiness"]["ok"])
            finally:
                self.stop_server(server, thread)
                launcher_server.CONFIG_PATH = previous_config_path

    def test_project_api_returns_404_for_missing_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                status, payload = self.request_json(server, "/api/projects/missing")
                self.assertEqual(status, HTTPStatus.NOT_FOUND)
                self.assertIn("project not found", payload["error"])
            finally:
                self.stop_server(server, thread)

    def test_project_api_returns_400_for_empty_project_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                status, payload = self.request_json(server, "/api/projects/%20/characters")
                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertIn("project_id is required", payload["error"])
            finally:
                self.stop_server(server, thread)

    def test_outputs_api_lists_exported_videos(self):
        with tempfile.TemporaryDirectory() as tmp:
            exports = Path(tmp) / "exports"
            exports.mkdir()
            old_video = exports / "demo-episode_000.mp4"
            old_video.write_bytes(b"old video")
            video = exports / "demo-episode_001.mp4"
            video.write_bytes(b"video")
            old_mtime = 1_700_000_000
            new_mtime = 1_700_000_100
            os.utime(old_video, (old_mtime, old_mtime))
            os.utime(video, (new_mtime, new_mtime))
            server, thread = self.with_server(Path(tmp) / "projects", exports)
            try:
                status, payload = self.request_json(server, "/api/outputs")

                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(payload["ok"])
                self.assertEqual([item["filename"] for item in payload["outputs"]], ["demo-episode_001.mp4", "demo-episode_000.mp4"])
                self.assertEqual(payload["outputs"][0]["video_path"], str(video))
                self.assertEqual(payload["outputs"][0]["size_bytes"], 5)
                self.assertEqual(payload["outputs"][0]["updated_at"], new_mtime)
            finally:
                self.stop_server(server, thread)

    def test_outputs_api_uses_configured_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_config_path = launcher_server.CONFIG_PATH
            config_path = Path(tmp) / "config/settings.local.json"
            configured_exports = Path(tmp) / "configured_exports"
            configured_exports.mkdir()
            video = configured_exports / "configured.mp4"
            video.write_bytes(b"video")
            config_path.parent.mkdir(parents=True)
            config_path.write_text(json.dumps({"output_dir": str(configured_exports)}), encoding="utf-8")
            launcher_server.CONFIG_PATH = config_path
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                status, payload = self.request_json(server, "/api/outputs")

                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual([item["filename"] for item in payload["outputs"]], ["configured.mp4"])
            finally:
                self.stop_server(server, thread)
                launcher_server.CONFIG_PATH = previous_config_path

    def test_comfyui_start_is_noop_in_remote_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_config_path = launcher_server.CONFIG_PATH
            config_path = Path(tmp) / "config/settings.local.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                json.dumps({"comfyui_mode": "remote", "comfyui_remote_base_url": "http://10.0.0.2:8188"}),
                encoding="utf-8",
            )
            launcher_server.CONFIG_PATH = config_path
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                with mock.patch("anime_workflow.launcher.server.ComfyUIService") as service:
                    status, payload = self.request_json(server, "/api/comfyui/start", {})

                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(payload["status"], "remote_configured")
                self.assertEqual(payload["base_url"], "http://10.0.0.2:8188")
                service.assert_not_called()
            finally:
                self.stop_server(server, thread)
                launcher_server.CONFIG_PATH = previous_config_path

    def test_jobs_api_creates_lists_cancels_and_retries_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = NoopRunner()
            server, thread = self.with_server(Path(tmp) / "projects", jobs_dir=Path(tmp) / "jobs", job_runner=runner)
            try:
                status, created = self.request_json(
                    server,
                    "/api/jobs",
                    {
                        "project_id": "demo",
                        "episode_ids": ["episode_001", "episode_002"],
                        "steps": ["full"],
                        "provider": "mock",
                    },
                )
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(created["ok"])
                self.assertEqual(created["job"]["steps"], ["storyboard", "images", "video"])
                self.assertEqual(created["job"]["status"], "queued")
                self.assertEqual(runner.started, 1)

                status, listed = self.request_json(server, "/api/jobs")
                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual([item["job_id"] for item in listed["jobs"]], [created["job"]["job_id"]])

                status, cancelled = self.request_json(server, f"/api/jobs/{created['job']['job_id']}/cancel", {})
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(cancelled["job"]["cancel_requested"])

                status, retried = self.request_json(server, f"/api/jobs/{created['job']['job_id']}/retry", {})
                self.assertEqual(status, HTTPStatus.OK)
                self.assertNotEqual(retried["job"]["job_id"], created["job"]["job_id"])
                self.assertEqual(retried["job"]["episode_ids"], ["episode_001", "episode_002"])
                self.assertEqual(runner.started, 3)
            finally:
                self.stop_server(server, thread)

    def test_jobs_api_rejects_bad_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, thread = self.with_server(Path(tmp) / "projects", jobs_dir=Path(tmp) / "jobs", job_runner=NoopRunner())
            try:
                status, payload = self.request_json(
                    server,
                    "/api/jobs",
                    {"project_id": "demo", "episode_ids": ["episode_001"], "steps": ["storyboard"], "provider": "openrouter"},
                )

                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertFalse(payload["ok"])
                self.assertIn("provider must be mock, openai, or comfyui", payload["error"])
            finally:
                self.stop_server(server, thread)

    def test_jobs_api_rejects_workflow_template_provider_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, thread = self.with_server(Path(tmp) / "projects", jobs_dir=Path(tmp) / "jobs", job_runner=NoopRunner())
            try:
                status, payload = self.request_json(
                    server,
                    "/api/jobs",
                    {
                        "project_id": "demo",
                        "episode_ids": ["episode_001"],
                        "steps": ["images"],
                        "provider": "mock",
                        "workflow_template": "comfyui_external_anime",
                    },
                )

                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["error"], "workflow_template provider does not match provider")
            finally:
                self.stop_server(server, thread)

    def test_jobs_api_requires_openai_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, thread = self.with_server(Path(tmp) / "projects", jobs_dir=Path(tmp) / "jobs", job_runner=NoopRunner())
            try:
                status, payload = self.request_json(
                    server,
                    "/api/jobs",
                    {"project_id": "demo", "episode_ids": ["episode_001"], "steps": ["storyboard"], "provider": "openai"},
                )
                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertIn("openai provider requires confirmation", payload["error"])

                status, created = self.request_json(
                    server,
                    "/api/jobs",
                    {
                        "project_id": "demo",
                        "episode_ids": ["episode_001"],
                        "steps": ["storyboard"],
                        "provider": "openai",
                        "confirm_openai": True,
                    },
                )
                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(created["job"]["provider"], "openai")
            finally:
                self.stop_server(server, thread)

    def test_jobs_api_comfyui_with_openai_key_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_config_path = launcher_server.CONFIG_PATH
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            server, thread = self.with_server(Path(tmp) / "projects", jobs_dir=Path(tmp) / "jobs", job_runner=NoopRunner())
            try:
                self.request_json(server, "/api/config", {"openai_api_key": "sk-test"})

                status, payload = self.request_json(
                    server,
                    "/api/jobs",
                    {"project_id": "demo", "episode_ids": ["episode_001"], "steps": ["images"], "provider": "comfyui"},
                )

                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertEqual(payload["error"], "comfyui openai route requires confirmation")
                self.assertEqual(list((Path(tmp) / "jobs").glob("job_*.json")), [])
            finally:
                self.stop_server(server, thread)
                launcher_server.CONFIG_PATH = previous_config_path

    def test_jobs_api_comfyui_without_openai_key_can_create_mock_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_config_path = launcher_server.CONFIG_PATH
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            server, thread = self.with_server(Path(tmp) / "projects", jobs_dir=Path(tmp) / "jobs", job_runner=NoopRunner())
            try:
                status, payload = self.request_json(
                    server,
                    "/api/jobs",
                    {"project_id": "demo", "episode_ids": ["episode_001"], "steps": ["images"], "provider": "comfyui"},
                )

                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(payload["job"]["provider"], "comfyui")
                self.assertEqual(payload["job"]["workflow_template"], "comfyui_external_anime")
            finally:
                self.stop_server(server, thread)
                launcher_server.CONFIG_PATH = previous_config_path

    def test_jobs_api_reads_detail_and_creates_targeted_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = NoopRunner()
            server, thread = self.with_server(Path(tmp) / "projects", jobs_dir=Path(tmp) / "jobs", job_runner=runner)
            try:
                status, created = self.request_json(
                    server,
                    "/api/jobs",
                    {
                        "project_id": "demo",
                        "episode_ids": ["episode_001", "episode_002"],
                        "steps": ["storyboard", "images", "video"],
                        "provider": "mock",
                    },
                )
                self.assertEqual(status, HTTPStatus.OK)
                job_id = created["job"]["job_id"]
                server.job_store.set_item_failed(job_id, "episode_001", "images", "image failed")

                status, detail = self.request_json(server, f"/api/jobs/{job_id}")
                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(detail["job"]["job_id"], job_id)
                self.assertEqual(detail["job"]["items"][1]["status"], "failed")

                status, failed_retry = self.request_json(server, f"/api/jobs/{job_id}/retry-failed", {})
                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(failed_retry["job"]["episode_ids"], ["episode_001"])
                self.assertEqual(failed_retry["job"]["steps"], ["images", "video"])

                status, episode_retry = self.request_json(server, f"/api/jobs/{job_id}/episodes/episode_002/retry", {})
                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(episode_retry["job"]["episode_ids"], ["episode_002"])
                self.assertEqual(episode_retry["job"]["steps"], ["storyboard", "images", "video"])

                status, step_retry = self.request_json(server, f"/api/jobs/{job_id}/episodes/episode_001/steps/video/retry", {})
                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(step_retry["job"]["episode_ids"], ["episode_001"])
                self.assertEqual(step_retry["job"]["steps"], ["video"])
            finally:
                self.stop_server(server, thread)

    def test_jobs_api_targeted_openai_retry_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, thread = self.with_server(Path(tmp) / "projects", jobs_dir=Path(tmp) / "jobs", job_runner=NoopRunner())
            try:
                status, created = self.request_json(
                    server,
                    "/api/jobs",
                    {
                        "project_id": "demo",
                        "episode_ids": ["episode_001"],
                        "steps": ["storyboard", "images", "video"],
                        "provider": "openai",
                        "confirm_openai": True,
                    },
                )
                self.assertEqual(status, HTTPStatus.OK)
                job_id = created["job"]["job_id"]
                server.job_store.set_item_failed(job_id, "episode_001", "images", "image failed")

                status, payload = self.request_json(server, f"/api/jobs/{job_id}/retry-failed", {})
                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertIn("openai provider requires confirmation", payload["error"])

                status, retried = self.request_json(server, f"/api/jobs/{job_id}/retry-failed", {"confirm_openai": True})
                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(retried["job"]["provider"], "openai")
            finally:
                self.stop_server(server, thread)

    def test_imports_api_adapts_text_into_project_episodes_and_local_storyboards(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            previous_imports_dir = launcher_server.IMPORTS_DIR
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            launcher_server.IMPORTS_DIR = Path(tmp) / "imports"
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                source = "雨夜主角收到匿名信。\n\n线索指向失踪的人。\n\n结尾出现新的号码。" * 20
                status, payload = self.request_json(
                    server,
                    "/api/imports/adapt",
                    {
                        "filename": "story.txt",
                        "content_base64": base64.b64encode(source.encode("utf-8")).decode("ascii"),
                        "project_id": "rain",
                        "project_name": "雨夜侦探",
                        "genre": "悬疑",
                        "platform": "douyin",
                        "duration_seconds": 30,
                        "shot_count": 3,
                        "max_episodes": 2,
                        "storyboard_provider": "local",
                    },
                )

                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["project"]["project_id"], "rain")
                self.assertGreaterEqual(len(payload["episodes"]), 1)
                self.assertEqual(payload["episodes"][0]["status"], "storyboarded")
                self.assertTrue(Path(payload["episodes"][0]["storyboard_path"]).exists())
                self.assertTrue((launcher_server.IMPORTS_DIR / f"{payload['import']['import_id']}.json").exists())
            finally:
                self.stop_server(server, thread)
                launcher_server.STORYBOARD_DIR = previous_storyboard_dir
                launcher_server.IMPORTS_DIR = previous_imports_dir

    def test_imports_api_requires_openai_storyboard_confirmation_and_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            previous_imports_dir = launcher_server.IMPORTS_DIR
            previous_config_path = launcher_server.CONFIG_PATH
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            launcher_server.IMPORTS_DIR = Path(tmp) / "imports"
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            server, thread = self.with_server(Path(tmp) / "projects")
            body = {
                "filename": "story.txt",
                "text": "雨夜主角收到匿名信。\n\n线索指向失踪的人。",
                "project_id": "rain",
                "project_name": "雨夜侦探",
                "storyboard_provider": "openai",
            }
            try:
                status, payload = self.request_json(server, "/api/imports/adapt", body)
                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertIn("openai storyboard provider requires confirmation", payload["error"])

                status, payload = self.request_json(server, "/api/imports/adapt", {**body, "confirm_openai": True})
                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertIn("OpenAI API Key is not configured", payload["error"])
            finally:
                self.stop_server_with_paths(server, thread, previous_storyboard_dir, previous_config_path)
                launcher_server.IMPORTS_DIR = previous_imports_dir

    def test_storyboard_review_api_saves_updates_and_rewrites_shots(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                self.request_json(server, "/api/projects", {"project_id": "demo", "name": "示例项目", "default_shot_count": 1})
                self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 1})
                storyboard = sample_review_storyboard()

                status, saved = self.request_json(
                    server,
                    "/api/storyboard/save",
                    {"project_id": "demo", "episode_id": "episode_001", "storyboard": storyboard},
                )
                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(saved["episode"]["status"], "storyboarded")
                self.assertTrue(Path(saved["storyboard_path"]).exists())

                status, updated = self.request_json(
                    server,
                    "/api/storyboard/shot/update",
                    {
                        "project_id": "demo",
                        "episode_id": "episode_001",
                        "shot_id": "shot_001",
                        "updates": {"scene": "新的雨夜场景", "dialogue": "新台词", "review_status": "revise", "review_note": "镜头需要更紧张"},
                    },
                )
                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(updated["storyboard"]["shots"][0]["scene"], "新的雨夜场景")
                self.assertEqual(updated["storyboard"]["shots"][0]["review_status"], "revise")

                status, snapshotted = self.request_json(
                    server,
                    "/api/storyboard/review/snapshot",
                    {"project_id": "demo", "episode_id": "episode_001", "note": "第一轮审稿"},
                )
                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(snapshotted["storyboard"]["review_versions"][0]["note"], "第一轮审稿")
                self.assertEqual(snapshotted["storyboard"]["review_versions"][0]["summary"]["revise"], 1)

                status, rewritten = self.request_json(
                    server,
                    "/api/storyboard/shot/rewrite",
                    {
                        "project_id": "demo",
                        "episode_id": "episode_001",
                        "shot_id": "shot_001",
                        "instruction": "更悬疑",
                        "provider": "local",
                    },
                )
                self.assertEqual(status, HTTPStatus.OK)
                self.assertIn("更悬疑", rewritten["storyboard"]["shots"][0]["scene"])
            finally:
                self.stop_server(server, thread)
                launcher_server.STORYBOARD_DIR = previous_storyboard_dir

    def test_storyboard_review_api_handles_missing_shot_and_openai_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                self.request_json(server, "/api/projects", {"project_id": "demo", "name": "示例项目", "default_shot_count": 1})
                self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 1})
                self.request_json(
                    server,
                    "/api/storyboard/save",
                    {"project_id": "demo", "episode_id": "episode_001", "storyboard": sample_review_storyboard()},
                )

                status, payload = self.request_json(
                    server,
                    "/api/storyboard/shot/rewrite",
                    {"project_id": "demo", "episode_id": "episode_001", "shot_id": "missing", "provider": "local"},
                )
                self.assertEqual(status, HTTPStatus.NOT_FOUND)
                self.assertIn("shot not found", payload["error"])

                status, payload = self.request_json(
                    server,
                    "/api/storyboard/shot/rewrite",
                    {"project_id": "demo", "episode_id": "episode_001", "shot_id": "shot_001", "provider": "openai"},
                )
                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertIn("openai storyboard provider requires confirmation", payload["error"])
            finally:
                self.stop_server(server, thread)
                launcher_server.STORYBOARD_DIR = previous_storyboard_dir

    def test_storyboard_review_api_regenerates_one_shot_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            previous_config_path = launcher_server.CONFIG_PATH
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                self.request_json(server, "/api/projects", {"project_id": "demo", "name": "示例项目", "default_shot_count": 1})
                self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 1})
                self.request_json(
                    server,
                    "/api/storyboard/save",
                    {"project_id": "demo", "episode_id": "episode_001", "storyboard": sample_review_storyboard()},
                )

                def fake_generate_shot_image(storyboard, shot_id, provider, source_dir, output_dir, metadata_dir, references=None, workflow_template=""):
                    updated = dict(storyboard)
                    updated["shots"] = [dict(shot) for shot in storyboard["shots"]]
                    updated["shots"][0]["source_image"] = str(Path(tmp) / "source.png")
                    updated["shots"][0]["anime_image"] = str(Path(tmp) / "anime.png")
                    updated["shots"][0]["metadata_path"] = str(Path(tmp) / "metadata.json")
                    return updated

                with mock.patch.object(launcher_server, "generate_shot_image", fake_generate_shot_image):
                    status, payload = self.request_json(
                        server,
                        "/api/storyboard/shot/image",
                        {"project_id": "demo", "episode_id": "episode_001", "shot_id": "shot_001", "provider": "mock"},
                    )

                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["provider"], "mock")
                self.assertEqual(payload["episode"]["status"], "imaged")
                self.assertEqual(payload["storyboard"]["shots"][0]["anime_image"], str(Path(tmp) / "anime.png"))
            finally:
                self.stop_server_with_paths(server, thread, previous_storyboard_dir, previous_config_path)

    def test_storyboard_shot_image_rejects_workflow_template_provider_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            previous_config_path = launcher_server.CONFIG_PATH
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                self.request_json(server, "/api/projects", {"project_id": "demo", "name": "Demo", "default_shot_count": 1})
                self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 1})
                self.request_json(
                    server,
                    "/api/storyboard/save",
                    {"project_id": "demo", "episode_id": "episode_001", "storyboard": sample_review_storyboard()},
                )

                status, payload = self.request_json(
                    server,
                    "/api/storyboard/shot/image",
                    {
                        "project_id": "demo",
                        "episode_id": "episode_001",
                        "shot_id": "shot_001",
                        "provider": "mock",
                        "workflow_template": "openai_image",
                    },
                )

                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertEqual(payload["error"], "workflow_template provider does not match provider")
            finally:
                self.stop_server_with_paths(server, thread, previous_storyboard_dir, previous_config_path)

    def test_comfyui_route_with_openai_key_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            previous_config_path = launcher_server.CONFIG_PATH
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                self.request_json(server, "/api/config", {"openai_api_key": "sk-test"})
                self.request_json(server, "/api/projects", {"project_id": "demo", "name": "Demo"})
                self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 1})
                storyboard = generate_storyboard(
                    {
                        "project_id": "demo",
                        "episode_id": "episode_001",
                        "premise": "rain alley clue",
                        "shot_count": 1,
                        "duration_seconds": 3,
                    }
                )
                save_storyboard(storyboard, launcher_server.STORYBOARD_DIR)

                status, response = self.request_json(
                    server,
                    "/api/storyboard/shot/image",
                    {
                        "project_id": "demo",
                        "episode_id": "episode_001",
                        "shot_id": "shot_001",
                        "provider": "comfyui",
                        "workflow_template": "comfyui_external_anime",
                    },
                )

                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertEqual(response["error"], "comfyui openai route requires confirmation")
            finally:
                self.stop_server_with_paths(server, thread, previous_storyboard_dir, previous_config_path)

    def test_storyboard_review_api_shot_image_openai_requires_confirmation_and_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            previous_config_path = launcher_server.CONFIG_PATH
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                self.request_json(server, "/api/projects", {"project_id": "demo", "name": "示例项目", "default_shot_count": 1})
                self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 1})
                self.request_json(
                    server,
                    "/api/storyboard/save",
                    {"project_id": "demo", "episode_id": "episode_001", "storyboard": sample_review_storyboard()},
                )

                status, payload = self.request_json(
                    server,
                    "/api/storyboard/shot/image",
                    {"project_id": "demo", "episode_id": "episode_001", "shot_id": "shot_001", "provider": "openai"},
                )
                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertIn("openai provider requires confirmation", payload["error"])

                status, payload = self.request_json(
                    server,
                    "/api/storyboard/shot/image",
                    {"project_id": "demo", "episode_id": "episode_001", "shot_id": "shot_001", "provider": "openai", "confirm_openai": True},
                )
                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertIn("OpenAI API Key is not configured", payload["error"])
            finally:
                self.stop_server_with_paths(server, thread, previous_storyboard_dir, previous_config_path)

    def test_project_episode_production_endpoints_update_episode_statuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            previous_config_path = launcher_server.CONFIG_PATH
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                self.request_json(
                    server,
                    "/api/projects",
                    {
                        "project_id": "demo",
                        "name": "示例项目",
                        "genre": "悬疑",
                        "premise": "匿名信",
                        "default_shot_count": 1,
                        "default_duration_seconds": 3,
                    },
                )
                self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 1})

                status, storyboarded = self.request_json(server, "/api/projects/demo/episodes/episode_001/storyboard", {})
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(storyboarded["ok"])
                self.assertEqual(storyboarded["episode"]["status"], "storyboarded")
                self.assertTrue(Path(storyboarded["storyboard_path"]).exists())

                def fake_generate_episode_images(storyboard, provider, source_dir, output_dir, metadata_dir, references=None, workflow_template=""):
                    updated = dict(storyboard)
                    updated["shots"] = [dict(shot) for shot in storyboard["shots"]]
                    updated["shots"][0]["workflow_template"] = workflow_template
                    updated["shots"][0]["anime_image"] = str(Path(tmp) / "shot_001.png")
                    return updated

                with mock.patch.object(launcher_server, "generate_episode_images", fake_generate_episode_images):
                    status, imaged = self.request_json(server, "/api/projects/demo/episodes/episode_001/images", {})
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(imaged["ok"])
                self.assertEqual(imaged["provider"], "mock")
                self.assertEqual(imaged["episode"]["status"], "imaged")

                video_path = Path(tmp) / "exports/demo-episode_001.mp4"
                video_path.parent.mkdir()
                video_path.write_bytes(b"fake video")
                seen_output_dirs: list[Path] = []

                def fake_export_episode_video(storyboard, output_dir):
                    seen_output_dirs.append(Path(output_dir))
                    return video_path

                with mock.patch.object(launcher_server, "export_episode_video", fake_export_episode_video):
                    status, exported = self.request_json(server, "/api/projects/demo/episodes/episode_001/video", {})
                self.assertEqual(status, HTTPStatus.OK)
                self.assertTrue(exported["ok"])
                self.assertEqual(exported["video_path"], str(video_path))
                self.assertEqual(exported["episode"]["status"], "exported")
                self.assertEqual(seen_output_dirs, [launcher_server.PROJECT_ROOT / "data/exports"])
            finally:
                self.stop_server_with_paths(server, thread, previous_storyboard_dir, previous_config_path)

    def test_project_episode_images_rejects_workflow_template_provider_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            previous_config_path = launcher_server.CONFIG_PATH
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                self.request_json(server, "/api/projects", {"project_id": "demo", "name": "Demo", "default_shot_count": 1})
                self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 1})
                save_storyboard(sample_review_storyboard(), launcher_server.STORYBOARD_DIR)

                status, payload = self.request_json(
                    server,
                    "/api/projects/demo/episodes/episode_001/images",
                    {"provider": "mock", "workflow_template": "comfyui_external_anime"},
                )

                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertEqual(payload["error"], "workflow_template provider does not match provider")
            finally:
                self.stop_server_with_paths(server, thread, previous_storyboard_dir, previous_config_path)

    def test_project_episode_video_uses_configured_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            previous_config_path = launcher_server.CONFIG_PATH
            configured_exports = Path(tmp) / "configured_exports"
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            launcher_server.CONFIG_PATH.parent.mkdir(parents=True)
            launcher_server.CONFIG_PATH.write_text(json.dumps({"output_dir": str(configured_exports)}), encoding="utf-8")
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                self.request_json(
                    server,
                    "/api/projects",
                    {
                        "project_id": "demo",
                        "name": "示例项目",
                        "default_shot_count": 1,
                        "default_duration_seconds": 3,
                    },
                )
                self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 1})
                self.request_json(server, "/api/projects/demo/episodes/episode_001/storyboard", {})
                with mock.patch.object(
                    launcher_server,
                    "generate_episode_images",
                    lambda storyboard, provider, source_dir, output_dir, metadata_dir, references=None, workflow_template="": {
                        **storyboard,
                        "shots": [{**storyboard["shots"][0], "workflow_template": workflow_template, "anime_image": str(Path(tmp) / "frame.png")}],
                    },
                ):
                    self.request_json(server, "/api/projects/demo/episodes/episode_001/images", {})

                seen_output_dirs: list[Path] = []
                video_path = configured_exports / "demo-episode_001.mp4"

                def fake_export_episode_video(storyboard, output_dir):
                    seen_output_dirs.append(Path(output_dir))
                    video_path.parent.mkdir(parents=True, exist_ok=True)
                    video_path.write_bytes(b"fake video")
                    return video_path

                with mock.patch.object(launcher_server, "export_episode_video", fake_export_episode_video):
                    status, payload = self.request_json(server, "/api/projects/demo/episodes/episode_001/video", {})

                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(seen_output_dirs, [configured_exports])
                self.assertEqual(payload["episode"]["video_path"], str(video_path))
            finally:
                self.stop_server_with_paths(server, thread, previous_storyboard_dir, previous_config_path)

    def test_project_episode_video_failure_marks_episode_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            previous_config_path = launcher_server.CONFIG_PATH
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            server, thread = self.with_server(Path(tmp) / "projects", exports_dir=Path(tmp) / "exports")
            try:
                self.request_json(server, "/api/projects", {"project_id": "demo", "name": "Demo", "default_shot_count": 1})
                self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 1})
                storyboard = generate_storyboard(
                    {
                        "project_id": "demo",
                        "episode_id": "episode_001",
                        "premise": "rain alley clue",
                        "shot_count": 1,
                        "duration_seconds": 3,
                    }
                )
                storyboard["shots"][0]["anime_image"] = str(Path(tmp) / "missing-frame.png")
                save_storyboard(storyboard, launcher_server.STORYBOARD_DIR)

                status, payload = self.request_json(server, "/api/projects/demo/episodes/episode_001/video", {})

                self.assertEqual(status, HTTPStatus.INTERNAL_SERVER_ERROR)
                self.assertFalse(payload["ok"])
                self.assertIn("frame not found", payload["error"])

                status, episodes = self.request_json(server, "/api/projects/demo/episodes")
                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(episodes["episodes"][0]["status"], "failed")
                self.assertIn("frame not found", episodes["episodes"][0]["error"])
            finally:
                self.stop_server_with_paths(server, thread, previous_storyboard_dir, previous_config_path)

    def test_project_episode_video_missing_storyboard_returns_404_without_failing_episode(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            previous_config_path = launcher_server.CONFIG_PATH
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            server, thread = self.with_server(Path(tmp) / "projects", exports_dir=Path(tmp) / "exports")
            try:
                self.request_json(server, "/api/projects", {"project_id": "demo", "name": "Demo", "default_shot_count": 1})
                self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 1})

                status, payload = self.request_json(server, "/api/projects/demo/episodes/episode_001/video", {})

                self.assertEqual(status, HTTPStatus.NOT_FOUND)
                self.assertFalse(payload.get("ok", False))

                status, episodes = self.request_json(server, "/api/projects/demo/episodes")
                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(episodes["episodes"][0]["status"], "draft")
                self.assertEqual(episodes["episodes"][0].get("error", ""), "")
            finally:
                self.stop_server_with_paths(server, thread, previous_storyboard_dir, previous_config_path)

    def test_project_episode_images_openai_without_key_returns_400(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            previous_config_path = launcher_server.CONFIG_PATH
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                self.request_json(server, "/api/projects", {"project_id": "demo", "name": "示例项目"})
                self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 1})
                self.request_json(server, "/api/projects/demo/episodes/episode_001/storyboard", {})

                status, payload = self.request_json(
                    server,
                    "/api/projects/demo/episodes/episode_001/images",
                    {"provider": "openai", "confirm_openai": True},
                )

                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertFalse(payload["ok"])
                self.assertIn("OpenAI API Key is not configured", payload["error"])
            finally:
                self.stop_server_with_paths(server, thread, previous_storyboard_dir, previous_config_path)

    def test_project_episode_images_openai_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            previous_config_path = launcher_server.CONFIG_PATH
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            launcher_server.CONFIG_PATH.parent.mkdir(parents=True)
            launcher_server.CONFIG_PATH.write_text(json.dumps({"openai_api_key": "sk-test"}), encoding="utf-8")
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                self.request_json(server, "/api/projects", {"project_id": "demo", "name": "示例项目"})
                self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 1})
                self.request_json(server, "/api/projects/demo/episodes/episode_001/storyboard", {})

                status, payload = self.request_json(
                    server,
                    "/api/projects/demo/episodes/episode_001/images",
                    {"provider": "openai"},
                )

                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertFalse(payload["ok"])
                self.assertIn("openai provider requires confirmation", payload["error"])
            finally:
                self.stop_server_with_paths(server, thread, previous_storyboard_dir, previous_config_path)

    def test_project_episode_production_path_rejects_empty_segments(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            previous_config_path = launcher_server.CONFIG_PATH
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                self.request_json(server, "/api/projects", {"project_id": "demo", "name": "示例项目"})
                self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 1})

                status, _ = self.request_json(server, "/api/projects/demo/episodes/episode_001//video", {})

                self.assertEqual(status, HTTPStatus.NOT_FOUND)
            finally:
                self.stop_server_with_paths(server, thread, previous_storyboard_dir, previous_config_path)

    def test_project_episode_production_rejects_invalid_episode_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            previous_config_path = launcher_server.CONFIG_PATH
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                self.request_json(server, "/api/projects", {"project_id": "demo", "name": "示例项目"})
                self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 1})

                status, payload = self.request_json(server, "/api/projects/demo/episodes/episode%20001/storyboard", {})

                self.assertEqual(status, HTTPStatus.BAD_REQUEST)
                self.assertFalse(payload["ok"])
                self.assertIn("episode_id is invalid", payload["error"])
            finally:
                self.stop_server_with_paths(server, thread, previous_storyboard_dir, previous_config_path)

    def test_project_episode_production_unknown_error_returns_500_and_marks_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_storyboard_dir = launcher_server.STORYBOARD_DIR
            previous_config_path = launcher_server.CONFIG_PATH
            launcher_server.STORYBOARD_DIR = Path(tmp) / "storyboards"
            launcher_server.CONFIG_PATH = Path(tmp) / "config/settings.local.json"
            server, thread = self.with_server(Path(tmp) / "projects")
            try:
                self.request_json(server, "/api/projects", {"project_id": "demo", "name": "示例项目"})
                self.request_json(server, "/api/projects/demo/episodes/batch", {"count": 1})
                self.request_json(server, "/api/projects/demo/episodes/episode_001/storyboard", {})

                with mock.patch.object(launcher_server, "generate_episode_images", mock.Mock(side_effect=RuntimeError("image provider failed"))):
                    status, payload = self.request_json(server, "/api/projects/demo/episodes/episode_001/images", {})

                self.assertEqual(status, HTTPStatus.INTERNAL_SERVER_ERROR)
                self.assertFalse(payload["ok"])
                self.assertIn("image provider failed", payload["error"])

                status, episodes = self.request_json(server, "/api/projects/demo/episodes")
                self.assertEqual(status, HTTPStatus.OK)
                self.assertEqual(episodes["episodes"][0]["status"], "failed")
                self.assertIn("image provider failed", episodes["episodes"][0]["error"])
            finally:
                self.stop_server_with_paths(server, thread, previous_storyboard_dir, previous_config_path)


if __name__ == "__main__":
    unittest.main()


def sample_review_storyboard():
    return {
        "project_id": "demo",
        "episode_id": "episode_001",
        "title": "雨夜来信",
        "genre": "悬疑",
        "premise": "雨夜收到匿名信",
        "protagonist": "林夏",
        "style_preset": "clean_anime_drama",
        "platform": "douyin",
        "duration_seconds": 30,
        "shot_count": 1,
        "shots": [
            {
                "shot_id": "shot_001",
                "duration": 30,
                "scene": "雨夜，信封出现。",
                "dialogue": "这是谁寄来的？",
                "image_prompt": "anime rain night letter",
                "camera": "close-up",
                "emotion": "suspenseful",
                "source_image": "",
                "anime_image": "",
            }
        ],
    }
