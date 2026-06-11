import unittest

from anime_workflow.story.review import (
    rewrite_storyboard_shot_local,
    snapshot_storyboard_review,
    update_storyboard_shot,
    validate_storyboard_for_review,
)


class StoryboardReviewTest(unittest.TestCase):
    def test_validate_accepts_valid_storyboard_and_rejects_invalid_shape(self):
        storyboard = sample_storyboard()

        self.assertEqual(validate_storyboard_for_review(storyboard)["episode_id"], "episode_001")

        with self.assertRaisesRegex(ValueError, "storyboard API returned invalid storyboard"):
            validate_storyboard_for_review({"title": "bad"})

    def test_update_storyboard_shot_changes_allowed_fields_only(self):
        storyboard = sample_storyboard()

        updated = update_storyboard_shot(
            storyboard,
            "shot_001",
            {
                "scene": "新的雨夜场景",
                "dialogue": "新台词",
                "anime_image": "should-not-change.png",
                "reference_bindings": ["hero", "rain_alley", "hero"],
                "workflow_template": "comfyui_external_anime",
                "review_status": "approved",
                "review_note": "画面和台词通过",
            },
        )

        shot = updated["shots"][0]
        self.assertEqual(shot["scene"], "新的雨夜场景")
        self.assertEqual(shot["dialogue"], "新台词")
        self.assertEqual(shot["anime_image"], "/old.png")
        self.assertEqual(shot["reference_bindings"], ["hero", "rain_alley"])
        self.assertEqual(shot["workflow_template"], "comfyui_external_anime")
        self.assertEqual(shot["review_status"], "approved")
        self.assertEqual(shot["review_note"], "画面和台词通过")
        self.assertTrue(shot["reviewed_at"])

    def test_snapshot_storyboard_review_records_summary_and_shots(self):
        storyboard = update_storyboard_shot(sample_storyboard(), "shot_001", {"review_status": "revise", "review_note": "主角脸不稳定"})

        updated = snapshot_storyboard_review(storyboard, "第一轮审稿")

        self.assertEqual(len(updated["review_versions"]), 1)
        version = updated["review_versions"][0]
        self.assertEqual(version["note"], "第一轮审稿")
        self.assertEqual(version["summary"]["revise"], 1)
        self.assertEqual(version["summary"]["pending"], 0)
        self.assertEqual(version["shots"][0]["review_note"], "主角脸不稳定")

    def test_update_storyboard_shot_rejects_missing_shot(self):
        with self.assertRaisesRegex(FileNotFoundError, "shot not found"):
            update_storyboard_shot(sample_storyboard(), "missing", {"scene": "x"})

    def test_rewrite_storyboard_shot_local_preserves_id_and_updates_prompt(self):
        updated = rewrite_storyboard_shot_local(sample_storyboard(), "shot_001", "更悬疑，结尾留钩子")
        shot = updated["shots"][0]

        self.assertEqual(shot["shot_id"], "shot_001")
        self.assertIn("更悬疑", shot["scene"])
        self.assertIn("结尾留钩子", shot["dialogue"])
        self.assertIn("更悬疑", shot["image_prompt"])


def sample_storyboard():
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
                "anime_image": "/old.png",
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
