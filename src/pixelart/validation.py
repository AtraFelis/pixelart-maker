import numpy as np
from PIL import Image
from pixelart.request import Request


def validate(image: Image.Image, request: Request):
    rgba = np.asarray(image.convert("RGBA"))
    visible = rgba[rgba[:, :, 3] > 0, :3]
    colors = np.unique(visible, axis=0)
    allowed = {tuple(bytes.fromhex(c[1:])) for c in request.palette}
    checks = {
        "size": image.size == request.canvas_dimensions,
        "color_limit": len(colors) <= request.colors,
        "binary_alpha": set(np.unique(rgba[:, :, 3])).issubset({0, 255}),
        "fixed_palette": not allowed or all(tuple(c) in allowed for c in colors),
    }
    return {
        "passed": all(checks.values()), "checks": checks,
        "size": list(image.size), "visible_colors": len(colors),
        "opaque_pixels": int(np.count_nonzero(rgba[:, :, 3])),
        "palette": ["#" + bytes(c).hex().upper() for c in colors],
        "artistic_quality": "requires_visual_review",
    }


def validate_export(image: Image.Image, canvas: Image.Image, request: Request):
    expected = canvas.resize(request.export_dimensions, Image.Resampling.NEAREST)
    checks = {"size": image.size == request.export_dimensions,
              "canvas_size": canvas.size == request.canvas_dimensions,
              "pixel_replication": image.mode == "RGBA" and np.array_equal(np.asarray(image), np.asarray(expected))}
    return {"passed": all(checks.values()), "checks": checks, "size": list(image.size),
            "scale": request.export_scale, "artistic_quality": "requires_visual_review"}
