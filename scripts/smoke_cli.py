"""Exercise the installed CLI with a synthetic image, without a generation server."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw
import pixelart


def main():
    executable = shutil.which("pixelart")
    if not executable:
        raise RuntimeError("pixelart entry point is missing; run uv sync --locked --no-editable")
    prefix = Path(sys.prefix).resolve()
    if not Path(executable).resolve().is_relative_to(prefix):
        raise RuntimeError("pixelart entry point must belong to the selected environment")
    if not Path(pixelart.__file__).resolve().is_relative_to(prefix):
        raise RuntimeError("smoke check requires a packaged install; run uv sync --locked --no-editable")
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

    def invoke(*arguments):
        result = subprocess.run([executable, *map(str, arguments)], env=env,
                                capture_output=True, text=True, encoding="utf-8", timeout=60)
        if result.returncode:
            raise RuntimeError(f"CLI failed ({result.returncode}): {result.stderr}")
        return result.stdout

    help_text = invoke("--help")
    if not all(name in help_text for name in ("generate", "convert", "resume", "inspect", "prompts")):
        raise RuntimeError("installed CLI help is missing expected commands")
    prompts = json.loads(invoke("prompts", "--prompt", "금발 여성 기사", "--prompt-preset", "character",
                                "--negative-prompt", ""))
    if prompts["preset"] != "character" or prompts["negative"] != "" or "금발 여성 기사" not in prompts["positive"]:
        raise RuntimeError("offline prompt preview lost the selected preset, Unicode input or empty override")
    with TemporaryDirectory(prefix="pixelart-ci-") as temporary:
        root = Path(temporary) / "한글 경로 with spaces"
        root.mkdir()
        source = root / "합성 입력.png"
        image = Image.new("RGBA", (64, 64))
        ImageDraw.Draw(image).rectangle((18, 8, 45, 55), fill=(220, 30, 50, 255))
        image.save(source)
        output = root / "변환 프로젝트"
        converted = json.loads(invoke("convert", source, "--size", "32", "--colors", "4",
                                      "--background", "alpha", "--output", output))
        inspected = json.loads(invoke("inspect", output))
        if converted["state"] != "review" or inspected != converted:
            raise RuntimeError("conversion and server-free reopen did not preserve project metadata")
        if not (output / converted["assets"]["final"]).is_file():
            raise RuntimeError("conversion did not save the final artifact")
        wide_output = root / "큰 직사각형 출력"
        wide = json.loads(invoke("convert", source, "--width", "128", "--height", "96",
                                 "--export-scale", "3", "--colors", "4", "--background", "alpha",
                                 "--output", wide_output))
        if wide["dimensions"]["canvas"] != [128, 96] or wide["dimensions"]["export"] != [384, 288]:
            raise RuntimeError("CLI confused pixel canvas dimensions with export dimensions")
        with Image.open(wide_output / "final.png") as canvas, Image.open(wide_output / "export.png") as export:
            if export.tobytes() != canvas.resize((384, 288), Image.Resampling.NEAREST).tobytes():
                raise RuntimeError("integer export changed RGBA pixel blocks")
        with Image.open(wide_output / "preview.png") as preview:
            if preview.size != (1024, 768):
                raise RuntimeError("large-canvas preview did not use a bounded integer scale")
        if json.loads(invoke("inspect", wide_output)) != wide:
            raise RuntimeError("rectangular dimensions did not survive server-free reopen")
    print("Packaged CLI smoke passed: help, prompts, square/rectangular convert, integer export, inspect; Unicode and space paths; no ComfyUI")


if __name__ == "__main__":
    main()
