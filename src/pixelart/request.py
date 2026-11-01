from dataclasses import asdict, dataclass, field
import math
import re

from pixelart.prompts import PROMPT_FIELDS, validate_options


MAX_CANVAS_EDGE = 2048
MAX_EXPORT_EDGE = 8192
MAX_EXPORT_PIXELS = 16_777_216
MAX_GENERATION_PIXELS = 1_048_576


def integer_in(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


@dataclass
class Request:
    prompt: str = "red potion bottle, cork stopper, game inventory icon"
    size: int | None = 32
    colors: int = 16
    seed: int = 42
    generation_size: int | None = 1024
    steps: int = 28
    cfg: float = 7.0
    checkpoint: str = ""
    lora: str = ""
    lora_strength: float = 1.0
    vae: str = ""
    background: str = "corner"
    tolerance: int = 36
    padding: int = 2
    method: str = "majority"
    palette: list[str] = field(default_factory=list)
    prompt_preset: str = "common"
    prompt_preset_version: int = 1
    positive_prompt: str | None = None
    negative_prompt: str | None = None
    width: int | None = None
    height: int | None = None
    export_scale: int = 1
    generation_width: int | None = None
    generation_height: int | None = None

    def __post_init__(self):
        validate_options(self)
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ValueError("prompt must not be empty")
        if (self.width is None) != (self.height is None):
            raise ValueError("width and height must be supplied together")
        if self.width is not None:
            if self.size is not None and (type(self.size) is not int or self.size != 32):
                raise ValueError("size cannot be combined with width and height")
            if not all(integer_in(value, 32, MAX_CANVAS_EDGE) for value in (self.width, self.height)):
                raise ValueError("canvas width and height must be integers in 32..2048")
            self.size = None
        elif not integer_in(self.size, 32, MAX_CANVAS_EDGE):
            raise ValueError("size must be an integer in 32..2048")
        if not integer_in(self.export_scale, 1, 16):
            raise ValueError("export_scale must be an integer in 1..16")
        export_width, export_height = self.export_dimensions
        if max(export_width, export_height) > MAX_EXPORT_EDGE or export_width * export_height > MAX_EXPORT_PIXELS:
            raise ValueError("export exceeds 8192 per edge or 16777216 total pixels")
        if not 1 <= self.colors <= 256:
            raise ValueError("colors must be between 1 and 256")
        if not 0 <= self.seed < 2**64:
            raise ValueError("seed must be an unsigned 64-bit integer")
        if (self.generation_width is None) != (self.generation_height is None):
            raise ValueError("generation_width and generation_height must be supplied together")
        if self.generation_width is not None:
            if self.generation_size is not None and (
                type(self.generation_size) is not int or self.generation_size != 1024
            ):
                raise ValueError("generation_size cannot be combined with explicit generation dimensions")
            dimensions = (self.generation_width, self.generation_height)
            if not all(integer_in(value, 256, 2048) and value % 64 == 0 for value in dimensions):
                raise ValueError("generation dimensions must be multiples of 64 in 256..2048")
            if self.generation_width * self.generation_height > MAX_GENERATION_PIXELS:
                raise ValueError("generation exceeds 1048576 total pixels; use a smaller source canvas")
            self.generation_size = None
        elif type(self.generation_size) is not int or self.generation_size not in (512, 768, 1024):
            raise ValueError("generation_size must be 512, 768 or 1024")
        if not 1 <= self.steps <= 100 or not math.isfinite(self.cfg) or not 0 <= self.cfg <= 20:
            raise ValueError("steps must be 1..100 and cfg must be finite and 0..20")
        if not math.isfinite(self.lora_strength) or not 0 <= self.lora_strength <= 2:
            raise ValueError("lora_strength must be finite and 0..2")
        if not self.lora and self.lora_strength != 1.0:
            raise ValueError("lora_strength requires a LoRA filename")
        for name in (self.lora, self.vae):
            if not isinstance(name, str):
                raise ValueError("LoRA and VAE names must be strings")
            normalized = name.replace(chr(92), "/")
            if normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
                raise ValueError("LoRA and VAE must be target-relative model names")
        if self.background not in ("corner", "alpha", "opaque"):
            raise ValueError("background must be corner, alpha or opaque")
        if not 0 <= self.tolerance <= 255 or not integer_in(self.padding, 0, min(self.canvas_dimensions) // 2 - 1):
            raise ValueError("invalid tolerance or padding")
        if self.method not in ("nearest", "majority", "grid"):
            raise ValueError("method must be nearest, majority or grid")
        for color in self.palette:
            if not isinstance(color, str) or re.fullmatch(r"#[0-9a-fA-F]{6}", color) is None:
                raise ValueError("palette entries must be #RRGGBB")
        if self.palette and len(self.palette) > self.colors:
            raise ValueError("fixed palette exceeds colors")

    @property
    def canvas_dimensions(self):
        return (self.width, self.height) if self.width is not None else (self.size, self.size)

    @property
    def generation_dimensions(self):
        return ((self.generation_width, self.generation_height) if self.generation_width is not None
                else (self.generation_size, self.generation_size))

    @property
    def export_dimensions(self):
        return tuple(value * self.export_scale for value in self.canvas_dimensions)

    @property
    def preview_scale(self):
        return max(1, min(16, 1024 // max(self.canvas_dimensions)))

    def dimensions(self):
        return {"canvas": list(self.canvas_dimensions), "export": list(self.export_dimensions),
                "export_scale": self.export_scale,
                "preview": [value * self.preview_scale for value in self.canvas_dimensions],
                "preview_scale": self.preview_scale}

    @classmethod
    def from_dict(cls, values):
        values = dict(values)
        if not PROMPT_FIELDS.intersection(values):
            values["prompt_preset"] = "item"
        return cls(**values)

    def to_dict(self):
        return asdict(self)
