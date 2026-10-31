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
    if not all(name in help_text for name in ("generate", "convert", "resume", "inspect")):
        raise RuntimeError("installed CLI help is missing expected commands")
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
    print("Packaged CLI smoke passed: help, convert, inspect; Unicode and space paths; no ComfyUI")


if __name__ == "__main__":
    main()
