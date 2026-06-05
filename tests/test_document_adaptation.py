import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from anime_workflow.imports.adaptation import build_episode_drafts, build_import_record, clean_source_text, split_short_video_episodes
from anime_workflow.imports.document_reader import extract_document_text
from anime_workflow.story.providers import LocalStoryboardProvider, OpenAICompatibleStoryboardProvider


class DocumentReaderTest(unittest.TestCase):
    def test_extracts_txt_and_markdown_text(self):
        self.assertEqual(extract_document_text("story.txt", "第一章\n雨夜来信".encode("utf-8")), "第一章\n雨夜来信")
        self.assertIn("雨夜来信", extract_document_text("story.md", "# 标题\n\n雨夜来信".encode("utf-8")))

    def test_extracts_text_based_pdf_literals(self):
        pdf = b"%PDF-1.4\n1 0 obj\nBT\n(First scene) Tj\n(Second clue) Tj\nET\nendobj\n%%EOF"

        text = extract_document_text("story.pdf", pdf)

        self.assertIn("First scene", text)
        self.assertIn("Second clue", text)

    def test_rejects_unsupported_or_empty_documents(self):
        with self.assertRaisesRegex(ValueError, "unsupported document type"):
            extract_document_text("story.docx", b"hello")
        with self.assertRaisesRegex(ValueError, "document text is empty"):
            extract_document_text("story.txt", b"   \n")
        with self.assertRaisesRegex(ValueError, "PDF text could not be extracted"):
            extract_document_text("scan.pdf", b"%PDF-1.4\n%%EOF")


class AdaptationTest(unittest.TestCase):
    def test_cleans_markdown_and_splits_short_video_chunks(self):
        source = "# 第一章\n\n雨夜来信。\n\n\n> 广告\n\n线索出现。" * 40

        cleaned = clean_source_text(source)
        chunks = split_short_video_episodes(cleaned, duration_seconds=30, max_episodes=3)

        self.assertNotIn("#", cleaned)
        self.assertNotIn("> 广告", cleaned)
        self.assertLessEqual(len(chunks), 3)
        self.assertTrue(all(chunk for chunk in chunks))

    def test_builds_episode_drafts_and_import_record(self):
        chunks = ["雨夜来信。主角发现第一条线索。", "第二天，线索指向失踪的人。"]

        episodes = build_episode_drafts(chunks, duration_seconds=60, shot_count=8)
        record = build_import_record(
            import_id="import_fixed",
            project_id="rain",
            filename="story.txt",
            content_type="text/plain",
            cleaned_text_path="data/imports/import_fixed.txt",
            text_length=100,
            episode_ids=[item["episode_id"] for item in episodes],
            settings={"platform": "douyin", "duration_seconds": 60, "shot_count": 8},
        )

        self.assertEqual([item["episode_id"] for item in episodes], ["episode_001", "episode_002"])
        self.assertEqual(episodes[0]["duration_seconds"], 60)
        self.assertEqual(episodes[0]["shot_count"], 8)
        self.assertEqual(episodes[0]["source_excerpt"], chunks[0])
        self.assertEqual(record["import_id"], "import_fixed")
        self.assertEqual(record["episode_ids"], ["episode_001", "episode_002"])


class StoryboardProviderTest(unittest.TestCase):
    def test_local_provider_generates_storyboard_shape(self):
        storyboard = LocalStoryboardProvider().generate(
            {
                "project_id": "rain",
                "episode_id": "episode_001",
                "title": "雨夜来信",
                "genre": "悬疑",
                "premise": "雨夜主角收到匿名信",
                "protagonist": "林夏",
                "style_preset": "clean_anime_drama",
                "platform": "douyin",
                "duration_seconds": 30,
                "shot_count": 3,
            }
        )

        self.assertEqual(storyboard["episode_id"], "episode_001")
        self.assertEqual(len(storyboard["shots"]), 3)
        self.assertIn("image_prompt", storyboard["shots"][0])

    def test_openai_chat_completions_provider_posts_and_parses_storyboard_json(self):
        with fake_openai_server(chat_payload()) as base_url:
            provider = OpenAICompatibleStoryboardProvider(
                api_key="sk-test",
                base_url=base_url,
                model="story-model",
                endpoint_mode="chat_completions",
            )

            storyboard = provider.generate(storyboard_values())

            self.assertEqual(storyboard["title"], "API 分镜")
            self.assertEqual(storyboard["shots"][0]["shot_id"], "shot_001")

    def test_openai_responses_provider_posts_and_parses_output_text(self):
        with fake_openai_server(responses_payload()) as base_url:
            provider = OpenAICompatibleStoryboardProvider(
                api_key="sk-test",
                base_url=base_url,
                model="story-model",
                endpoint_mode="responses",
            )

            storyboard = provider.generate(storyboard_values())

            self.assertEqual(storyboard["title"], "API 分镜")

    def test_openai_provider_rejects_invalid_json_and_shape(self):
        with fake_openai_server({"choices": [{"message": {"content": "not json"}}]}) as base_url:
            provider = OpenAICompatibleStoryboardProvider("sk-test", base_url, "story-model", "chat_completions")
            with self.assertRaisesRegex(ValueError, "storyboard API returned invalid JSON"):
                provider.generate(storyboard_values())

        with fake_openai_server({"choices": [{"message": {"content": json.dumps({"title": "bad"})}}]}) as base_url:
            provider = OpenAICompatibleStoryboardProvider("sk-test", base_url, "story-model", "chat_completions")
            with self.assertRaisesRegex(ValueError, "storyboard API returned invalid storyboard"):
                provider.generate(storyboard_values())


def storyboard_values():
    return {
        "project_id": "rain",
        "episode_id": "episode_001",
        "title": "雨夜来信",
        "genre": "悬疑",
        "premise": "雨夜主角收到匿名信",
        "protagonist": "林夏",
        "style_preset": "clean_anime_drama",
        "platform": "douyin",
        "duration_seconds": 30,
        "shot_count": 1,
    }


def storyboard_payload():
    values = storyboard_values()
    values["title"] = "API 分镜"
    values["shots"] = [
        {
            "shot_id": "shot_001",
            "duration": 30,
            "scene": "雨夜，匿名信出现。",
            "dialogue": "这封信是谁寄来的？",
            "image_prompt": "anime rain night detective",
            "camera": "close-up",
            "emotion": "suspenseful",
            "source_image": "",
            "anime_image": "",
        }
    ]
    return values


def chat_payload():
    return {"choices": [{"message": {"content": json.dumps(storyboard_payload(), ensure_ascii=False)}}]}


def responses_payload():
    return {"output_text": json.dumps(storyboard_payload(), ensure_ascii=False)}


class fake_openai_server:
    def __init__(self, payload: dict):
        self.payload = payload
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def __enter__(self):
        payload = self.payload

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                self.server.last_path = self.path
                self.server.last_body = json.loads(self.rfile.read(length).decode("utf-8"))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode("utf-8"))

            def log_message(self, format, *args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_port}"

    def __exit__(self, exc_type, exc, tb):
        assert self.server is not None
        assert self.thread is not None
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
