"""Controlled model comparison; immutable definitions and no automatic resubmission."""
from pathlib import Path
import asyncio
import json
import re
import time

from PIL import Image

from pixelart.config import Profile
from pixelart.pipeline import generate, resume
from pixelart.project import Project, write_json
from pixelart.providers.base import connect
from pixelart.request import Request


def load_definition(samples_path: Path, variants_path: Path, profile: Profile):
    samples = json.loads(samples_path.read_text(encoding="utf-8"))
    configuration = json.loads(variants_path.read_text(encoding="utf-8"))
    variants = configuration["variants"]
    for collection in (samples, variants):
        names = [item["name"] for item in collection]
        if not names or len(names) != len(set(names)):
            raise ValueError("sample and variant names must be nonempty and unique")
        if any(not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name) for name in names):
            raise ValueError("names must be safe lowercase identifiers")
    definition = {
        "format_version": 1, "samples": samples, "variants": variants,
        "settings": configuration["settings"], "profile_fingerprint": profile.fingerprint(),
    }
    for variant in variants:
        if not variant.get("checkpoint"):
            raise ValueError("comparison checkpoints must be explicit")
        for sample in samples:
            make_request(definition, variant, sample)
    return definition


def make_request(definition, variant, sample):
    settings = {**definition["settings"], **{k: v for k, v in variant.items() if k != "name"},
                **{k: v for k, v in sample.items() if k != "name"}}
    return Request(**settings)


def check_existing(path: Path, expected: Request):
    if not path.exists():
        return None
    project = Project.open(path)
    actual = Request(**project.manifest["request"]).to_dict()
    if actual != expected.to_dict():
        raise ValueError("existing project settings differ; use a new comparison output directory")
    return project


class PreparedProvider:
    """Reuse discovery within one variant; every graph is still validated on the live target."""
    def __init__(self, provider, expected, preflight):
        self.provider, self.expected, self.preflight_result = provider, expected, preflight

    async def preflight(self, checkpoint, lora="", vae=""):
        if (checkpoint, lora, vae) != self.expected:
            raise ValueError("prepared provider does not match the request")
        return self.preflight_result

    def __getattr__(self, name):
        return getattr(self.provider, name)


def describe(project: Project, variant, sample, elapsed=None):
    report = json.loads(project.asset("report.json").read_text(encoding="utf-8"))
    with Image.open(project.asset(project.manifest["assets"]["source"])) as source:
        count = source.convert("RGB").getcolors(maxcolors=2**24)
        source_colors = len(count) if count else None
    grid = next((note["grid_recovery"] for note in report["notes"]
                 if isinstance(note, dict) and "grid_recovery" in note), {})
    return {
        "variant": variant, "sample": sample, "project": f"{variant}/{sample}",
        "state": project.manifest["state"], "job_id": project.manifest.get("job_id"),
        "request": project.manifest["request"], "source_color_count": source_colors,
        "technical_pass": all(v["passed"] for v in report["candidates"].values()),
        "final_colors": report["candidates"][report["method"]]["visible_colors"],
        "grid_detected": grid.get("detected", False),
        "client_elapsed_seconds": elapsed, "quality": "requires_visual_review",
    }


async def run_comparison(output: Path, definition: dict, profile: Profile, wait_seconds=600):
    output.mkdir(parents=True, exist_ok=True)
    ledger_path = output / "comparison.json"
    old_records = {}
    if ledger_path.exists():
        previous = json.loads(ledger_path.read_text(encoding="utf-8"))
        if previous["definition"] != definition:
            raise ValueError("comparison definition changed; choose a new output directory")
        old_records = {(r["variant"], r["sample"]): r for r in previous["records"]}
    records = []
    ledger_records = dict(old_records)
    write_json(ledger_path, {"definition": definition, "records": list(old_records.values())})
    for variant in definition["variants"]:
        projects = []
        for sample in definition["samples"]:
            expected = make_request(definition, variant, sample)
            path = output / variant["name"] / sample["name"]
            projects.append((sample, expected, path, check_existing(path, expected)))
        unfinished = any(project is None or project.manifest["state"] != "review"
                         for _, _, _, project in projects)

        async def execute(provider=None):
            for sample, request, path, project in projects:
                started = time.monotonic()
                print(json.dumps({"variant": variant["name"], "sample": sample["name"],
                                  "event": "starting"}), flush=True)
                reused = project is not None and project.manifest["state"] == "review"
                if project is None:
                    project = await generate(path, request, profile, wait_seconds=wait_seconds, provider=provider)
                elif not reused:
                    project = await resume(project, profile, wait_seconds)
                if project.manifest["state"] != "review":
                    raise RuntimeError("generation still running; rerun comparison to resume, not resubmit")
                key = (variant["name"], sample["name"])
                elapsed = old_records.get(key, {}).get("client_elapsed_seconds") if reused else round(time.monotonic() - started, 3)
                record = describe(project, *key, elapsed)
                records.append(record)
                ledger_records[key] = record
                write_json(ledger_path, {"definition": definition, "records": list(ledger_records.values())})
                print(json.dumps({"variant": variant["name"], "sample": sample["name"], "state": "review"}), flush=True)
        if unfinished:
            async with connect(profile) as active:
                selected = (variant["checkpoint"], variant.get("lora", ""), variant.get("vae", ""))
                assets = {k: variant[k] for k in ("lora", "vae") if variant.get(k)}
                preflight = await active.preflight(variant["checkpoint"], **assets)
                await execute(PreparedProvider(active, selected, preflight))
        else:
            await execute()
    return records
