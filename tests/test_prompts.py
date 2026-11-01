import unittest
import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from PIL import Image
from pixelart.cli import main
from pixelart.comparison import check_existing, load_definition, make_request, normalize_definition, run_comparison
from pixelart.config import Profile
from pixelart.pipeline import generate, resume
from pixelart.project import Project, write_json
from pixelart.prompts import ITEM_NEGATIVE, PROMPT_FIELDS, resolve_prompts, saved_prompts

from pixelart.request import Request
from pixelart.workflow import build_workflow


class PromptRegressionTests(unittest.TestCase):
    def test_common_default_does_not_suppress_people(self):
        graph = build_workflow(Request(prompt="blonde female knight saluting with sword pointing upward"), "knight")
        words = {word.strip() for word in graph["3"]["inputs"]["text"].split(",")}
        self.assertFalse(words & {"human", "person", "body", "face", "scenery", "room", "architecture"})

    def test_common_default_does_not_force_an_item(self):
        graph = build_workflow(Request(prompt="blonde female knight saluting"), "knight")
        self.assertNotIn("single isolated object", graph["2"]["inputs"]["text"])


class PromptControlTests(unittest.TestCase):
    def test_item_reproduces_the_previous_workflow_exactly(self):
        prompt = "  a gold coin  "
        graph = build_workflow(Request(prompt=prompt, prompt_preset="item"), "old")
        self.assertEqual(graph["2"]["inputs"]["text"],
            "masterpiece, best quality, pixel art, flat 2d sprite of a gold coin"
            ", (single isolated object:1.3), centered, simple silhouette, bold black outline, "
            "few flat solid colors, minimal details, generous empty margin, "
            "(plain solid white background:1.5), no shadow, no text, no frame")
        self.assertEqual(graph["3"]["inputs"]["text"],
            "photorealistic, 3d render, gradient background, complex background, text, "
            "letters, watermark, blurry, tiny details, multiple objects, cropped, out of frame, "
            "user interface, HUD, border, frame, screenshot, infographic, panel, scenery, human, person, "
            "body, face, room, architecture, photorealistic, reflection, cast shadow")

    def test_character_preserves_requested_subject_and_pose(self):
        description = "blonde female knight, sword salute pointing upward"
        result = resolve_prompts(Request(prompt=description, prompt_preset="character"))
        self.assertIn(description, result["positive"])
        self.assertNotIn("single isolated object", result["positive"])
        self.assertFalse(set(result["negative"].split(", ")) & {"human", "person", "body", "face"})
        self.assertEqual((result["preset"], result["preset_version"]), ("character", 1))

    def test_overrides_replace_each_complete_prompt_and_keep_exact_input(self):
        request = Request(prompt="knight", prompt_preset="item", positive_prompt=" custom positive ", negative_prompt="")
        result = resolve_prompts(request)
        self.assertEqual(result["positive"], " custom positive ")
        self.assertEqual(result["negative"], "")
        self.assertEqual(result["input"], {"prompt": "knight", "positive_prompt": " custom positive ", "negative_prompt": ""})
        graph = build_workflow(request, "x")
        self.assertEqual(graph["2"]["inputs"]["text"], result["positive"])
        self.assertEqual(graph["3"]["inputs"]["text"], "")
        self.assertEqual(resolve_prompts(Request(negative_prompt="my negative"))["negative"], "my negative")

    def test_invalid_options_fail_at_request_boundary(self):
        for values in ({"prompt_preset": "unknown"}, {"prompt_preset": []},
                       {"prompt_preset_version": 2}, {"prompt_preset_version": True},
                       {"prompt_preset_version": 1.0}, {"positive_prompt": " "},
                       {"positive_prompt": False}, {"negative_prompt": []}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Request(**values)

    def test_existing_positional_description_and_size_remain_compatible(self):
        request = Request("coin", 64)
        self.assertEqual((request.prompt, request.size, request.prompt_preset), ("coin", 64, "common"))

    def test_legacy_loader_is_item_while_new_request_is_common(self):
        self.assertEqual(Request.from_dict({"prompt": "coin"}).prompt_preset, "item")
        self.assertEqual(Request(prompt="coin").prompt_preset, "common")
        for preset in ("common", "item", "character"):
            request = Request(prompt_preset=preset, negative_prompt="")
            self.assertEqual(Request.from_dict(request.to_dict()), request)

    def test_preview_is_offline_and_project_edit_mix_is_rejected(self):
        with patch("pixelart.cli.doctor", side_effect=AssertionError("offline")), patch("pixelart.cli.generate", side_effect=AssertionError("offline")), patch("sys.stdout", new_callable=io.StringIO) as stdout:
            self.assertEqual(main(["prompts", "--prompt", "knight", "--prompt-preset", "character", "--negative-prompt", ""]), 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual((result["preset"], result["negative"]), ("character", ""))
        with patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(main(["prompts", "--project", "missing", "--negative-prompt", ""]), 1)
            self.assertIn("cannot be combined", stderr.getvalue())

    def test_legacy_project_shows_actual_saved_text_without_recomposing(self):
        with TemporaryDirectory() as tmp:
            project = Project.create(Path(tmp)/"legacy", {"prompt": "coin"})
            graph = build_workflow(Request(prompt="coin", prompt_preset="item"), "legacy")
            graph["2"]["inputs"]["text"] = "historic custom text"
            write_json(project.root/"workflow.json", graph)
            project.add_asset("workflow", project.root/"workflow.json")
            with patch("pixelart.prompts.resolve_prompts", side_effect=AssertionError("must not recompose")), patch("sys.stdout", new_callable=io.StringIO) as stdout:
                self.assertEqual(main(["prompts", "--project", str(project.root)]), 0)
                result = json.loads(stdout.getvalue())
            self.assertEqual(result["positive"], "historic custom text")
            self.assertIsNone(result["preset"])
            self.assertEqual(result["origin"], "legacy_workflow")

    def test_convert_project_has_no_generated_prompt_record(self):
        with TemporaryDirectory() as tmp:
            project = Project.create(Path(tmp)/"import", Request().to_dict())
            self.assertIsNone(saved_prompts(project))
            with patch("sys.stderr", new_callable=io.StringIO) as stderr:
                self.assertEqual(main(["prompts", "--project", str(project.root)]), 1)
            self.assertIn("no saved generation prompts", stderr.getvalue())

    def test_definition_pins_common_prompts_identically_across_variants(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            write_json(root/"samples.json", [{"name":"knight","prompt":"knight"}])
            config={"settings":{"prompt_preset":"character", "negative_prompt":""},
                    "variants":[{"name":"base","checkpoint":"base"},{"name":"pixel","checkpoint":"base","lora":"pixel"}]}
            write_json(root/"variants.json", config)
            data=load_definition(root/"samples.json",root/"variants.json",Profile())
            self.assertEqual(data["format_version"], 2)
            prompts=[resolve_prompts(make_request(data,v,data["samples"][0])) for v in data["variants"]]
            self.assertEqual(prompts[0],prompts[1])
            self.assertEqual(data["effective_prompts"]["knight"], prompts[0])
            for region in ("variants", "samples"):
                for key, value in (("prompt_preset","item"),("prompt_preset_version",1),("positive_prompt","other"),("negative_prompt","other")):
                    changed=deepcopy(data)
                    changed[region][0][key]=value
                    with self.subTest(region=region,key=key), self.assertRaises(ValueError):
                        normalize_definition(changed)
            data["effective_prompts"]["knight"]["positive"]="tampered"
            with self.assertRaisesRegex(ValueError,"pinned effective"):
                normalize_definition(data)

    def test_legacy_definition_equivalence_is_explicit_item_only(self):
        old={"format_version":1,"settings":{},"variants":[{"name":"base","checkpoint":"base"}],
             "samples":[{"name":"coin","prompt":"coin"}],"profile_fingerprint":Profile().fingerprint()}
        item=deepcopy(old);item["format_version"]=2;item["settings"]["prompt_preset"]="item"
        common=deepcopy(old);common["format_version"]=2
        self.assertEqual(normalize_definition(old),normalize_definition(item))
        self.assertNotEqual(normalize_definition(old),normalize_definition(common))

    def test_comparison_reuse_requires_saved_effective_text(self):
        with TemporaryDirectory() as tmp:
            request = Request(prompt="coin", prompt_preset="item")
            project = Project.create(Path(tmp)/"incomplete", request.to_dict())
            with self.assertRaisesRegex(ValueError, "no saved generation prompts"):
                check_existing(project.root, request)

    def test_existing_workflow_tamper_is_rejected_even_if_request_matches(self):
        with TemporaryDirectory() as tmp:
            request=Request(prompt="coin",prompt_preset="item")
            project=Project.create(Path(tmp)/"old",request.to_dict())
            graph=build_workflow(request,"old");graph["3"]["inputs"]["text"]="changed"
            write_json(project.root/"workflow.json",graph);project.add_asset("workflow",project.root/"workflow.json")
            with self.assertRaisesRegex(ValueError,"workflow prompts differ"):
                check_existing(project.root,request)


class PromptPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_submission_metadata_workflow_and_offline_inspection_agree(self):
        fake=AsyncMock();fake.preflight.return_value={"checkpoint":"base"};fake.submit.return_value="job"
        request=Request(prompt="knight",prompt_preset="character",negative_prompt="",lora="pixel",vae="fixed")
        with TemporaryDirectory() as tmp:
            project=await generate(Path(tmp)/"new",request,Profile(),submit_only=True,provider=fake)
            opened=Project.open(project.root)
            expected=resolve_prompts(request)
            self.assertEqual(opened.manifest["prompts"],expected)
            self.assertEqual(json.loads((project.root/"prompts.json").read_text()),expected)
            self.assertEqual(json.loads((project.root/"request.json").read_text()),request.to_dict())
            self.assertEqual(saved_prompts(opened),expected)
            fake.submit.assert_awaited_once()
            graph=json.loads((project.root/"workflow.json").read_text())
            self.assertEqual(graph["3"]["inputs"]["clip"],["8",1])
            with patch("sys.stdout",new_callable=io.StringIO) as stdout:
                self.assertEqual(main(["inspect",str(project.root)]),3)
                self.assertEqual(json.loads(stdout.getvalue())["prompts"],expected)
            graph["2"]["inputs"]["text"]="edited";write_json(project.root/"workflow.json",graph)
            with self.assertRaisesRegex(ValueError,"differ from workflow"):
                saved_prompts(opened)

    async def test_legacy_source_resume_preserves_workflow_and_avoids_submission(self):
        with TemporaryDirectory() as tmp:
            project=Project.create(Path(tmp)/"old",{"prompt":"coin","size":32,"background":"alpha"})
            graph=build_workflow(Request(prompt="coin",prompt_preset="item"),"old")
            write_json(project.root/"workflow.json",graph);project.add_asset("workflow",project.root/"workflow.json")
            source=project.root/"source.png";Image.new("RGBA",(32,32),"red").save(source);project.add_asset("source",source)
            original=(project.root/"workflow.json").read_bytes()
            with patch("pixelart.pipeline.connect",side_effect=AssertionError("no generation server")):
                result=await resume(Project.open(project.root),Profile())
            self.assertEqual(result.manifest["state"],"review")
            self.assertEqual((project.root/"workflow.json").read_bytes(),original)
            self.assertEqual(json.loads((project.root/"report.json").read_text())["request"]["prompt_preset"],"item")
            self.assertEqual(saved_prompts(result)["negative"],ITEM_NEGATIVE)

    async def test_legacy_completed_comparison_reuses_outputs_without_server(self):
        profile=Profile()
        old={"format_version":1,"settings":{"background":"alpha"},"variants":[{"name":"base","checkpoint":"base"}],
             "samples":[{"name":"coin","prompt":"coin"}],"profile_fingerprint":profile.fingerprint()}
        with TemporaryDirectory() as tmp, patch("sys.stdout",new_callable=io.StringIO):
            root=Path(tmp);request=make_request(old,old["variants"][0],old["samples"][0])
            legacy={k:v for k,v in request.to_dict().items() if k not in PROMPT_FIELDS}
            project=Project.create(root/"base"/"coin",legacy)
            graph=build_workflow(request,"old");write_json(project.root/"workflow.json",graph);project.add_asset("workflow",project.root/"workflow.json")
            source=project.root/"source.png";Image.new("RGBA",(32,32),"red").save(source);project.add_asset("source",source)
            await resume(project,profile)
            project.update("review",job_id="historic-job")
            write_json(root/"comparison.json",{"definition":old,"records":[{"variant":"base","sample":"coin","client_elapsed_seconds":12.5}]})
            data=deepcopy(old);data["format_version"]=2;data["settings"]["prompt_preset"]="item"
            with patch("pixelart.comparison.connect",side_effect=AssertionError("no server")):
                records=await run_comparison(root,data,profile)
            self.assertEqual(records[0]["job_id"],"historic-job")
            self.assertEqual(records[0]["client_elapsed_seconds"],12.5)
            changed=deepcopy(data);changed["settings"]["prompt_preset"]="common"
            before=(root/"comparison.json").read_bytes()
            with self.assertRaisesRegex(ValueError,"definition changed"):
                await run_comparison(root,changed,profile)
            self.assertEqual((root/"comparison.json").read_bytes(),before)

    async def test_sample_runner_accepts_unchanged_historic_item_request(self):
        spec = importlib.util.spec_from_file_location("sample_runner_prompts", "examples/run_samples.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        restore = Request.from_dict
        for legacy in (True, False):
            with self.subTest(legacy=legacy), TemporaryDirectory() as tmp, patch("sys.stdout", new_callable=io.StringIO):
                root = Path(tmp)
                sample = {"name": "coin", "prompt": "coin", "size": 32, "seed": 42}
                write_json(root / "samples.json", [sample])
                request = Request(prompt="coin", checkpoint="base", prompt_preset="item")
                saved = {key: value for key, value in request.to_dict().items()
                         if not legacy or key not in PROMPT_FIELDS}
                project = Project.create(root / "output" / "coin", saved)
                project.update("review")
                restored = []

                def load_request(values):
                    result = restore(values)
                    restored.append(result)
                    return result

                with patch.object(module, "__file__", str(root / "run_samples.py")), \
                     patch.object(module, "generate", side_effect=AssertionError("must reuse")), \
                     patch.object(module, "resume", side_effect=AssertionError("already completed")), \
                     patch.object(module.Request, "from_dict", side_effect=load_request) as loader:
                    records = await module.run(SimpleNamespace(profile=None, output=root / "output"))
                    loader.assert_called_once_with(saved)
                self.assertEqual(records[0]["state"], "review")
                self.assertEqual(restored[0].prompt_preset, "item")
                self.assertEqual(resolve_prompts(restored[0])["negative"], ITEM_NEGATIVE)
                self.assertEqual(restored[0].to_dict(), request.to_dict())


if __name__ == "__main__":
    unittest.main()
