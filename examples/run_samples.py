"""Run six real, sequential jobs. Existing confirmed jobs are resumed, never resubmitted."""
import argparse
import asyncio
import json
from pathlib import Path

from pixelart.config import Profile
from pixelart.pipeline import generate, resume
from pixelart.project import Project, write_json
from pixelart.request import Request


async def run(args):
    samples = json.loads((Path(__file__).parent / "samples.json").read_text(encoding="utf-8"))
    profile = Profile.load(args.profile)
    records = []
    for sample in samples:
        directory = args.output / sample["name"]
        print(json.dumps({"sample": sample["name"], "event": "starting"}), flush=True)
        request = Request(prompt=sample["prompt"], size=sample["size"], seed=sample["seed"],
                          generation_size=1024, steps=28, cfg=7)
        if directory.exists():
            project = Project.open(directory)
            saved = Request(**project.manifest["request"])
            # An unspecified checkpoint resolves on first submit; all requested settings must still match.
            request.checkpoint = saved.checkpoint
            if saved.to_dict() != request.to_dict():
                raise ValueError("existing sample request differs from the definition; use a new output directory")
            if project.manifest["state"] != "review":
                project = await resume(project, profile, 600)
        else:
            project = await generate(directory, request, profile, wait_seconds=600)
        records.append({"name": sample["name"], "project": directory.name,
                        "state": project.manifest["state"], "quality": project.manifest["quality"]})
        write_json(args.output / "index.json", {"samples": records})
        print(json.dumps({"sample": sample["name"], "state": project.manifest["state"]}), flush=True)
        if project.manifest["state"] != "review":
            raise RuntimeError("job not collected; rerun this command to resume")
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/evaluation"))
    parser.add_argument("--profile", type=Path)
    asyncio.run(run(parser.parse_args()))
