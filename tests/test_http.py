from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import asyncio
import io
import json
import unittest

from PIL import Image

from pixelart.config import Profile
from pixelart.providers.comfy_http import ComfyHTTP


class Handler(BaseHTTPRequestHandler):
    submitted = None

    def log_message(self, *args):
        pass

    def reply(self, value, content_type="application/json"):
        payload = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/system_stats":
            self.reply({"devices": []})
        elif self.path == "/models/checkpoints":
            self.reply(["remote.safetensors"])
        elif self.path.startswith("/object_info/"):
            self.reply({self.path.rsplit("/", 1)[-1]: {}})
        elif self.path.startswith("/history/"):
            self.reply({"abc": {"status": {"status_str": "success"}, "outputs": {
                "7": {"images": [{"filename": "../../escape.png", "subfolder": "", "type": "output"}]}
            }}})
        elif self.path.startswith("/view?"):
            data = io.BytesIO()
            Image.new("RGBA", (32, 32), "red").save(data, format="PNG")
            self.reply(data.getvalue(), "image/png")
        else:
            self.send_error(404)

    def do_POST(self):
        Handler.submitted = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.reply({"prompt_id": "abc"})


class HTTPTests(unittest.TestCase):
    def test_target_query_submit_status_and_safe_download(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        async def run(tmp):
            adapter = ComfyHTTP(Profile(provider="comfy-http", url=f"http://127.0.0.1:{server.server_port}"))
            self.assertEqual((await adapter.preflight(""))["checkpoint"], "remote.safetensors")
            graph = Path(tmp) / "workflow.json"
            graph.write_text('{"7":{"class_type":"SaveImage","inputs":{}}}')
            await adapter.validate(graph)
            self.assertEqual(await adapter.submit(graph), "abc")
            self.assertEqual((await adapter.status("abc"))["state"], "completed")
            files = await adapter.fetch("abc", Path(tmp) / "outputs")
            self.assertEqual(files[0].name, "image-000.png")
            self.assertFalse((Path(tmp) / "escape.png").exists())
            self.assertEqual(Handler.submitted["prompt"]["7"]["class_type"], "SaveImage")
            with Image.open(files[0]) as image:
                self.assertEqual(image.size, (32, 32))
        try:
            with TemporaryDirectory() as tmp:
                asyncio.run(run(tmp))
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
