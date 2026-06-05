import tempfile
import unittest
from pathlib import Path

from anime_workflow.services.anime_api_adapter import MockAnimeProvider
from anime_workflow.story.episode_runner import export_episode_video, generate_episode_images
from anime_workflow.story.storyboard import generate_storyboard, load_storyboard, save_storyboard


class EpisodeProductionTest(unittest.TestCase):
    def test_generate_storyboard_writes_requested_shots(self):
        with tempfile.TemporaryDirectory() as tmp:
            storyboard = generate_storyboard(
                {
                    "project_id": "rain_detective",
                    "episode_id": "episode_001",
                    "genre": "悬疑",
                    "premise": "雨夜主角收到匿名信",
                    "protagonist": "年轻侦探",
                    "style_preset": "clean_anime_drama",
                    "platform": "douyin",
                    "duration_seconds": 18,
                    "shot_count": 6,
                }
            )
            path = save_storyboard(storyboard, Path(tmp))
            loaded = load_storyboard(path)

            self.assertEqual(loaded["project_id"], "rain_detective")
            self.assertEqual(loaded["episode_id"], "episode_001")
            self.assertEqual(len(loaded["shots"]), 6)
            self.assertEqual(sum(shot["duration"] for shot in loaded["shots"]), 18)
            self.assertIn("雨夜主角收到匿名信", loaded["shots"][0]["image_prompt"])

    def test_mock_episode_images_and_video_are_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storyboard = generate_storyboard(
                {
                    "project_id": "demo_project",
                    "episode_id": "episode_001",
                    "genre": "都市",
                    "premise": "主角准备发布第一集",
                    "protagonist": "短剧导演",
                    "style_preset": "clean_anime_drama",
                    "platform": "douyin",
                    "duration_seconds": 6,
                    "shot_count": 2,
                }
            )

            with_images = generate_episode_images(
                storyboard=storyboard,
                provider=MockAnimeProvider(),
                source_dir=root / "source_frames",
                output_dir=root / "anime_frames",
                metadata_dir=root / "metadata",
            )
            video_path = export_episode_video(with_images, root / "exports")

            self.assertEqual(len(with_images["shots"]), 2)
            self.assertTrue(Path(with_images["shots"][0]["source_image"]).exists())
            self.assertTrue(Path(with_images["shots"][0]["anime_image"]).exists())
            self.assertTrue(video_path.exists())


if __name__ == "__main__":
    unittest.main()
