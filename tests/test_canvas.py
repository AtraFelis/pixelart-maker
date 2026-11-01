"""Canvas dimensions, exact exports and backward-compatible recovery."""
import asyncio
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

import numpy as np
from PIL import Image, ImageDraw

from pixelart.cli import main
from pixelart.comparison import make_request, normalize_definition, run_comparison
from pixelart.config import Profile
from pixelart.pipeline import generate, import_image, resume
from pixelart.pixels import convert, majority_resize
from pixelart.project import Project, write_json
from pixelart.request import Request
from pixelart.validation import validate, validate_export
from pixelart.workflow import build_workflow


def definition():
    return {"format_version": 2, "settings": {}, "profile_fingerprint": Profile().fingerprint(),
            "variants": [{"name": "base", "checkpoint": "base"}],
            "samples": [{"name": "coin", "prompt": "coin", "size": 32}]}


class CanvasRequestTests(unittest.TestCase):
    def test_square_sizes_and_existing_positional_api(self):
        for size in (32, 64, 128, 256, 512, 1024, 2048):
            with self.subTest(size=size):
                request = Request("coin", size)
                self.assertEqual(request.canvas_dimensions, (size, size))
                self.assertEqual(request.export_dimensions, (size, size))
        self.assertEqual(Request().canvas_dimensions, (32, 32))

    def test_rectangular_roundtrip_separates_three_sizes(self):
        request = Request(width=480, height=270, export_scale=4,
                          generation_width=1024, generation_height=576)
        self.assertEqual(request.canvas_dimensions, (480, 270))
        self.assertEqual(request.export_dimensions, (1920, 1080))
        self.assertEqual(request.generation_dimensions, (1024, 576))
        self.assertIsNone(request.size)
        self.assertIsNone(request.generation_size)
        self.assertEqual(Request.from_dict(json.loads(json.dumps(request.to_dict()))), request)

    def test_old_requests_default_to_original_square_and_scale_one(self):
        request = Request.from_dict({"prompt": "coin", "size": 64})
        self.assertEqual((request.canvas_dimensions, request.generation_dimensions), ((64, 64), (1024, 1024)))
        self.assertEqual((request.export_scale, request.prompt_preset), (1, "item"))

    def test_invalid_or_unpaired_canvas_and_padding(self):
        for values in ({"size": 31}, {"size": 2049}, {"size": 64.0}, {"size": True},
                       {"width": 480}, {"height": 270}, {"width": 480, "height": 0},
                       {"width": 480.0, "height": 270}, {"size": 64, "width": 480, "height": 270},
                       {"width": 256, "height": 32, "padding": 16}, {"padding": 1.5}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Request(**values)
        self.assertEqual(Request(width=256, height=32, padding=15).canvas_dimensions, (256, 32))

    def test_export_budget_is_checked_without_allocating_images(self):
        self.assertEqual(Request(size=1024, export_scale=4).export_dimensions, (4096, 4096))
        self.assertEqual(Request(width=2048, height=32, export_scale=4).export_dimensions, (8192, 128))
        for values in ({"export_scale": 0}, {"export_scale": 17}, {"export_scale": True},
                       {"export_scale": 2.0}, {"size": 2048, "export_scale": 5},
                       {"width": 1920, "height": 1080, "export_scale": 3}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Request(**values)

    def test_generation_budget_and_alignment(self):
        for values in ({"generation_width": 1024}, {"generation_height": 576},
                       {"generation_width": 1024, "generation_height": 575},
                       {"generation_width": 1024.0, "generation_height": 576},
                       {"generation_width": 2048, "generation_height": 1024},
                       {"generation_width": 192, "generation_height": 256},
                       {"generation_size": 512, "generation_width": 1024, "generation_height": 576}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Request(**values)
        self.assertEqual(Request(generation_width=2048, generation_height=512).generation_dimensions, (2048, 512))

    def test_preview_limits_preserve_small_sizes(self):
        for size, scale in ((32, 16), (64, 16), (128, 8), (256, 4), (1024, 1), (2048, 1)):
            with self.subTest(size=size):
                self.assertEqual(Request(size=size).preview_scale, scale)
        self.assertEqual(Request(width=480, height=270).dimensions()["preview"], [960, 540])

    def test_workflow_uses_generation_dimensions_not_export_dimensions(self):
        request = Request(width=480, height=270, export_scale=4, generation_width=1024, generation_height=576)
        graph = build_workflow(request, "wide")
        self.assertEqual(graph["4"]["inputs"], {"width": 1024, "height": 576, "batch_size": 1})
        self.assertEqual(build_workflow(Request(size=1024), "old")["4"]["inputs"]["width"], 1024)


class CanvasPixelTests(unittest.TestCase):
    def test_rectangular_fit_preserves_aspect_ratio_and_padding(self):
        request = Request(width=128, height=96, padding=4, background="alpha", colors=1, palette=["#FF0000"])
        candidates, _, notes = convert(Image.new("RGBA", (64, 32), "red"), request)
        for image in candidates.values():
            self.assertEqual(image.size, (128, 96))
            self.assertEqual(image.getchannel("A").getbbox(), (4, 18, 124, 78))
            self.assertTrue(validate(image, request)["passed"])
        self.assertTrue(any(isinstance(note, str) and "enlarges" in note for note in notes))

    def test_empty_rectangular_canvas_keeps_explicit_empty_warning(self):
        request = Request(width=128, height=96, background="alpha")
        candidates, _, notes = convert(Image.new("RGBA", (64, 32)), request)
        for image in candidates.values():
            self.assertEqual(image.size, (128, 96))
            self.assertIsNone(image.getchannel("A").getbbox())
        self.assertTrue(any(isinstance(note, str) and "Empty foreground" in note for note in notes))

    def test_large_native_canvases_obey_pixel_constraints(self):
        for size in (128, 256, 1024):
            request = Request(size=size, background="alpha", colors=2)
            source = Image.new("RGBA", (32, 32), "red")
            ImageDraw.Draw(source).rectangle((16, 0, 31, 31), fill="blue")
            candidates, _, _ = convert(source, request)
            self.assertTrue(validate(candidates["majority"], request)["passed"])

    def test_majority_enlargement_retains_floor_sampling_and_alpha(self):
        source = Image.new("RGBA", (3, 2))
        source.putdata([(255, 0, 0, 255), (0, 255, 0, 20), (7, 8, 9, 0),
                        (0, 0, 255, 255), (255, 255, 0, 255), (0, 255, 255, 255)])
        actual = np.asarray(majority_resize(source, (5, 3)))
        expected = np.array([
            [(255, 0, 0, 255), (255, 0, 0, 255), (0, 255, 0, 255), (0, 255, 0, 255), (0, 0, 0, 0)],
            [(255, 0, 0, 255), (255, 0, 0, 255), (0, 255, 0, 255), (0, 255, 0, 255), (0, 0, 0, 0)],
            [(0, 0, 255, 255), (0, 0, 255, 255), (255, 255, 0, 255), (255, 255, 0, 255), (0, 255, 255, 255)],
        ], dtype=np.uint8)
        np.testing.assert_array_equal(actual, expected)

    def test_majority_downsampling_votes_and_alpha_threshold_stay_unchanged(self):
        source = Image.new("RGBA", (4, 4))
        ImageDraw.Draw(source).rectangle((0, 0, 1, 1), fill="red")
        ImageDraw.Draw(source).rectangle((2, 2, 3, 3), fill="blue")
        source.putpixel((2, 0), (0, 255, 0, 255))
        self.assertEqual(list(map(tuple, np.asarray(majority_resize(source, (2, 2))).reshape(-1, 4))),
                         [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 0, 0), (0, 0, 255, 255)])

    def test_export_checks_every_pixel_of_each_integer_block(self):
        request = Request(size=32, export_scale=4)
        source = Image.new("RGBA", (32, 32), "red")
        source.putpixel((3, 4), (0, 0, 0, 0))
        export = source.resize(request.export_dimensions, Image.Resampling.NEAREST)
        self.assertTrue(validate_export(export, source, request)["passed"])
        expected = np.repeat(np.repeat(np.asarray(source), 4, axis=0), 4, axis=1)
        np.testing.assert_array_equal(np.asarray(export), expected)
        export.putpixel((1, 1), (0, 0, 255, 255))
        self.assertFalse(validate_export(export, source, request)["checks"]["pixel_replication"])
        self.assertFalse(validate_export(source, source, request)["checks"]["size"])


class CanvasCLITests(unittest.TestCase):
    def test_invalid_dimensions_fail_before_connecting_or_creating_output(self):
        bad_arguments = (["--size", "9999"], ["--width", "480"],
                         ["--size", "32", "--width", "480", "--height", "270"],
                         ["--size", "2048", "--export-scale", "16"],
                         ["--generation-width", "2048", "--generation-height", "2048"],
                         ["--generation-size", "1024", "--generation-width", "1024", "--generation-height", "576"])
        for arguments in bad_arguments:
            with self.subTest(arguments=arguments), TemporaryDirectory() as tmp, \
                 patch("sys.stderr", new_callable=io.StringIO), patch("pixelart.cli.generate") as generate_call:
                output = Path(tmp) / "invalid"
                self.assertEqual(main(["generate", "--output", str(output), *arguments]), 1)
                generate_call.assert_not_called()
                self.assertFalse(output.exists())

    def test_real_convert_cli_saves_full_hd_export_and_portable_dimensions(self):
        with TemporaryDirectory() as tmp, patch("sys.stdout", new_callable=io.StringIO) as stdout:
            root = Path(tmp)
            source = root / "source.png"
            Image.new("RGBA", (48, 27), "red").save(source)
            output = root / "wide"
            args = ["convert", str(source), "--output", str(output), "--width", "480", "--height", "270",
                    "--export-scale", "4", "--background", "alpha", "--colors", "1", "--padding", "0"]
            self.assertEqual(main(args), 0)
            summary = json.loads(stdout.getvalue())
            self.assertEqual(summary["dimensions"]["canvas"], [480, 270])
            self.assertEqual(summary["dimensions"]["export"], [1920, 1080])
            with Image.open(output / "final.png") as canvas, Image.open(output / "export.png") as export:
                self.assertEqual(canvas.size, (480, 270))
                self.assertEqual(export.size, (1920, 1080))
                self.assertEqual(export.tobytes(), canvas.resize(export.size, Image.Resampling.NEAREST).tobytes())
            with Image.open(output / "preview.png") as preview:
                self.assertEqual(preview.size, (960, 540))
            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            self.assertTrue(report["export"]["passed"])
            self.assertIsNone(report["dimensions"]["generation"])
            moved = root / "다른 PC 경로"
            shutil.copytree(output, moved)
            self.assertEqual(Project.open(moved).manifest["request"], Project.open(output).manifest["request"])
            self.assertFalse(any(Path(path).is_absolute() for path in Project.open(moved).manifest["assets"].values()))

    def test_comparison_dimension_allowlists_and_legacy_defaults(self):
        data = definition()
        data["settings"] = {"generation_width": 1024, "generation_height": 576, "export_scale": 4}
        data["samples"][0] = {"name": "wide", "prompt": "landscape", "width": 480, "height": 270}
        normalized = normalize_definition(data)
        request = make_request(normalized, normalized["variants"][0], normalized["samples"][0])
        self.assertEqual((request.canvas_dimensions, request.export_dimensions), ((480, 270), (1920, 1080)))
        for region, key, value in (("variants", "width", 480), ("variants", "export_scale", 4),
                                   ("samples", "generation_width", 1024), ("samples", "export_scale", 4)):
            changed = deepcopy(data)
            changed[region][0][key] = value
            with self.subTest(region=region, key=key), self.assertRaises(ValueError):
                normalize_definition(changed)
        changed = deepcopy(data)
        changed["settings"]["width"] = 480
        with self.assertRaises(ValueError):
            normalize_definition(changed)
        legacy = definition()
        explicit = deepcopy(legacy)
        explicit["settings"]["export_scale"] = 1
        self.assertEqual(normalize_definition(legacy), normalize_definition(explicit))
        for value in (legacy, explicit):
            value["format_version"] = 1
        self.assertEqual(normalize_definition(legacy), normalize_definition(explicit))

    def test_comparison_accepts_null_square_aliases_for_saved_rectangles(self):
        data = definition()
        data["samples"][0].update(size=None, width=480, height=270)
        data["settings"].update(generation_size=None, generation_width=1024, generation_height=576)
        normalized = normalize_definition(data)
        request = make_request(normalized, normalized["variants"][0], normalized["samples"][0])
        self.assertEqual(request.canvas_dimensions, (480, 270))
        self.assertEqual(request.generation_dimensions, (1024, 576))

    def test_comparison_rejects_ambiguous_square_and_rectangle(self):
        for region in ("samples", "settings"):
            data = definition()
            if region == "samples":
                data[region][0].update(width=480, height=270)
            else:
                data[region].update(generation_size=1024, generation_width=1024, generation_height=576)
            with self.subTest(region=region), self.assertRaises(ValueError):
                normalize_definition(data)


class CanvasRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_rectangular_submission_persists_actual_generation_graph(self):
        fake = AsyncMock()
        fake.preflight.return_value = {"checkpoint": "base"}
        fake.submit.return_value = "confirmed-job"
        request = Request(width=480, height=270, export_scale=4, generation_width=1024, generation_height=576)
        with TemporaryDirectory() as tmp:
            project = await generate(Path(tmp) / "job", request, Profile(), submit_only=True, provider=fake)
            graph = json.loads(project.asset(project.manifest["assets"]["workflow"]).read_text())
            self.assertEqual(graph["4"]["inputs"]["width"], 1024)
            self.assertEqual(graph["4"]["inputs"]["height"], 576)
            self.assertEqual(Request.from_dict(Project.open(project.root).manifest["request"]), request)
            fake.validate.assert_awaited_once()
            fake.submit.assert_awaited_once()

    async def test_legacy_resume_keeps_workflow_original_and_small_preview(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            values = {"prompt": "coin", "size": 64, "generation_size": 512, "background": "alpha"}
            project = Project.create(root / "old", values)
            source = project.root / "source.png"
            Image.new("RGBA", (512, 512), "red").save(source)
            project.add_asset("source", source)
            graph = project.root / "workflow.json"
            write_json(graph, build_workflow(Request.from_dict(values), "old"))
            project.add_asset("workflow", graph)
            project.update("running", job_id="old-confirmed")
            before = (source.read_bytes(), graph.read_bytes())
            with patch("pixelart.pipeline.connect", side_effect=AssertionError("offline")):
                result = await resume(Project.open(project.root), Profile())
            self.assertEqual(result.manifest["job_id"], "old-confirmed")
            self.assertEqual((source.read_bytes(), graph.read_bytes()), before)
            self.assertEqual(result.manifest["assets"]["majority_preview"], "previews/majority-16x.png")
            with Image.open(project.root / "final.png") as final, Image.open(project.root / "export.png") as export:
                self.assertEqual(final.size, (64, 64))
                self.assertEqual(final.tobytes(), export.tobytes())

    async def test_changed_export_scale_does_not_overwrite_existing_comparison_ledger(self):
        data = normalize_definition(definition())
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "comparison.json"
            write_json(ledger, {"definition": data, "records": []})
            before = ledger.read_bytes()
            changed = deepcopy(data)
            changed["settings"]["export_scale"] = 2
            with patch("pixelart.comparison.connect", side_effect=AssertionError("no server")), \
                 self.assertRaisesRegex(ValueError, "definition changed"):
                await run_comparison(root, changed, Profile())
            self.assertEqual(ledger.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
