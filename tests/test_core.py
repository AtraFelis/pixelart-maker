import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import io
import json
import shutil
import unittest

import numpy as np
from PIL import Image, ImageDraw

from pixelart.cli import main
from pixelart.config import Profile
from pixelart.pipeline import generate, import_image, resume
from pixelart.pixels import convert, prepare, save_png
from pixelart.project import Project
from pixelart.providers.base import ProviderError, SubmissionUnknown, job_state
from pixelart.providers.local_mcp import CORE_NODES, normalize_result
from pixelart.request import Request
from pixelart.validation import validate
from pixelart.workflow import build_workflow


def fixture():
    image = Image.new("RGBA", (64, 64), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 8, 43, 55), fill=(25, 20, 30, 255))
    draw.rectangle((24, 12, 39, 51), fill=(210, 35, 50, 255))
    return image


class PixelTests(unittest.TestCase):
    def test_output_constraints_and_png_roundtrip(self):
        for size in (32, 64):
            request = Request(size=size, colors=4)
            candidates, _, _ = convert(fixture(), request)
            with TemporaryDirectory() as tmp:
                for name, image in candidates.items():
                    self.assertTrue(validate(image, request)["passed"])
                    save_png(image, Path(tmp) / (name + ".png"))
                    self.assertEqual(image.mode, "RGBA")

    def test_fixed_palette_only_contains_allowed_colors(self):
        request = Request(colors=2, palette=["#110022", "#FF0033"])
        candidates, _, _ = convert(fixture(), request)
        for image in candidates.values():
            self.assertTrue(validate(image, request)["passed"])
            self.assertLessEqual(validate(image, request)["visible_colors"], 2)

    def test_background_removal_does_not_remove_enclosed_white(self):
        image = Image.new("RGBA", (32, 32), "white")
        ImageDraw.Draw(image).rectangle((5, 5, 26, 26), outline="black", width=2)
        prepared, _ = prepare(image, Request())
        self.assertEqual(prepared.getpixel((0, 0))[3], 0)
        self.assertEqual(prepared.getpixel((16, 16))[3], 255)

    def test_disagreeing_corners_are_not_silently_deleted(self):
        image = fixture()
        image.putpixel((0, 0), (0, 0, 0, 255))
        prepared, notes = prepare(image, Request())
        self.assertEqual(prepared.getpixel((63, 0))[3], 255)
        self.assertIn("skipped", notes[0])

    def test_alpha_threshold_and_hidden_rgb_normalized(self):
        image = Image.new("RGBA", (3, 1))
        image.putdata([(123, 88, 9, 0), (10, 20, 30, 127), (10, 20, 30, 128)])
        prepared, _ = prepare(image, Request(background="alpha"))
        self.assertEqual(list(prepared.get_flattened_data()), [(0, 0, 0, 0), (0, 0, 0, 0), (10, 20, 30, 255)])

    def test_opaque_background_also_obeys_fixed_palette(self):
        image = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle((3, 3, 8, 8), fill="red")
        request = Request(colors=1, palette=["#880011"], background="opaque")
        candidates, _, _ = convert(image, request)
        for image in candidates.values():
            self.assertTrue(validate(image, request)["passed"])
            self.assertTrue(np.all(np.array(image)[:, :, 3] == 255))

    def test_empty_image_has_explicit_quality_warning(self):
        candidates, _, notes = convert(Image.new("RGBA", (12, 12)), Request())
        self.assertTrue(validate(candidates["nearest"], Request())["passed"])
        self.assertIn("Empty foreground", notes[0])

    def test_preview_is_exact_pixel_replication(self):
        image = convert(fixture(), Request())[0]["majority"]
        enlarged = np.array(image.resize((512, 512), Image.Resampling.NEAREST))
        expected = np.repeat(np.repeat(np.array(image), 16, axis=0), 16, axis=1)
        np.testing.assert_array_equal(enlarged, expected)

    def test_validation_detects_invalid_size_colors_and_alpha(self):
        image = Image.new("RGBA", (3, 3), (12, 34, 56, 140))
        report = validate(image, Request(colors=1, palette=["#FF0000"]))
        self.assertFalse(report["passed"])
        self.assertFalse(report["checks"]["size"])
        self.assertFalse(report["checks"]["binary_alpha"])
        self.assertFalse(report["checks"]["fixed_palette"])


class ProjectTests(unittest.TestCase):
    def test_unicode_path_copy_and_server_free_reopen(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "참고 그림.png"
            fixture().save(source)
            project = import_image(source, root / "첫 번째 폴더", Request())
            copied = root / "다른 PC 경로" / "프로젝트"
            shutil.copytree(project.root, copied)
            opened = Project.open(copied)
            self.assertEqual(opened.asset(opened.manifest["assets"]["final"]).read_bytes(),
                             project.asset(project.manifest["assets"]["final"]).read_bytes())
            for value in opened.manifest["assets"].values():
                self.assertFalse(Path(value).is_absolute())
            self.assertEqual(opened.manifest["quality"], "not_reviewed")

    def test_project_cannot_overwrite_existing_folder(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(FileExistsError):
                Project.create(Path(tmp), Request().to_dict())

    def test_manifest_path_escape_is_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            project = Project.create(root, Request().to_dict())
            with self.assertRaises(ValueError):
                project.asset("../outside.png")
            project.manifest["assets"]["bad"] = "../outside.png"
            project.save()
            with self.assertRaises(ValueError):
                Project.open(root)

    def test_cli_invalid_request_creates_no_project(self):
        with TemporaryDirectory() as tmp, patch("sys.stderr", new_callable=io.StringIO):
            output = Path(tmp) / "invalid"
            self.assertEqual(main(["convert", "missing.png", "--colors", "0", "--output", str(output)]), 1)
            self.assertFalse(output.exists())


class ContractTests(unittest.TestCase):
    def test_request_rejects_bad_inputs(self):
        for values in ({"size": 16}, {"colors": 0}, {"seed": -1}, {"cfg": float("nan")},
                       {"palette": ["#QQ0000"]}, {"padding": 17}, {"steps": 0}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Request(**values)

    def test_result_parses_structured_json_and_text(self):
        self.assertEqual(normalize_result(SimpleNamespace(
            isError=False, structuredContent={"valid": True}, content=[])), {"valid": True})
        self.assertEqual(normalize_result(SimpleNamespace(
            isError=False, structuredContent=None,
            content=[SimpleNamespace(type="text", text='{"prompt_id":"abc"}')])), {"prompt_id": "abc"})

    def test_tool_error_is_not_treated_as_valid_response(self):
        with self.assertRaises(ProviderError):
            normalize_result(SimpleNamespace(isError=True, structuredContent=None,
                content=[SimpleNamespace(type="text", text="missing model")]))
        with self.assertRaises(ProviderError):
            normalize_result(SimpleNamespace(isError=False, structuredContent=None,
                content=[SimpleNamespace(type="text", text="not json")]))

    def test_nested_status_failure_has_precedence(self):
        self.assertEqual(job_state({"status": {"status_str": "success"}}), "completed")
        self.assertEqual(job_state({"status": "completed", "child": {"status": "error"}}), "failed")
        self.assertEqual(job_state({"status": "queued"}), "running")

    def test_workflow_is_known_unpaid_core_graph(self):
        request = Request(checkpoint="example.safetensors", seed=900)
        graph = build_workflow(request, "abc")
        self.assertEqual({node["class_type"] for node in graph.values()}, CORE_NODES)
        self.assertEqual(graph["5"]["inputs"]["seed"], 900)
        self.assertEqual(graph["4"]["inputs"]["batch_size"], 1)

    def test_secret_url_and_unknown_profile_fields_rejected(self):
        with self.assertRaises(ValueError):
            Profile(provider="comfy-http", url="https://name:secret@host")
        with self.assertRaises(ValueError):
            Profile(provider="cloud-magic")
        a = Profile(id="gpu", provider="comfy-http", url="https://a")
        b = Profile(id="gpu", provider="comfy-http", url="https://b")
        self.assertNotEqual(a.fingerprint(), b.fingerprint())
        with patch("pixelart.config.platform.node", return_value="other machine"):
            elsewhere = Profile().fingerprint()
        self.assertNotEqual(Profile().fingerprint(), elsewhere)


class ResumeTests(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_then_resume_submits_only_once(self):
        class Fake:
            submissions = 0
            completed = False
            async def preflight(self, checkpoint): return {"checkpoint": "example.safetensors"}
            async def validate(self, path): pass
            async def submit(self, path):
                self.submissions += 1
                return "job-1"
            async def status(self, job):
                return {"state": "completed" if self.completed else "running"}
            async def fetch(self, job, directory):
                directory.mkdir(parents=True, exist_ok=True)
                fixture().save(directory / "source.png")
                return [directory / "source.png"]
        fake = Fake()
        @asynccontextmanager
        async def connection(profile):
            yield fake
        with TemporaryDirectory() as tmp, patch("pixelart.pipeline.connect", connection):
            output = Path(tmp) / "job"
            project = await generate(output, Request(), Profile(), wait_seconds=0)
            self.assertEqual(project.manifest["state"], "running")
            fake.completed = True
            finished = await resume(Project.open(output), Profile(), wait_seconds=0)
            self.assertEqual(finished.manifest["state"], "review")
            self.assertEqual(fake.submissions, 1)

    async def test_ambiguous_submission_never_auto_retries(self):
        class Fake:
            async def preflight(self, checkpoint): return {"checkpoint": "example.safetensors"}
            async def validate(self, path): pass
            async def submit(self, path): raise SubmissionUnknown("connection lost")
        @asynccontextmanager
        async def connection(profile):
            yield Fake()
        with TemporaryDirectory() as tmp, patch("pixelart.pipeline.connect", connection):
            output = Path(tmp) / "job"
            with self.assertRaises(SubmissionUnknown):
                await generate(output, Request(), Profile())
            project = Project.open(output)
            self.assertEqual(project.manifest["state"], "submission_unknown")
            with self.assertRaises(ProviderError):
                await resume(project, Profile())

    async def test_resume_wrong_target_fails_before_connecting(self):
        with TemporaryDirectory() as tmp:
            project = Project.create(Path(tmp) / "project", Request().to_dict())
            project.update("running", job_id="abc", provider={"fingerprint": "different"})
            with patch("pixelart.pipeline.connect") as connection, self.assertRaises(ProviderError):
                await resume(project, Profile())
            connection.assert_not_called()


if __name__ == "__main__":
    unittest.main()
