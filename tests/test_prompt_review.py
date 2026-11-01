"""Regressions from the GitHub review of prompt controls."""
from contextlib import asynccontextmanager
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

from PIL import Image

from pixelart.comparison import make_request, run_comparison
from pixelart.config import Profile
from pixelart.pipeline import process
from pixelart.project import Project
from pixelart.prompts import resolve_prompts


def definition(profile):
    return {"format_version": 2, "profile_fingerprint": profile.fingerprint(),
            "settings": {"background": "alpha"},
            "variants": [{"name": "base", "checkpoint": "base"}],
            "samples": [{"name": "coin", "prompt": "coin"}]}


def source_at(directory):
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "source.png"
    Image.new("RGBA", (32, 32), "red").save(source)
    return source


def snapshot_project(root, data, profile):
    request = make_request(data, data["variants"][0], data["samples"][0])
    project = Project.create(root / "base" / "coin", request.to_dict())
    project.update("running", job_id="confirmed-job", prompts=resolve_prompts(request),
                   provider={"fingerprint": profile.fingerprint()})
    return project


class WorkflowReuseReviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_completed_snapshot_without_workflow_is_not_reused(self):
        profile = Profile()
        data = definition(profile)
        with TemporaryDirectory() as tmp, patch("sys.stdout", new_callable=io.StringIO):
            root = Path(tmp)
            project = snapshot_project(root, data, profile)
            project.add_asset("source", source_at(project.root / "original"))
            process(project)
            self.assertEqual(project.manifest["state"], "review")
            with patch("pixelart.comparison.connect", side_effect=AssertionError("must not generate")), \
                 self.assertRaisesRegex(ValueError, "workflow"):
                await run_comparison(root, data, profile)

    async def test_pending_snapshot_without_workflow_can_resume_without_resubmitting(self):
        profile = Profile()
        data = definition(profile)
        for saved_source in (False, True):
            with self.subTest(saved_source=saved_source), TemporaryDirectory() as tmp, \
                 patch("sys.stdout", new_callable=io.StringIO):
                root = Path(tmp)
                project = snapshot_project(root, data, profile)
                if saved_source:
                    project.add_asset("source", source_at(project.root / "original"))
                    project.update("processing")
                fake = AsyncMock()
                fake.status.return_value = {"state": "completed"}
                fake.preflight.side_effect = AssertionError("no new model discovery")
                fake.submit.side_effect = AssertionError("must never resubmit")

                async def fetch(job, directory):
                    return [source_at(directory)]
                fake.fetch.side_effect = fetch

                @asynccontextmanager
                async def connect(profile):
                    yield fake

                with patch("pixelart.comparison.connect", side_effect=AssertionError("no new submission")), \
                     patch("pixelart.pipeline.connect", connect):
                    records = await run_comparison(root, data, profile)
                self.assertEqual((records[0]["state"], records[0]["job_id"]), ("review", "confirmed-job"))
                self.assertTrue(records[0]["technical_pass"])
                fake.preflight.assert_not_awaited()
                fake.submit.assert_not_awaited()
                if saved_source:
                    fake.status.assert_not_awaited()
                    fake.fetch.assert_not_awaited()
                else:
                    fake.status.assert_awaited_once_with("confirmed-job")
                    fake.fetch.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
