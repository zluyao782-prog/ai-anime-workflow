import importlib.util
import json
import tempfile
import unittest
from base64 import b64encode
from pathlib import Path
from unittest.mock import Mock, patch


class ComfyUICustomNodeTest(unittest.TestCase):
    def test_external_anime_node_is_registered_as_output_node(self):
        node_path = Path("comfyui_custom_nodes/external_anime_api_bridge/__init__.py")
        spec = importlib.util.spec_from_file_location("external_anime_api_bridge", node_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        self.assertTrue(module.ExternalAnimeStylize.OUTPUT_NODE)

    def test_external_anime_node_mock_copies_source_to_output(self):
        node_path = Path("comfyui_custom_nodes/external_anime_api_bridge/__init__.py")
        spec = importlib.util.spec_from_file_location("external_anime_api_bridge", node_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            output = root / "anime.png"
            source.write_bytes(b"source-image")

            node = module.ExternalAnimeStylize()
            result = node.stylize(
                source_image_path=str(source),
                output_path=str(output),
                style_preset="clean_anime",
                prompt="moonlit village",
                api_endpoint="mock",
                api_key="",
                provider_name="mock",
                model_version="mock-v1",
            )

            self.assertEqual(result, (str(output),))
            self.assertEqual(output.read_bytes(), b"source-image")

    def test_external_anime_node_openai_mode_uses_images_edits(self):
        node_path = Path("comfyui_custom_nodes/external_anime_api_bridge/__init__.py")
        spec = importlib.util.spec_from_file_location("external_anime_api_bridge", node_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            output = root / "anime.png"
            source.write_bytes(b"source-image")

            opener = Mock()
            response = Mock()
            response.read.return_value = json.dumps(
                {"data": [{"b64_json": b64encode(b"anime-image").decode("ascii")}]}
            ).encode("utf-8")
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            opener.return_value = response

            with patch.object(module.urllib_request, "urlopen", opener):
                node = module.ExternalAnimeStylize()
                result = node.stylize(
                    source_image_path=str(source),
                    output_path=str(output),
                    style_preset="clean_anime",
                    prompt="moonlit village",
                    api_endpoint="https://api.openai.com/v1/images/edits",
                    api_key="secret",
                    provider_name="openai",
                    model_version="gpt-image-2",
                )

            self.assertEqual(result, (str(output),))
            self.assertEqual(output.read_bytes(), b"anime-image")
            http_request = opener.call_args.args[0]
            self.assertEqual(http_request.full_url, "https://api.openai.com/v1/images/edits")
            self.assertEqual(http_request.get_header("Authorization"), "Bearer secret")
            self.assertIn("multipart/form-data", http_request.get_header("Content-type"))
            self.assertIn(b"gpt-image-2", http_request.data)


if __name__ == "__main__":
    unittest.main()
