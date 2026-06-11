import json
import tempfile
import unittest
from base64 import b64decode, b64encode
from pathlib import Path
from unittest.mock import Mock

from anime_workflow.services.anime_api_adapter import (
    AnimeApiRequest,
    AnimeApiAdapter,
    ComfyUIAnimeProvider,
    HttpAnimeProvider,
    MockAnimeProvider,
    OpenAIImageProvider,
)


class AnimeApiAdapterTest(unittest.TestCase):
    def test_stylize_writes_result_metadata_and_cache_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            source.write_bytes(b"fake-image-bytes")

            adapter = AnimeApiAdapter(
                provider=MockAnimeProvider(),
                output_dir=root / "anime_frames",
                metadata_dir=root / "api_metadata",
            )
            request = AnimeApiRequest(
                project_id="p01",
                episode_id="e01",
                shot_id="s01",
                source_image=source,
                style_preset="clean_anime",
                prompt="young detective, moonlit village",
            )

            first = adapter.stylize(request)
            second = adapter.stylize(request)

            self.assertTrue(first.output_image.exists())
            self.assertEqual(first.output_image, second.output_image)
            self.assertFalse(first.cache_hit)
            self.assertTrue(second.cache_hit)
            self.assertEqual(adapter.provider.call_count, 1)

            metadata = json.loads(first.metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["provider"], "mock")
            self.assertEqual(metadata["project_id"], "p01")
            self.assertEqual(metadata["episode_id"], "e01")
            self.assertEqual(metadata["shot_id"], "s01")
            self.assertEqual(metadata["status"], "succeeded")
            self.assertEqual(metadata["style_preset"], "clean_anime")

    def test_missing_source_image_fails_before_provider_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            provider = MockAnimeProvider()
            adapter = AnimeApiAdapter(
                provider=provider,
                output_dir=root / "anime_frames",
                metadata_dir=root / "api_metadata",
            )

            with self.assertRaises(FileNotFoundError):
                adapter.stylize(
                    AnimeApiRequest(
                        project_id="p01",
                        episode_id="e01",
                        shot_id="s01",
                        source_image=root / "missing.png",
                        style_preset="clean_anime",
                    )
                )

            self.assertEqual(provider.call_count, 0)

    def test_http_provider_posts_base64_image_and_writes_response_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            source.write_bytes(b"source-image")
            output = root / "output.png"

            opener = Mock()
            response = Mock()
            response.read.return_value = json.dumps(
                {"image_base64": b64encode(b"anime-image").decode("ascii")}
            ).encode("utf-8")
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            opener.return_value = response

            provider = HttpAnimeProvider(
                endpoint="https://api.example.test/anime",
                api_key="secret",
                provider_name="example",
                model_version="v1",
                opener=opener,
            )
            provider.stylize(
                AnimeApiRequest(
                    project_id="p01",
                    episode_id="e01",
                    shot_id="s01",
                    source_image=source,
                    style_preset="clean_anime",
                    prompt="moonlit village",
                ),
                output,
            )

            self.assertEqual(output.read_bytes(), b"anime-image")
            http_request = opener.call_args.args[0]
            self.assertEqual(http_request.full_url, "https://api.example.test/anime")
            self.assertEqual(http_request.get_header("Authorization"), "Bearer secret")
            payload = json.loads(http_request.data.decode("utf-8"))
            self.assertEqual(payload["style_preset"], "clean_anime")
            self.assertEqual(payload["prompt"], "moonlit village")
            self.assertEqual(payload["image_base64"], b64encode(b"source-image").decode("ascii"))

    def test_openai_provider_uses_images_edits_multipart_and_writes_b64_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            source.write_bytes(b"source-image")
            output = root / "anime.png"

            opener = Mock()
            response = Mock()
            response.read.return_value = json.dumps(
                {"data": [{"b64_json": b64encode(b"anime-image").decode("ascii")}]}
            ).encode("utf-8")
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            opener.return_value = response

            provider = OpenAIImageProvider(api_key="secret", model="gpt-image-2", opener=opener)
            provider.stylize(
                AnimeApiRequest(
                    project_id="p01",
                    episode_id="e01",
                    shot_id="s01",
                    source_image=source,
                    style_preset="clean_anime",
                    prompt="把这张分镜改成统一角色的动漫短剧画风",
                ),
                output,
            )

            self.assertEqual(output.read_bytes(), b"anime-image")
            http_request = opener.call_args.args[0]
            self.assertEqual(http_request.full_url, "https://api.openai.com/v1/images/edits")
            self.assertEqual(http_request.get_method(), "POST")
            self.assertEqual(http_request.get_header("Authorization"), "Bearer secret")
            self.assertIn("multipart/form-data", http_request.get_header("Content-type"))
            body = http_request.data
            self.assertIn(b'name="model"', body)
            self.assertIn(b"gpt-image-2", body)
            self.assertIn(b'name="prompt"', body)
            self.assertIn("统一角色".encode("utf-8"), body)
            self.assertIn(b'name="image"; filename="source.png"', body)

    def test_openai_provider_builds_images_endpoint_from_gateway_base_url(self):
        provider = OpenAIImageProvider(api_key="secret", endpoint="https://aigate.zhixingjidian.cn")

        self.assertEqual(provider.endpoint, "https://aigate.zhixingjidian.cn/v1/images/edits")

    def test_openai_provider_keeps_full_images_endpoint(self):
        provider = OpenAIImageProvider(api_key="secret", endpoint="https://proxy.example.test/custom/images/edits")

        self.assertEqual(provider.endpoint, "https://proxy.example.test/custom/images/edits")

    def test_comfyui_provider_submits_external_node_and_writes_base64_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            source.write_bytes(b"source-image")
            reference = root / "reference.png"
            reference.write_bytes(b"reference-image")
            client = Mock()
            client.submit_prompt.return_value = "prompt-1"
            client.wait_for_history.return_value = {
                "outputs": {
                    "1": {
                        "string": [
                            json.dumps({"image_base64": b64encode(b"anime-image").decode("ascii")})
                        ]
                    }
                }
            }
            provider = ComfyUIAnimeProvider(
                base_url="http://10.0.0.2:8188",
                api_endpoint="mock",
                provider_name="mock",
                model_version="mock-v1",
                workflow_template={
                    "comfyui": {
                        "node_id": "42",
                        "class_type": "ExternalAnimeStylize",
                        "inputs": {
                            "source_image_base64": "{{source_image_base64}}",
                            "reference_image_base64": "{{reference_image_base64}}",
                            "output_path": "{{remote_output_path}}",
                            "prompt": "{{prompt}}",
                            "return_image_base64": "{{return_image_base64}}",
                        },
                    }
                },
                client=client,
            )
            output = root / "anime.png"

            provider.stylize(
                AnimeApiRequest(
                    project_id="demo",
                    episode_id="episode_001",
                    shot_id="shot_001",
                    source_image=source,
                    style_preset="clean",
                    prompt="rainy alley",
                    reference_images=(reference,),
                ),
                output,
            )

            self.assertEqual(output.read_bytes(), b"anime-image")
            workflow = client.submit_prompt.call_args.args[0]
            inputs = workflow["42"]["inputs"]
            self.assertEqual(workflow["42"]["class_type"], "ExternalAnimeStylize")
            self.assertEqual(b64decode(inputs["source_image_base64"]), b"source-image")
            self.assertEqual(b64decode(inputs["reference_image_base64"]), b"reference-image")
            self.assertEqual(inputs["prompt"], "rainy alley")
            self.assertEqual(inputs["return_image_base64"], "true")
            client.wait_for_history.assert_called_once_with("prompt-1", timeout_seconds=180)


if __name__ == "__main__":
    unittest.main()
