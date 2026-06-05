import json
import os
import tempfile
import unittest
from pathlib import Path

from anime_workflow.projects.store import ProjectStore


class ProjectLibraryTest(unittest.TestCase):
    def test_create_project_writes_project_json_and_lists_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")

            project = store.save_project(
                {
                    "project_id": "Rain Detective",
                    "name": "雨夜侦探",
                    "genre": "悬疑",
                    "platform": "douyin",
                    "premise": "雨夜匿名信引发的连续失踪案",
                    "default_duration_seconds": 30,
                    "default_shot_count": 6,
                    "default_style_id": "clean_anime_drama",
                }
            )

            self.assertEqual(project["project_id"], "rain_detective")
            self.assertEqual(project["name"], "雨夜侦探")
            self.assertEqual(project["status"], "active")
            self.assertTrue((Path(tmp) / "projects/rain_detective/project.json").exists())
            self.assertEqual([item["project_id"] for item in store.list_projects()], ["rain_detective"])

    def test_project_validation_rejects_empty_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")

            with self.assertRaisesRegex(ValueError, "name is required"):
                store.save_project({"project_id": "demo", "name": ""})

    def test_update_project_preserves_explicit_empty_premise(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")
            store.save_project(
                {
                    "project_id": "demo",
                    "name": "示例项目",
                    "premise": "旧简介",
                }
            )

            project = store.save_project({"project_id": "demo", "name": "示例项目", "premise": ""})

            self.assertEqual(project["premise"], "")
            self.assertEqual(store.get_project("demo")["premise"], "")

    def test_get_project_rejects_non_object_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "projects/demo/project.json"
            project_path.parent.mkdir(parents=True)
            project_path.write_text(json.dumps([]), encoding="utf-8")
            store = ProjectStore(Path(tmp) / "projects")

            with self.assertRaisesRegex(ValueError, "project json must be an object"):
                store.get_project("demo")

    def test_create_character_and_style_under_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")
            store.save_project({"project_id": "demo", "name": "示例项目"})

            character = store.save_character(
                "demo",
                {
                    "character_id": "hero",
                    "name": "林夏",
                    "role": "年轻侦探",
                    "appearance": "黑发，冷静，蓝色风衣",
                    "personality": "敏锐但克制",
                    "costume": "蓝色风衣",
                },
            )
            style = store.save_style(
                "demo",
                {
                    "style_id": "dark_suspense",
                    "name": "暗色悬疑",
                    "base_prompt": "dark suspense anime, cinematic lighting",
                    "negative_prompt": "low quality, blurry",
                    "aspect_ratio": "9:16",
                },
            )

            self.assertEqual(character["character_id"], "hero")
            self.assertEqual(style["style_id"], "dark_suspense")
            self.assertEqual(store.list_characters("demo")[0]["name"], "林夏")
            self.assertEqual(store.list_styles("demo")[0]["name"], "暗色悬疑")

    def test_create_batch_episodes_uses_project_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")
            store.save_project(
                {
                    "project_id": "demo",
                    "name": "示例项目",
                    "genre": "悬疑",
                    "premise": "匿名信连环案",
                    "default_duration_seconds": 30,
                    "default_shot_count": 6,
                }
            )

            episodes = store.create_episode_batch("demo", {"count": 3, "direction": "每集一个线索，结尾反转"})

            self.assertEqual([item["episode_no"] for item in episodes], [1, 2, 3])
            self.assertEqual(episodes[0]["episode_id"], "episode_001")
            self.assertEqual(episodes[0]["status"], "draft")
            self.assertIn("第1集", episodes[0]["title"])
            self.assertEqual(store.list_episodes("demo")[2]["episode_id"], "episode_003")

    def test_update_episode_by_id_preserves_existing_episode_no(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")
            store.save_project({"project_id": "demo", "name": "示例项目"})
            store.save_episode("demo", {"episode_id": "episode_003", "episode_no": 3})

            episode = store.save_episode("demo", {"episode_id": "episode_003", "status": "exported"})

            self.assertEqual(episode["episode_no"], 3)
            self.assertEqual(store.list_episodes("demo")[0]["episode_no"], 3)

    def test_update_episode_status_preserves_existing_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")
            store.save_project({"project_id": "demo", "name": "示例项目"})
            episode = store.save_episode("demo", {"episode_no": 1})

            updated = store.update_episode(
                "demo",
                episode["episode_id"],
                {"status": "exported", "video_path": "data/exports/demo.mp4"},
            )

            self.assertEqual(updated["episode_no"], 1)
            self.assertEqual(updated["status"], "exported")
            self.assertEqual(updated["video_path"], "data/exports/demo.mp4")

    def test_create_episode_batch_starts_after_max_existing_episode_no(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")
            store.save_project({"project_id": "demo", "name": "示例项目"})
            store.save_episode("demo", {"episode_id": "episode_001", "episode_no": 1})
            store.save_episode("demo", {"episode_id": "episode_005", "episode_no": 5})

            episodes = store.create_episode_batch("demo", {"count": 1})

            self.assertEqual(episodes[0]["episode_no"], 6)
            self.assertEqual(episodes[0]["episode_id"], "episode_006")

    def test_update_episode_preserves_and_clears_error_by_key_presence(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")
            store.save_project({"project_id": "demo", "name": "示例项目"})
            store.save_episode("demo", {"episode_id": "episode_001", "error": "old error"})

            updated = store.save_episode("demo", {"episode_id": "episode_001", "status": "exported"})
            cleared = store.save_episode("demo", {"episode_id": "episode_001", "error": ""})

            self.assertEqual(updated["error"], "old error")
            self.assertEqual(cleared["error"], "")

    def test_build_storyboard_input_combines_project_character_style_episode(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")
            store.save_project(
                {
                    "project_id": "demo",
                    "name": "雨夜侦探",
                    "genre": "悬疑",
                    "platform": "douyin",
                    "premise": "匿名信连环案",
                    "default_style_id": "dark_suspense",
                }
            )
            store.save_character("demo", {"character_id": "hero", "name": "林夏", "role": "年轻侦探", "appearance": "黑发蓝色风衣"})
            store.save_style(
                "demo",
                {"style_id": "dark_suspense", "name": "暗色悬疑", "base_prompt": "dark suspense anime, cinematic lighting"},
            )
            episode = store.save_episode("demo", {"episode_no": 1, "premise": "林夏收到第一封匿名信"})

            values = store.build_storyboard_values("demo", episode["episode_id"])

            self.assertEqual(values["project_id"], "demo")
            self.assertEqual(values["episode_id"], "episode_001")
            self.assertIn("匿名信连环案", values["premise"])
            self.assertIn("林夏", values["protagonist"])
            self.assertIn("dark_suspense", values["style_preset"])
            self.assertIn("dark suspense anime, cinematic lighting", values["style_preset"])

    def test_build_storyboard_values_without_characters_or_styles_uses_sensible_fallbacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")
            store.save_project({"project_id": "demo", "name": "示例项目"})
            episode = store.save_episode("demo", {"episode_no": 1})

            values = store.build_storyboard_values("demo", episode["episode_id"])

            self.assertEqual(values["protagonist"], "年轻主角")
            self.assertIn("clean_anime_drama", values["style_preset"])

    def test_build_storyboard_values_with_style_id_mismatch_ignores_unrelated_style_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "projects")
            store.save_project({"project_id": "demo", "name": "示例项目", "default_style_id": "mystery_noir"})
            store.save_style(
                "demo",
                {"style_id": "bright_comedy", "name": "明亮喜剧", "base_prompt": "cheerful comedy anime"},
            )
            episode = store.save_episode("demo", {"episode_no": 1})

            values = store.build_storyboard_values("demo", episode["episode_id"])

            self.assertEqual(values["style_preset"], "mystery_noir")
            self.assertNotIn("cheerful comedy anime", values["style_preset"])

    def test_get_episode_rejects_non_object_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode_path = Path(tmp) / "projects/demo/episodes/episode_001.json"
            episode_path.parent.mkdir(parents=True)
            episode_path.write_text(json.dumps([]), encoding="utf-8")
            store = ProjectStore(Path(tmp) / "projects")

            with self.assertRaisesRegex(ValueError, "episode json must be an object"):
                store.get_episode("demo", "episode_001")

    def test_list_outputs_returns_exported_videos(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exports = root / "exports"
            exports.mkdir()
            old_video = exports / "demo-episode_000.mp4"
            old_video.write_bytes(b"old video")
            video = exports / "demo-episode_001.mp4"
            video.write_bytes(b"video")
            ignored = exports / "notes.txt"
            ignored.write_text("not a video", encoding="utf-8")
            old_mtime = 1_700_000_000
            new_mtime = 1_700_000_100
            old_video.touch()
            video.touch()

            os.utime(old_video, (old_mtime, old_mtime))
            os.utime(video, (new_mtime, new_mtime))
            store = ProjectStore(root / "projects")

            outputs = store.list_outputs(exports)

            self.assertEqual([item["filename"] for item in outputs], ["demo-episode_001.mp4", "demo-episode_000.mp4"])
            self.assertEqual(outputs[0]["video_path"], str(video))
            self.assertEqual(outputs[0]["size_bytes"], 5)
            self.assertEqual(outputs[0]["updated_at"], new_mtime)


if __name__ == "__main__":
    unittest.main()
