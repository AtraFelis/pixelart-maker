from pixelart.request import Request

from pixelart.prompts import resolve_prompts


def build_workflow(request: Request, project_id: str):
    prompts = resolve_prompts(request)
    graph = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": request.checkpoint}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompts["positive"], "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": prompts["negative"], "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {
            "width": request.generation_dimensions[0], "height": request.generation_dimensions[1], "batch_size": 1,
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
    if request.lora:
        graph["8"] = {"class_type": "LoraLoader", "inputs": {
            "model": ["1", 0], "clip": ["1", 1], "lora_name": request.lora,
            "strength_model": request.lora_strength, "strength_clip": request.lora_strength,
        }}
        graph["5"]["inputs"]["model"] = ["8", 0]
        graph["2"]["inputs"]["clip"] = ["8", 1]
        graph["3"]["inputs"]["clip"] = ["8", 1]
    if request.vae:
        graph["9"] = {"class_type": "VAELoader", "inputs": {"vae_name": request.vae}}
        graph["6"]["inputs"]["vae"] = ["9", 0]
    return graph
