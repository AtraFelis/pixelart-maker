"""Compare the same six requests with baseline, SDXL base and SDXL Pixel Art XL."""
import argparse
import asyncio
from pathlib import Path

from pixelart.comparison import load_definition, run_comparison
from pixelart.config import Profile

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/model-comparison"))
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--samples", type=Path, default=Path(__file__).with_name("samples.json"))
    parser.add_argument("--variants", type=Path, default=Path(__file__).with_name("model_variants.json"))
    parser.add_argument("--wait-seconds", type=float, default=600)
    args = parser.parse_args()
    if not 0 <= args.wait_seconds <= 3600:
        parser.error("wait-seconds must be 0..3600")
    profile = Profile.load(args.profile)
    definition = load_definition(args.samples, args.variants, profile)
    asyncio.run(run_comparison(args.output, definition, profile, args.wait_seconds))
