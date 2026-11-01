from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

from pixelart.request import Request
from pixelart.grid import recover_grid


def prepare(image: Image.Image, request: Request):
    pixels = np.array(image.convert("RGBA"), dtype=np.uint8)
    pixels[:, :, 3] = np.where(pixels[:, :, 3] >= 128, 255, 0)
    notes = []
    if request.background == "opaque":
        # Composite genuine alpha on white; do not expose hidden RGB.
        base = Image.new("RGBA", image.size, (255, 255, 255, 255))
        pixels = np.array(Image.alpha_composite(base, image.convert("RGBA")))
    elif request.background == "corner" and np.all(pixels[:, :, 3] == 255):
        corners = pixels[[0, 0, -1, -1], [0, -1, 0, -1], :3].astype(np.int32)
        key = np.median(corners, axis=0)
        if np.max(np.abs(corners - key)) > request.tolerance:
            notes.append("Corners disagree: automatic background removal skipped; use alpha or another source.")
        else:
            eligible = np.max(np.abs(pixels[:, :, :3].astype(np.int32) - key), axis=2) <= request.tolerance
            height, width = eligible.shape
            visited = np.zeros((height, width), dtype=bool)
            queue = deque()
            def visit(y, x):
                if eligible[y, x] and not visited[y, x]:
                    visited[y, x] = True
                    queue.append((y, x))
            for x in range(width):
                visit(0, x)
                visit(height - 1, x)
            for y in range(height):
                visit(y, 0)
                visit(y, width - 1)
            while queue:
                y, x = queue.popleft()
                for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= ny < height and 0 <= nx < width:
                        visit(ny, nx)
            pixels[visited, 3] = 0
            notes.append(f"Removed {int(visited.sum())} border-connected background pixels; inspect light edges.")
    pixels[pixels[:, :, 3] == 0] = 0
    return Image.fromarray(pixels), notes


def palette_for(image: Image.Image, request: Request):
    if request.palette:
        return np.array([tuple(bytes.fromhex(c[1:])) for c in request.palette], dtype=np.uint8)
    pixels = np.array(image)
    visible = pixels[pixels[:, :, 3] > 0, :3]
    if len(visible) == 0:
        return np.array([[0, 0, 0]], dtype=np.uint8)
    # Keep generation-sized images from making quantization unnecessarily expensive.
    samples = visible[::max(1, len(visible) // 65536)]
    strip = Image.fromarray(samples.reshape(1, -1, 3))
    indexed = strip.quantize(colors=request.colors, method=Image.Quantize.MEDIANCUT,
                             dither=Image.Dither.NONE)
    table = np.asarray(indexed.getpalette(), dtype=np.uint8).reshape(-1, 3)
    return table[np.unique(np.array(indexed))]


def map_palette(image: Image.Image, palette: np.ndarray):
    pixels = np.array(image)
    rgb = pixels[:, :, :3].reshape(-1, 3)
    indices = np.flatnonzero(pixels[:, :, 3].ravel())
    for start in range(0, len(indices), 8192):
        selected = indices[start:start + 8192]
        distances = rgb[selected, None, :].astype(np.int32) - palette[None, :, :].astype(np.int32)
        best = np.argmin(np.sum(distances * distances, axis=2), axis=1)
        rgb[selected] = palette[best]
    return Image.fromarray(pixels)


def majority_resize(image: Image.Image, size: tuple[int, int]):
    pixels = np.array(image)
    height, width = pixels.shape[:2]
    out_w, out_h = size
    if out_w >= width and out_h >= height:
        # Each old voting cell contains exactly one source pixel when enlarging.
        # Keep the original floor-based coordinates (not Pillow's center-based nearest).
        ys = np.arange(out_h) * height // out_h
        xs = np.arange(out_w) * width // out_w
        output = pixels[np.ix_(ys, xs)].copy()
        output[:, :, 3] = np.where(output[:, :, 3] > 0, 255, 0)
        output[output[:, :, 3] == 0] = 0
        return Image.fromarray(output)
    output = np.zeros((out_h, out_w, 4), dtype=np.uint8)
    for y in range(out_h):
        top, bottom = y * height // out_h, max(y * height // out_h + 1, (y + 1) * height // out_h)
        for x in range(out_w):
            left, right = x * width // out_w, max(x * width // out_w + 1, (x + 1) * width // out_w)
            cell = pixels[top:bottom, left:right].reshape(-1, 4)
            visible = cell[cell[:, 3] > 0]
            if len(visible) and len(visible) / len(cell) >= 0.2:
                colors, counts = np.unique(visible[:, :3], axis=0, return_counts=True)
                output[y, x] = (*colors[np.argmax(counts)], 255)
    return Image.fromarray(output)


def convert(image: Image.Image, request: Request):
    prepared, notes = prepare(image, request)
    canvas_width, canvas_height = request.canvas_dimensions
    palette = palette_for(prepared, request)
    bounds = prepared.getchannel("A").getbbox()
    if bounds is None:
        if request.method == "grid":
            raise ValueError("no periodic grid detected in empty foreground; choose nearest or majority")
        notes.append("Empty foreground: technical validity does not imply usable artwork.")
        blank = Image.new("RGBA", (canvas_width, canvas_height))
        return {"nearest": blank.copy(), "majority": blank.copy()}, palette, notes
    cropped = map_palette(prepared.crop(bounds), palette)
    limit_width, limit_height = canvas_width - 2 * request.padding, canvas_height - 2 * request.padding
    ratio = min(limit_width / cropped.width, limit_height / cropped.height)
    size = (max(1, round(cropped.width * ratio)), max(1, round(cropped.height * ratio)))
    if ratio > 1:
        notes.append("The fitted canvas enlarges the source; this does not create new image detail.")
    candidates = {}
    for name, scaled in (
        ("nearest", cropped.resize(size, Image.Resampling.NEAREST)),
        ("majority", majority_resize(cropped, size)),
    ):
        background = (255, 255, 255, 255) if request.background == "opaque" else (0, 0, 0, 0)
        canvas = Image.new("RGBA", (canvas_width, canvas_height), background)
        canvas.paste(scaled, ((canvas_width - size[0]) // 2, (canvas_height - size[1]) // 2))
        # In opaque mode the padding must also obey the chosen palette.
        canvas = map_palette(canvas, palette)
        candidates[name] = canvas
    recovered, grid = recover_grid(prepared)
    if recovered is not None and recovered.getchannel("A").getbbox():
        grid_crop = map_palette(recovered.crop(recovered.getchannel("A").getbbox()), palette)
        grid_ratio = min(limit_width / grid_crop.width, limit_height / grid_crop.height)
        grid_size = (max(1, round(grid_crop.width * grid_ratio)), max(1, round(grid_crop.height * grid_ratio)))
        grid_canvas = Image.new("RGBA", (canvas_width, canvas_height), background)
        grid_canvas.paste(grid_crop.resize(grid_size, Image.Resampling.NEAREST),
                          ((canvas_width - grid_size[0]) // 2, (canvas_height - grid_size[1]) // 2))
        candidates["grid"] = map_palette(grid_canvas, palette)
    notes.append({"grid_recovery": grid})
    if request.method not in candidates:
        raise ValueError("no periodic grid detected; choose nearest or majority")
    return candidates, palette, notes


def save_png(image: Image.Image, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    with Image.open(path) as reopened:
        if reopened.convert("RGBA").tobytes() != image.convert("RGBA").tobytes():
            raise ValueError("PNG round-trip changed pixels")
