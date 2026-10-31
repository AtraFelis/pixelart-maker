"""Behavioral regressions from the model-comparison GitHub review."""
import asyncio
from contextlib import asynccontextmanager
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

from PIL import Image
from pixelart.comparison import load_definition, make_request, run_comparison
from pixelart.config import Profile
from pixelart.project import Project, write_json
from pixelart.providers.base import ProviderError


def definition(profile):
    return {"format_version": 1, "profile_fingerprint": profile.fingerprint(),
            "settings": {"steps": 1, "generation_size": 512},
            "variants": [{"name": "base", "checkpoint": "base"}],
            "samples": [{"name": "potion", "prompt": "potion", "size": 32, "seed": 42}]}


def write_source(directory):
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "source.png"
    image = Image.new("RGBA", (32, 32))
    image.paste((220, 30, 50, 255), (8, 4, 24, 28))
    image.save(source)
    return source


def existing(root, data, profile, source=False):
    request = make_request(data, data["variants"][0], data["samples"][0])
    project = Project.create(root / "base" / "potion", request.to_dict())
    project.update("processing" if source else "running", job_id="confirmed-job",
                   provider={"fingerprint": profile.fingerprint()})
    if source:
        project.add_asset("source", write_source(project.root / "original"))
    return project


class DefinitionBoundaryTests(unittest.TestCase):
    def load(self, data):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "samples.json", data["samples"])
            write_json(root / "variants.json", {"settings": data["settings"], "variants": data["variants"]})
            return load_definition(root / "samples.json", root / "variants.json", Profile())

    def test_variants_cannot_change_sampling_or_sample_fields(self):
        for field, value in (("steps", 2), ("cfg", 4), ("seed", 9), ("size", 64), ("prompt", "changed")):
            data = definition(Profile())
            data["variants"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.load(data)

    def test_samples_cannot_override_models_or_shared_conditions(self):
        for field, value in (("lora", "other"), ("vae", "other"), ("checkpoint", "other"), ("lora_strength", 1), ("steps", 2)):
            data = definition(Profile())
            data["samples"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.load(data)

    def test_shared_settings_cannot_smuggle_model_or_sample_fields(self):
        for field, value in (("checkpoint", "other"), ("lora", "other"), ("prompt", "other"), ("seed", 9)):
            data = definition(Profile())
            data["settings"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.load(data)

    def test_supported_fields_keep_common_conditions_and_variant_selection(self):
        data = definition(Profile())
        data["settings"].update(cfg=4, colors=8)
        data["variants"][0].update(lora="pixel", vae="fixed", lora_strength=0.8)
        data["samples"][0].update(size=64, seed=7)
        loaded = self.load(data)
        request = make_request(loaded, loaded["variants"][0], loaded["samples"][0])
        self.assertEqual((request.cfg, request.colors, request.steps), (4, 8, 1))
        self.assertEqual((request.checkpoint, request.lora, request.vae, request.lora_strength), ("base", "pixel", "fixed", 0.8))
        self.assertEqual((request.size, request.seed), (64, 7))


class ResumeBoundaryTests(unittest.IsolatedAsyncioTestCase):
    def fake(self):
        fake = AsyncMock()
        fake.status.return_value = {"state": "completed"}
        fake.preflight.return_value = {"checkpoint": "base"}
        async def fetch(job, directory):
            return [write_source(directory)]
        fake.fetch.side_effect = fetch
        return fake

    async def test_confirmed_job_collects_when_model_is_unavailable(self):
        profile = Profile()
        data = definition(profile)
        fake = self.fake()
        fake.preflight.side_effect = ProviderError("model removed")
        @asynccontextmanager
        async def connect(profile): yield fake
        with TemporaryDirectory() as tmp, patch("pixelart.comparison.connect", connect), patch("pixelart.pipeline.connect", connect), patch("sys.stdout", new_callable=io.StringIO):
            root = Path(tmp)
            existing(root, data, profile)
            records = await run_comparison(root, data, profile)
            self.assertEqual(records[0]["job_id"], "confirmed-job")
            self.assertTrue(records[0]["technical_pass"])
            fake.status.assert_awaited_once_with("confirmed-job")
            fake.preflight.assert_not_awaited()
            fake.submit.assert_not_awaited()

    async def test_saved_source_reprocesses_with_no_server(self):
        profile = Profile()
        data = definition(profile)
        with TemporaryDirectory() as tmp, patch("pixelart.comparison.connect", side_effect=AssertionError("must not connect")), patch("pixelart.pipeline.connect", side_effect=AssertionError("must not connect")), patch("sys.stdout", new_callable=io.StringIO):
            root = Path(tmp)
            project = existing(root, data, profile, source=True)
            records = await run_comparison(root, data, profile)
            self.assertEqual(records[0]["state"], "review")
            self.assertTrue((project.root / "final.png").exists())

    async def test_saved_source_finishes_before_later_new_job_preflight_fails(self):
        profile = Profile()
        data = definition(profile)
        data["samples"].append({"name": "coin", "prompt": "coin", "size": 32, "seed": 43})
        fake = self.fake()
        fake.preflight.side_effect = ProviderError("model removed")
        @asynccontextmanager
        async def connect(profile): yield fake
        with TemporaryDirectory() as tmp, patch("pixelart.comparison.connect", connect), patch("pixelart.pipeline.connect", side_effect=AssertionError("saved source is local")), patch("sys.stdout", new_callable=io.StringIO):
            root = Path(tmp)
            project = existing(root, data, profile, source=True)
            with self.assertRaisesRegex(ProviderError, "model removed"):
                await run_comparison(root, data, profile)
            self.assertEqual(Project.open(project.root).manifest["state"], "review")
            self.assertEqual(len(json.loads((root / "comparison.json").read_text())["records"]), 1)
            fake.preflight.assert_awaited_once_with("base")
            fake.submit.assert_not_awaited()

    async def test_new_jobs_share_one_preflight_but_submit_each_workflow(self):
        profile = Profile()
        data = definition(profile)
        data["samples"].append({"name": "coin", "prompt": "coin", "size": 32, "seed": 43})
        fake = self.fake()
        fake.submit.side_effect = ["new-1", "new-2"]
        @asynccontextmanager
        async def connect(profile): yield fake
        with TemporaryDirectory() as tmp, patch("pixelart.comparison.connect", connect), patch("sys.stdout", new_callable=io.StringIO):
            records = await run_comparison(Path(tmp), data, profile)
            self.assertEqual([r["job_id"] for r in records], ["new-1", "new-2"])
            fake.preflight.assert_awaited_once_with("base")
            self.assertEqual(fake.validate.await_count, 2)
            self.assertEqual(fake.submit.await_count, 2)
