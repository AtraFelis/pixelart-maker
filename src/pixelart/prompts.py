"""Versioned prompt composition and offline access to the submitted text."""
import json


PRESETS = ("common", "item", "character")
PROMPT_FIELDS = {"prompt_preset", "prompt_preset_version", "positive_prompt", "negative_prompt"}
COMMON_NEGATIVE = "photorealistic, 3d render, blurry, watermark, jpeg artifacts"
ITEM_NEGATIVE = (
    "photorealistic, 3d render, gradient background, complex background, text, "
    "letters, watermark, blurry, tiny details, multiple objects, cropped, out of frame, "
    "user interface, HUD, border, frame, screenshot, infographic, panel, scenery, human, person, "
    "body, face, room, architecture, photorealistic, reflection, cast shadow"
)


def validate_options(request):
    if not isinstance(request.prompt_preset, str) or request.prompt_preset not in PRESETS:
        raise ValueError("prompt_preset must be common, item or character")
    if type(request.prompt_preset_version) is not int or request.prompt_preset_version != 1:
        raise ValueError("unsupported prompt preset version")
    if request.positive_prompt is not None and (
        not isinstance(request.positive_prompt, str) or not request.positive_prompt.strip()
    ):
        raise ValueError("positive_prompt must be a nonempty string or null")
    if request.negative_prompt is not None and not isinstance(request.negative_prompt, str):
        raise ValueError("negative_prompt must be a string or null; an empty string disables it")


def resolve_prompts(request):
    validate_options(request)
    subject = request.prompt.strip()
    if request.prompt_preset == "item":
        positive = (
            "masterpiece, best quality, pixel art, flat 2d sprite of " + subject +
            ", (single isolated object:1.3), centered, simple silhouette, bold black outline, "
            "few flat solid colors, minimal details, generous empty margin, "
            "(plain solid white background:1.5), no shadow, no text, no frame"
        )
        negative = ITEM_NEGATIVE
    elif request.prompt_preset == "character":
        positive = (
            "pixel art character sprite, " + subject +
            ", readable character silhouette, clear pose, crisp pixel edges, limited color palette"
        )
        negative = COMMON_NEGATIVE + ", extra limbs, fused limbs, extra fingers"
    else:
        positive = "pixel art, " + subject + ", crisp pixel edges, limited color palette"
        negative = COMMON_NEGATIVE
    return {
        "preset": request.prompt_preset, "preset_version": request.prompt_preset_version,
        "input": {"prompt": request.prompt, "positive_prompt": request.positive_prompt,
                  "negative_prompt": request.negative_prompt},
        "positive": positive if request.positive_prompt is None else request.positive_prompt,
        "negative": negative if request.negative_prompt is None else request.negative_prompt,
    }


def saved_prompts(project):
    """Read actual saved encoder text, never recompose a historical workflow."""
    snapshot = project.manifest.get("prompts")
    workflow = project.manifest.get("assets", {}).get("workflow")
    if not workflow:
        return snapshot
    graph = json.loads(project.asset(workflow).read_text(encoding="utf-8"))
    samplers = [node for node in graph.values() if node.get("class_type") == "KSampler"]
    if len(samplers) != 1:
        raise ValueError("saved workflow must have exactly one KSampler to inspect prompts")
    texts = {}
    for kind in ("positive", "negative"):
        reference = samplers[0]["inputs"][kind]
        encoder = graph[str(reference[0])]
        if encoder.get("class_type") != "CLIPTextEncode" or not isinstance(encoder["inputs"].get("text"), str):
            raise ValueError("saved prompt encoder is not supported")
        texts[kind] = encoder["inputs"]["text"]
    if snapshot is not None:
        if any(snapshot.get(key) != value for key, value in texts.items()):
            raise ValueError("saved prompts differ from workflow text")
        return snapshot
    return {"preset": None, "preset_version": None, "origin": "legacy_workflow",
            "input": {key: project.manifest["request"].get(key) for key in
                      ("prompt", "positive_prompt", "negative_prompt")}, **texts}
