"""Regression cases derived from CodeRabbit PR #1 findings."""
import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image
from pixelart.config import Profile
from pixelart.pixels import convert
from pixelart.project import Project
from pixelart.providers.base import ProviderError, SubmissionUnknown
from pixelart.providers.comfy_http import ComfyHTTP
from pixelart.request import Request


@contextmanager
def server(handler):
    instance = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{instance.server_port}"
    finally:
        instance.shutdown()
        thread.join()
        instance.server_close()


class ReviewInputTests(unittest.TestCase):
    def test_palette_rejects_non_hex_and_non_strings_at_request_boundary(self):
        for color in ("#-00000", "#+12345", "#1_2345", "# 12345", None, 1234567):
            with self.subTest(color=color), self.assertRaises(ValueError):
                Request(palette=[color])
        self.assertEqual(Request(palette=["#aB12eF"]).palette, ["#aB12eF"])

    def test_empty_grid_input_has_clear_failure(self):
        with self.assertRaisesRegex(ValueError, "grid"):
            convert(Image.new("RGBA", (12, 12)), Request(method="grid"))

    def test_token_profile_requires_https_or_loopback(self):
        for url in ("http://gpu.example", "http://192.168.1.20", "http://localhost.attacker.example"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                Profile(provider="comfy-http", url=url, token_env="TEST_COMFY_TOKEN")
        for url in ("https://gpu.example", "http://127.0.0.1:8188", "http://127.0.0.2", "http://[::1]", "http://localhost"):
            with self.subTest(url=url):
                Profile(provider="comfy-http", url=url, token_env="TEST_COMFY_TOKEN")
        Profile(provider="comfy-http", url="http://192.168.1.20")

    def test_sample_runner_rejects_changed_definition_before_reuse(self):
        spec = importlib.util.spec_from_file_location("sample_runner", "examples/run_samples.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for changed in ({"prompt": "old potion"}, {"size": 64}, {"seed": 10}):
            with self.subTest(changed=changed), TemporaryDirectory() as tmp:
                root = Path(tmp)
                sample = {"name": "potion", "prompt": "new potion", "size": 32, "seed": 42}
                (root / "samples.json").write_text(json.dumps([sample]), encoding="utf-8")
                values = {"prompt": sample["prompt"], "size": 32, "seed": 42, "checkpoint": "resolved.safetensors", "prompt_preset": "item", **changed}
                project = Project.create(root / "output" / "potion", Request(**values).to_dict())
                project.update("review")
                with patch.object(module, "__file__", str(root / "run_samples.py")), self.assertRaisesRegex(ValueError, "request|definition"):
                    asyncio.run(module.run(SimpleNamespace(profile=None, output=root / "output")))
                self.assertFalse((root / "output" / "index.json").exists())


class ReviewHTTPTests(unittest.TestCase):
    def test_redirects_never_forward_credentials_or_change_submit_method(self):
        received = []
        class Target(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                received.append((self.command, self.headers.get("Authorization")))
                payload = b'{"prompt_id":"redirected"}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            do_POST = do_GET
        with server(Target) as target:
            class Redirect(BaseHTTPRequestHandler):
                def log_message(self, *args): pass
                def do_GET(self):
                    if self.command == "POST":
                        self.rfile.read(int(self.headers["Content-Length"]))
                    self.send_response(302)
                    self.send_header("Location", target + "/leak")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                do_POST = do_GET
            with server(Redirect) as origin, patch.dict("os.environ", {"TEST_COMFY_TOKEN": "test-only-token"}):
                adapter = ComfyHTTP(Profile(provider="comfy-http", url=origin, token_env="TEST_COMFY_TOKEN"))
                for payload in (None, {"prompt": {}}):
                    with self.subTest(payload=payload), self.assertRaises(ProviderError):
                        asyncio.run(adapter.request("/prompt", payload))
        self.assertEqual(received, [])

    def test_explicit_http_rejection_is_not_ambiguous_but_server_failure_is(self):
        for status in (400, 401, 403, 422, 500):
            class Reject(BaseHTTPRequestHandler):
                def log_message(self, *args): pass
                def do_POST(self):
                    self.rfile.read(int(self.headers["Content-Length"]))
                    self.send_error(status)
            with self.subTest(status=status), server(Reject) as url, TemporaryDirectory() as tmp:
                graph = Path(tmp) / "workflow.json"
                graph.write_text("{}", encoding="utf-8")
                adapter = ComfyHTTP(Profile(provider="comfy-http", url=url))
                with self.assertRaises(ProviderError) as caught:
                    asyncio.run(adapter.submit(graph))
                self.assertEqual(isinstance(caught.exception, SubmissionUnknown), status == 500)

    def test_missing_token_is_rejected_before_submission(self):
        adapter = ComfyHTTP(Profile(provider="comfy-http", url="http://127.0.0.1:1", token_env="TEST_COMFY_TOKEN"))
        with TemporaryDirectory() as tmp, patch.dict("os.environ", {}, clear=True):
            graph = Path(tmp) / "workflow.json"
            graph.write_text("{}", encoding="utf-8")
            with self.assertRaises(ProviderError) as caught:
                asyncio.run(adapter.submit(graph))
            self.assertNotIsInstance(caught.exception, SubmissionUnknown)


if __name__ == "__main__":
    unittest.main()
