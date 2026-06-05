import json
import unittest
from unittest.mock import Mock

from anime_workflow.services.comfyui_client import ComfyUIClient


class ComfyUIClientTest(unittest.TestCase):
    def test_submit_prompt_posts_prompt_payload(self):
        opener = Mock()
        response = Mock()
        response.read.return_value = json.dumps({"prompt_id": "abc123"}).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener.return_value = response

        client = ComfyUIClient(base_url="http://127.0.0.1:8188", opener=opener)
        prompt_id = client.submit_prompt({"1": {"class_type": "ExternalAnimeStylize"}})

        self.assertEqual(prompt_id, "abc123")
        request = opener.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8188/prompt")
        self.assertEqual(request.get_method(), "POST")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["prompt"], {"1": {"class_type": "ExternalAnimeStylize"}})

    def test_history_fetches_prompt_history(self):
        opener = Mock()
        response = Mock()
        response.read.return_value = json.dumps({"outputs": {}}).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener.return_value = response

        client = ComfyUIClient(base_url="http://127.0.0.1:8188", opener=opener)
        history = client.history("abc123")

        self.assertEqual(history, {"outputs": {}})
        request = opener.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8188/history/abc123")


if __name__ == "__main__":
    unittest.main()
