from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts" / "generate_image_atlas.py"
SPEC = importlib.util.spec_from_file_location("generate_image_atlas", SCRIPT)
assert SPEC and SPEC.loader
atlas = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(atlas)


class FakeResponse:
    def __init__(self, payload):
        self.body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size=-1):
        if not self.body:
            return b""
        if size < 0:
            result, self.body = self.body, b""
            return result
        result, self.body = self.body[:size], self.body[size:]
        return result


def schema():
    return {
        "components": {
            "schemas": {
                "Input": {
                    "type": "object",
                    "required": ["model", "prompt"],
                    "properties": {
                        "model": {"type": "string"},
                        "prompt": {"type": "string"},
                        "aspect_ratio": {"enum": ["1:1", "16:9"]},
                        "resolution": {"enum": ["1k", "2k", "4k"]},
                        "output_format": {"enum": ["png", "jpeg"]},
                        "enable_sync_mode": {"type": "boolean"},
                        "enable_base64_output": {"type": "boolean"},
                    },
                }
            }
        }
    }


class AtlasImageTests(unittest.TestCase):
    @patch.object(atlas.urllib.request, "urlopen")
    def test_live_schema_submit_once_poll_and_download(self, urlopen):
        urlopen.side_effect = [
            FakeResponse(
                {
                    "data": [
                        {
                            "model": atlas.DEFAULT_MODEL,
                            "type": "Image",
                            "schema": "https://static.atlascloud.ai/model/schema/test.json",
                        }
                    ]
                }
            ),
            FakeResponse(schema()),
            FakeResponse({"data": {"id": "pred-1", "status": "created"}}),
            FakeResponse({"data": {"id": "pred-1", "status": "processing"}}),
            FakeResponse(
                {
                    "data": {
                        "id": "pred-1",
                        "status": "completed",
                        "outputs": ["https://cdn.test/output.png"],
                    }
                }
            ),
            FakeResponse(b"png-bytes"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output.png"
            result = atlas.generate(
                "a blue icon",
                output,
                api_key="test-key",
                poll_attempts=3,
                poll_interval=0,
                sleep=lambda _seconds: None,
            )
            self.assertEqual(result, output)
            self.assertEqual(output.read_bytes(), b"png-bytes")

        requests = [call.args[0] for call in urlopen.call_args_list]
        post_requests = [request for request in requests if request.get_method() == "POST"]
        self.assertEqual(len(post_requests), 1)
        self.assertEqual(
            post_requests[0].full_url,
            "https://api.atlascloud.ai/api/v1/model/generateImage",
        )
        submitted = json.loads(post_requests[0].data)
        self.assertEqual(submitted["model"], atlas.DEFAULT_MODEL)
        self.assertEqual(submitted["aspect_ratio"], "1:1")
        self.assertEqual(submitted["resolution"], "1k")

    def test_invalid_value_is_rejected_by_live_schema(self):
        responses = iter(
            [
                {
                    "data": [
                        {
                            "model": atlas.DEFAULT_MODEL,
                            "type": "Image",
                            "schema": "https://static.atlascloud.ai/model/schema/test.json",
                        }
                    ]
                },
                schema(),
            ]
        )

        def request_json(*_args, **_kwargs):
            return next(responses)

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(atlas.AtlasError, "Invalid aspect_ratio"):
                atlas.generate(
                    "a blue icon",
                    Path(directory) / "output.png",
                    api_key="test-key",
                    aspect_ratio="2:1",
                    request_json=request_json,
                )

    @patch.object(atlas.urllib.request, "urlopen")
    def test_missing_key_stops_before_network(self, urlopen):
        with patch.dict(atlas.os.environ, {}, clear=True):
            self.assertEqual(atlas.main(["--prompt", "icon", "--filename", "out.png"]), 2)
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
