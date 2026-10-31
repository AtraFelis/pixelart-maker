from dataclasses import asdict, dataclass, field
import math
import re


@dataclass
class Request:
    prompt: str = "red potion bottle, cork stopper, game inventory icon"
    size: int = 32
    colors: int = 16
    seed: int = 42
    generation_size: int = 1024
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

    def __post_init__(self):
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ValueError("prompt must not be empty")
        if self.size not in (32, 64):
            raise ValueError("size must be 32 or 64")
        if not 1 <= self.colors <= 256:
            raise ValueError("colors must be between 1 and 256")
        if not 0 <= self.seed < 2**64:
            raise ValueError("seed must be an unsigned 64-bit integer")
        if self.generation_size not in (512, 768, 1024):
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
        if not 0 <= self.tolerance <= 255 or not 0 <= self.padding < self.size // 2:
            raise ValueError("invalid tolerance or padding")
        if self.method not in ("nearest", "majority", "grid"):
            raise ValueError("method must be nearest, majority or grid")
        for color in self.palette:
            if not isinstance(color, str) or re.fullmatch(r"#[0-9a-fA-F]{6}", color) is None:
                raise ValueError("palette entries must be #RRGGBB")
        if self.palette and len(self.palette) > self.colors:
            raise ValueError("fixed palette exceeds colors")

    def to_dict(self):
        return asdict(self)
