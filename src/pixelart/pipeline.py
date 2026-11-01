import asyncio
from contextlib import asynccontextmanager
import importlib.metadata
import shutil
import sys
import time
from pathlib import Path

from PIL import Image

from pixelart.config import Profile
from pixelart.pixels import convert, save_png
from pixelart.project import Project, write_json
from pixelart.prompts import resolve_prompts
from pixelart.providers.base import ProviderError, SubmissionUnknown, connect
from pixelart.request import Request
from pixelart.validation import validate, validate_export
from pixelart.workflow import build_workflow


def environment():
    return {"python": sys.version.split()[0], **{
        name: importlib.metadata.version(name) for name in ("Pillow", "numpy", "mcp")
    }}


def process(project: Project):
    started = time.monotonic()
    request = Request.from_dict(project.manifest["request"])
    source = project.asset(project.manifest["assets"]["source"])
    project.update("processing")
    with Image.open(source) as image:
        source_size = list(image.size)
        candidates, palette, notes = convert(image, request)
    reports = {}
    for name, image in candidates.items():
        destination = project.root / "candidates" / f"{name}.png"
        save_png(image, destination)
        preview = project.root / "previews" / f"{name}-{request.preview_scale}x.png"
        save_png(image.resize(tuple(value * request.preview_scale for value in image.size), Image.Resampling.NEAREST), preview)
        reports[name] = validate(image, request)
        if not reports[name]["passed"]:
            raise ValueError("pixel invariants failed for " + name)
        project.add_asset(name, destination)
        project.add_asset(name + "_preview", preview)
    final = project.root / "final.png"
    save_png(candidates[request.method], final)
    shutil.copy2(project.asset(project.manifest["assets"][request.method + "_preview"]),
                 project.root / "preview.png")
    project.add_asset("final", final)
    project.add_asset("preview", project.root / "preview.png")
    export = candidates[request.method].resize(request.export_dimensions, Image.Resampling.NEAREST)
    export_report = validate_export(export, candidates[request.method], request)
    if not export_report["passed"]:
        raise ValueError("integer export invariants failed")
    save_png(export, project.root / "export.png")
    project.add_asset("export", project.root / "export.png")
    dimensions = {**request.dimensions(), "source": source_size,
                  "generation": list(request.generation_dimensions) if "workflow" in project.manifest["assets"] else None}
    report = {
        "format_version": 1, "request": request.to_dict(), "candidates": reports,
        "dimensions": dimensions, "export": export_report,
        "method": request.method, "processing_seconds": round(time.monotonic() - started, 3),
        "notes": notes, "quality": "requires_visual_review",
        "palette": ["#" + bytes(c).hex().upper() for c in palette],
        "limitations": [
            "Nearest/majority are resampling baselines; grid is an experimental periodic-edge candidate.",
            "Border background removal may erase light edge details; compare the original.",
            "Passing pixel constraints does not establish artistic quality.",
        ],
    }
    write_json(project.root / "report.json", report)
    project.add_asset("report", project.root / "report.json")
    project.update("review", quality="not_reviewed", environment=environment())
    return project


def import_image(source: Path, output: Path, request: Request):
    # Read before creating a project so invalid source paths do not leave empty runs.
    with Image.open(source) as image:
        original = image.convert("RGBA")
    project = Project.create(output, request.to_dict())
    raw = project.root / "original" / ("input" + source.suffix.lower())
    raw.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, raw)
    project.add_asset("imported_original", raw)
    canonical = raw.parent / "source.png"
    save_png(original, canonical)
    project.add_asset("source", canonical)
    return process(project)


@asynccontextmanager
async def borrowed_provider(provider):
    yield provider


async def generate(output: Path, request: Request, profile: Profile, submit_only=False, wait_seconds=180, provider=None):
    project = Project.create(output, request.to_dict())
    project.manifest["provider"] = {
        "id": profile.id, "kind": profile.provider, "fingerprint": profile.fingerprint(),
    }
    project.save()
    try:
        context = connect(profile) if provider is None else borrowed_provider(provider)
        async with context as provider:
            optional_assets = {key: getattr(request, key) for key in ("lora", "vae") if getattr(request, key)}
            preflight = await provider.preflight(request.checkpoint, **optional_assets)
            request.checkpoint = preflight["checkpoint"]
            project.manifest["request"] = request.to_dict()
            write_json(project.root / "request.json", request.to_dict())
            prompts = resolve_prompts(request)
            project.manifest["prompts"] = prompts
            write_json(project.root / "prompts.json", prompts)
            project.add_asset("prompts", project.root / "prompts.json")
            workflow_path = project.root / "workflow.json"
            write_json(workflow_path, build_workflow(request, project.manifest["id"]))
            project.add_asset("workflow", workflow_path)
            await provider.validate(workflow_path)
            project.update("submitting", environment=environment())
            try:
                job_id = await provider.submit(workflow_path)
            except SubmissionUnknown:
                project.update("submission_unknown")
                raise
            project.update("running", job_id=job_id)
            if submit_only:
                return project
            return await collect(project, provider, wait_seconds)
    except Exception as exc:
        project.manifest["last_error"] = {"type": type(exc).__name__, "stage": project.manifest["state"]}
        project.save()
        # In-flight/uncertain jobs must stay resumable and must never be resubmitted.
        if project.manifest["state"] not in ("running", "fetching", "submission_unknown"):
            project.update("failed")
        raise


async def collect(project: Project, provider, wait_seconds: float):
    deadline = time.monotonic() + wait_seconds
    while True:
        status = await provider.status(project.manifest["job_id"])
        if status["state"] == "failed":
            project.update("failed", failure="generation_failed")
            raise ProviderError("generation failed; inspect ComfyUI's job error details")
        if status["state"] == "completed":
            break
        if time.monotonic() >= deadline:
            project.update("running")
            return project
        await asyncio.sleep(min(2, max(0, deadline - time.monotonic())))
    project.update("fetching")
    sources = await provider.fetch(project.manifest["job_id"], project.root / "original" / "raw")
    if len(sources) != 1:
        raise ProviderError("expected exactly one output PNG from the prototype workflow")
    canonical = project.root / "original" / "source.png"
    with Image.open(sources[0]) as image:
        save_png(image.convert("RGBA"), canonical)
    project.add_asset("source", canonical)
    return process(project)


async def resume(project: Project, profile: Profile, wait_seconds=180):
    if project.manifest["assets"].get("source"):
        # Finished assets stay usable on another PC without server credentials.
        return process(project)
    if project.manifest["state"] == "submission_unknown":
        raise ProviderError("submission is uncertain; inspect the original server; automatic resubmission is disabled")
    if not project.manifest.get("job_id"):
        raise ProviderError("project has no confirmed job id; no job will be resubmitted")
    if project.manifest.get("provider", {}).get("fingerprint") != profile.fingerprint():
        raise ProviderError("profile differs from the original job target; use the original profile")
    async with connect(profile) as provider:
        return await collect(project, provider, wait_seconds)
