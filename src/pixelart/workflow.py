from pixelart.request import Request


NEGATIVE = (
    "photorealistic, 3d render, gradient background, complex background, text, "
    "letters, watermark, blurry, tiny details, multiple objects, cropped, out of frame, "
    "user interface, HUD, border, frame, screenshot, infographic, panel, scenery, human, person, "
    "body, face, room, architecture, photorealistic, reflection, cast shadow"
)


def build_workflow(request: Request, project_id: str):
    prompt = (
        "masterpiece, best quality, pixel art, flat 2d sprite of " + request.prompt.strip() +
        ", (single isolated object:1.3), centered, simple silhouette, bold black outline, "
        "few flat solid colors, minimal details, generous empty margin, "
        "(plain solid white background:1.5), no shadow, no text, no frame"
    )
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": request.checkpoint}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {
            "width": request.generation_size, "height": request.generation_size, "batch_size": 1,
        }},
        "5": {"class_type": "KSampler", "inputs": {
            "seed": request.seed, "steps": request.steps, "cfg": request.cfg,
            "sampler_name": "euler_ancestral", "scheduler": "normal", "denoise": 1.0,
            "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
        }},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {
            "filename_prefix": "pixelart/" + project_id, "images": ["6", 0],
        }},
    }
