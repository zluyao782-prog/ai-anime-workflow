import unittest
import tempfile
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
        try:
            with request.urlopen(http_request, timeout=3) as response:
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
                self.assertIn("provider must be mock or openai", payload["error"])
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

                def fake_generate_episode_images(storyboard, provider, source_dir, output_dir, metadata_dir):
                    updated = dict(storyboard)
                    updated["shots"] = [dict(shot) for shot in storyboard["shots"]]
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
                with mock.patch.object(launcher_server, "generate_episode_images", lambda storyboard, provider, source_dir, output_dir, metadata_dir: {**storyboard, "shots": [{**storyboard["shots"][0], "anime_image": str(Path(tmp) / "frame.png")}]}):
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
