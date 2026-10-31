import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
import io
import json
import unittest

from PIL import Image

from pixelart.cli import parser
from pixelart.comparison import check_existing, load_definition, run_comparison
from pixelart.config import Profile
from pixelart.pipeline import generate
from pixelart.project import Project, write_json
from pixelart.providers.base import ProviderError
from pixelart.providers.comfy_http import ComfyHTTP
from pixelart.providers.local_mcp import CORE_NODES, LocalMCP
from pixelart.request import Request
from pixelart.workflow import build_workflow


class LoraTests(unittest.TestCase):
    def test_both_clip_encoders_and_sampler_use_the_lora(self):
        graph = build_workflow(Request(lora="pixel.safetensors", lora_strength=0.8, vae="fixed.safetensors"), "x")
        self.assertEqual(graph["5"]["inputs"]["model"], ["8", 0])
        self.assertEqual(graph["2"]["inputs"]["clip"], ["8", 1])
        self.assertEqual(graph["3"]["inputs"]["clip"], ["8", 1])
        self.assertEqual(graph["8"]["inputs"]["strength_model"], 0.8)
        self.assertEqual(graph["8"]["inputs"]["strength_clip"], 0.8)
        self.assertEqual(graph["6"]["inputs"]["vae"], ["9", 0])

    def test_no_lora_keeps_the_original_graph(self):
        graph = build_workflow(Request(), "x")
        self.assertEqual(len(graph), 7)
        self.assertEqual({n["class_type"] for n in graph.values()}, CORE_NODES)
        self.assertEqual(graph["5"]["inputs"]["model"], ["1", 0])
        self.assertEqual(graph["6"]["inputs"]["vae"], ["1", 2])

    def test_zero_strength_and_separate_vae(self):
        graph = build_workflow(Request(lora="pixel.safetensors", lora_strength=0), "x")
        self.assertEqual(graph["8"]["inputs"]["strength_clip"], 0)
        self.assertEqual(graph["6"]["inputs"]["vae"], ["1", 2])
        graph = build_workflow(Request(vae="fixed.safetensors"), "x")
        self.assertNotIn("8", graph)
        self.assertEqual(graph["2"]["inputs"]["clip"], ["1", 1])

    def test_invalid_strength_and_model_names(self):
        for value in (-0.1, 2.1, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Request(lora="pixel.safetensors", lora_strength=value)
        with self.assertRaises(ValueError):
            Request(lora_strength=0.8)
        for value in ("/root.safetensors", r"\root.safetensors", "../bad.safetensors",
                      r"..\bad.safetensors", r"C:\models\bad.safetensors"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Request(lora=value)

    def test_cli_accepts_optional_assets(self):
        args = parser().parse_args(["generate", "--output", "output/demo", "--lora", "pixel.safetensors",
                                   "--lora-strength", "0.75", "--vae", "fixed.safetensors"])
        self.assertEqual((args.lora, args.lora_strength, args.vae), ("pixel.safetensors", 0.75, "fixed.safetensors"))

    def test_request_roundtrip_and_legacy_defaults(self):
        old = Request(**{"prompt": "coin", "size": 32})
        self.assertEqual(old.lora, "")
        selected = Request(lora="pixel.safetensors", vae="fixed.safetensors", lora_strength=0.7)
        self.assertEqual(Request(**selected.to_dict()), selected)


class PreflightTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_target_checks_optional_files_and_nodes(self):
        client = LocalMCP(Profile())
        async def call(name, args):
            if name == "server_info":
                return {"server": {"running": True, "url": "http://127.0.0.1:8188"}}
            if name == "search_models":
                names = {"checkpoints": ["base.safetensors"], "loras": ["pixel.safetensors"], "vae": ["fixed.safetensors"]}
                return {"files": [{"name": x} for x in names[args["folder"]]]}
            return {"id": args["name"], "is_api_node": False}
        client.call = AsyncMock(side_effect=call)
        result = await client.preflight("base.safetensors", "pixel.safetensors", "fixed.safetensors")
        self.assertEqual(result["lora"], "pixel.safetensors")
        queried = {c.args[1]["name"] for c in client.call.call_args_list if c.args[0] == "nodes"}
        self.assertEqual(queried, CORE_NODES | {"LoraLoader", "VAELoader"})
        with self.assertRaises(ProviderError):
            await client.preflight("base.safetensors", "missing.safetensors")

    async def test_remote_looks_up_remote_files_and_allows_known_optional_nodes(self):
        adapter = ComfyHTTP(Profile(provider="comfy-http", url="http://example.invalid"))
        async def response(route):
            if route.startswith("/models/"):
                return {"/models/checkpoints": ["base"], "/models/loras": ["pixel"], "/models/vae": ["fixed"]}[route]
            if route.startswith("/object_info/"):
                return {route.rsplit("/", 1)[-1]: {}}
            return {}
        adapter.request = AsyncMock(side_effect=response)
        await adapter.preflight("base", "pixel", "fixed")
        with self.assertRaises(ProviderError):
            await adapter.preflight("base", "missing", "fixed")
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "workflow.json"
            write_json(path, build_workflow(Request(lora="pixel", vae="fixed"), "x"))
            await adapter.validate(path)
            write_json(path, {"1": {"class_type": "PaidPartnerNode"}})
            with self.assertRaises(ProviderError):
                await adapter.validate(path)

    async def test_pipeline_persists_assets_and_does_not_submit_missing_lora(self):
        fake = AsyncMock()
        fake.preflight.return_value = {"checkpoint": "base"}
        fake.submit.return_value = "job"
        @asynccontextmanager
        async def connection(profile):
            yield fake
        with TemporaryDirectory() as tmp, patch("pixelart.pipeline.connect", connection):
            root = Path(tmp) / "project"
            project = await generate(root, Request(checkpoint="base", lora="pixel", vae="fixed"), Profile(), submit_only=True)
            fake.preflight.assert_awaited_once_with("base", lora="pixel", vae="fixed")
            self.assertEqual(Project.open(root).manifest["request"]["lora"], "pixel")
            self.assertEqual(json.loads((root / "workflow.json").read_text())["8"]["inputs"]["lora_name"], "pixel")
            fake.reset_mock()
            fake.preflight.side_effect = ProviderError("missing lora")
            with self.assertRaises(ProviderError):
                await generate(Path(tmp) / "missing", Request(lora="missing"), Profile())
            fake.submit.assert_not_awaited()


class ComparisonTests(unittest.IsolatedAsyncioTestCase):
    def definition(self, profile):
        return {"format_version": 1, "profile_fingerprint": profile.fingerprint(),
                "settings": {"steps": 1, "generation_size": 512},
                "variants": [{"name": "base", "checkpoint": "base"}],
                "samples": [{"name": "potion", "prompt": "potion", "size": 32, "seed": 42}]}

    async def test_completed_comparison_reopens_without_server(self):
        fake = AsyncMock()
        fake.preflight.return_value = {"checkpoint": "base"}
        fake.submit.return_value = "job"
        fake.status.return_value = {"state": "completed"}
        async def fetch(job, directory):
            directory.mkdir(parents=True)
            path = directory / "source.png"
            Image.new("RGBA", (32, 32), "red").save(path)
            return [path]
        fake.fetch.side_effect = fetch
        @asynccontextmanager
        async def connection(profile):
            yield fake
        profile = Profile()
        with TemporaryDirectory() as tmp, patch("pixelart.comparison.connect", connection), patch("sys.stdout", new_callable=io.StringIO):
            root = Path(tmp)
            definition = self.definition(profile)
            records = await run_comparison(root, definition, profile)
            self.assertTrue(records[0]["technical_pass"])
            self.assertEqual(fake.submit.await_count, 1)
            with patch("pixelart.comparison.connect", side_effect=AssertionError("must not connect")):
                again = await run_comparison(root, definition, profile)
            self.assertEqual(again[0]["job_id"], "job")
            changed = json.loads(json.dumps(definition))
            changed["settings"]["cfg"] = 4
            with self.assertRaises(ValueError):
                await run_comparison(root, changed, profile)
            self.assertEqual(fake.submit.await_count, 1)

    def test_existing_project_setting_mismatch_is_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "project"
            Project.create(path, Request(seed=1).to_dict())
            with self.assertRaises(ValueError):
                check_existing(path, Request(seed=2))

    def test_definition_rejects_path_traversal_and_duplicate_names(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            samples = root / "samples.json"
            variants = root / "variants.json"
            write_json(samples, [{"name": "../escape", "prompt": "potion"}])
            write_json(variants, {"settings": {}, "variants": [{"name": "base", "checkpoint": "base"}]})
            with self.assertRaises(ValueError):
                load_definition(samples, variants, Profile())
            write_json(samples, [{"name": "potion", "prompt": "one"}, {"name": "potion", "prompt": "two"}])
            with self.assertRaises(ValueError):
                load_definition(samples, variants, Profile())
