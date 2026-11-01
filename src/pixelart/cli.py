import argparse
import asyncio
import json
from pathlib import Path
import sys

from pixelart.config import Profile
from pixelart.pipeline import generate, import_image, resume
from pixelart.project import Project
from pixelart.providers.base import connect
from pixelart.request import Request
from pixelart.prompts import PRESETS, PROMPT_FIELDS, resolve_prompts, saved_prompts


def prompt_options(command, preview=False):
    command.add_argument("--prompt-preset", choices=PRESETS, default=None if preview else "common")
    command.add_argument("--positive-prompt", help="Replace the entire composed positive prompt")
    command.add_argument("--negative-prompt", help="Replace the entire negative prompt; empty string disables it")


def parser():
    result = argparse.ArgumentParser(description="Generate, compare and validate 32/64-pixel game assets.")
    sub = result.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="Check a generation target without generating")
    doctor.add_argument("--profile", type=Path)
    doctor.add_argument("--checkpoint", default="")
    doctor.add_argument("--lora", default="")
    doctor.add_argument("--vae", default="")
    for name in ("generate", "convert"):
        command = sub.add_parser(name)
        command.add_argument("--output", type=Path, required=True, help="New project directory; never overwritten")
        command.add_argument("--prompt", default="red potion bottle, cork stopper, game inventory icon")
        command.add_argument("--size", type=int, choices=(32, 64), default=32)
        command.add_argument("--colors", type=int, default=16)
        command.add_argument("--seed", type=int, default=42)
        command.add_argument("--background", choices=("corner", "alpha", "opaque"), default="corner")
        command.add_argument("--tolerance", type=int, default=36)
        command.add_argument("--padding", type=int, default=2)
        command.add_argument("--method", choices=("nearest", "majority", "grid"), default="majority")
        command.add_argument("--palette", help="Comma-separated #RRGGBB colors")
        if name == "generate":
            prompt_options(command)
            command.add_argument("--profile", type=Path)
            command.add_argument("--checkpoint", default="")
            command.add_argument("--lora", default="")
            command.add_argument("--lora-strength", type=float, default=1.0)
            command.add_argument("--vae", default="")
            command.add_argument("--generation-size", type=int, choices=(512, 768, 1024), default=1024)
            command.add_argument("--steps", type=int, default=28)
            command.add_argument("--cfg", type=float, default=7.0)
            command.add_argument("--submit-only", action="store_true")
            command.add_argument("--wait-seconds", type=float, default=180)
        else:
            command.add_argument("source", type=Path)
    command = sub.add_parser("resume", help="Collect an existing job or reprocess a completed source")
    command.add_argument("project", type=Path)
    command.add_argument("--profile", type=Path)
    command.add_argument("--wait-seconds", type=float, default=180)
    command = sub.add_parser("inspect", help="Open portable project metadata without a generation server")
    command.add_argument("project", type=Path)
    command = sub.add_parser("prompts", help="Preview prompts offline or inspect the actual saved workflow text")
    command.add_argument("--project", type=Path)
    command.add_argument("--prompt")
    prompt_options(command, preview=True)
    return result


async def doctor(profile, checkpoint, lora="", vae=""):
    async with connect(profile) as provider:
        assets = {key: value for key, value in (("lora", lora), ("vae", vae)) if value}
        return await provider.preflight(checkpoint, **assets)


def summary(project):
    return {"project": str(project.root), "state": project.manifest["state"],
            "job_id": project.manifest.get("job_id"), "assets": project.manifest["assets"],
            "quality": project.manifest["quality"], "prompts": saved_prompts(project)}


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            result = asyncio.run(doctor(Profile.load(args.profile), args.checkpoint, args.lora, args.vae))
        elif args.command == "prompts":
            edits = {key: getattr(args, key, None) for key in ("prompt", *sorted(PROMPT_FIELDS))}
            if args.project is not None:
                if any(value is not None for value in edits.values()):
                    raise ValueError("--project cannot be combined with prompt editing options")
                result = saved_prompts(Project.open(args.project))
                if result is None:
                    raise ValueError("project has no saved generation prompts")
            else:
                result = resolve_prompts(Request(**{key: value for key, value in edits.items() if value is not None}))
        elif args.command == "inspect":
            result = summary(Project.open(args.project))
        elif args.command == "resume":
            if not 0 <= args.wait_seconds <= 3600:
                raise ValueError("wait-seconds must be 0..3600")
            result = summary(asyncio.run(resume(
                Project.open(args.project), Profile.load(args.profile), args.wait_seconds,
            )))
        else:
            values = {name: getattr(args, name) for name in (
                "prompt", "size", "colors", "seed", "background", "tolerance", "padding", "method",
            )}
            if args.palette:
                values["palette"] = [c.strip() for c in args.palette.split(",")]
            if args.command == "generate":
                values.update({name: getattr(args, name) for name in (
                    "checkpoint", "generation_size", "steps", "cfg", "lora", "lora_strength", "vae",
                    "prompt_preset", "positive_prompt", "negative_prompt",
                )})
                if not 0 <= args.wait_seconds <= 3600:
                    raise ValueError("wait-seconds must be 0..3600")
                project = asyncio.run(generate(
                    args.output, Request(**values), Profile.load(args.profile), args.submit_only, args.wait_seconds,
                ))
            else:
                project = import_image(args.source, args.output, Request(**values))
            result = summary(project)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("state", "review") == "review" or getattr(args, "submit_only", False) else 3
    except Exception as exc:
        def message(error):
            if isinstance(error, BaseExceptionGroup):
                return "; ".join(message(item) for item in error.exceptions)
            return str(error)
        print(json.dumps({"error": message(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
