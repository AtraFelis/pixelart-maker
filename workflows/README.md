# Prototype workflow

The API-format graph is built by src/pixelart/workflow.py and saved in each run as workflow.json.

It uses only CheckpointLoaderSimple, CLIPTextEncode, EmptyLatentImage, KSampler, VAEDecode and SaveImage. No custom node, LoRA or paid API is installed or invoked.

A matching checkpoint must already be present on the selected target. The model name is configurable; generated output is not guaranteed to have a recoverable native grid.

The default is a 1024-pixel square, 28 Euler ancestral steps, normal schedule and CFG 7. Change these only as a documented experiment. Final 32/64 size is independent of generation size.
