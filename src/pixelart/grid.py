"""Conservative periodic-edge grid candidate; no claim of universal grid recovery."""
import numpy as np
from PIL import Image


def axis_grid(pixels, axis):
    difference = np.abs(np.diff(pixels.astype(np.int16), axis=axis))
    # Edges in RGB or alpha; transparent padding must not dominate by hidden RGB.
    energy = np.max(difference, axis=2).mean(axis=1 if axis == 0 else 0)
    if len(energy) < 24 or energy.max() < 1:
        return None
    padded = np.pad(energy, (1, 1))
    peaks = np.flatnonzero(
        (energy >= energy.max() * 0.18)
        & (energy >= padded[:-2]) & (energy > padded[2:])
    ) + 1
    if len(peaks) < 6:
        return None
    weights = energy[peaks - 1]
    candidates = []
    for step in range(2, min(64, len(energy) // 6) + 1):
        votes = np.bincount(peaks % step, weights=weights, minlength=step)
        phase = int(votes.argmax())
        concentration = float(votes[phase] / weights.sum())
        if concentration >= 0.85 and np.count_nonzero(peaks % step == phase) >= 6:
            candidates.append((step, phase, concentration))
    if not candidates:
        return None
    # Divisors get equal votes on exact integer grids; prefer the coarsest fit.
    step, phase, concentration = max(candidates)
    return {"step": step, "phase": phase, "edge_concentration": round(concentration, 4)}


def recover_grid(image: Image.Image):
    pixels = np.array(image.convert("RGBA"))
    x = axis_grid(pixels, 1)
    y = axis_grid(pixels, 0)
    if not x or not y:
        return None, {"detected": False, "reason": "insufficient periodic edge evidence"}
    def centers(length, grid):
        values = np.arange(grid["phase"] + grid["step"] / 2 - grid["step"], length, grid["step"])
        return np.clip(values[values >= 0].astype(int), 0, length - 1)
    xs, ys = centers(image.width, x), centers(image.height, y)
    recovered = Image.fromarray(pixels[np.ix_(ys, xs)])
    return recovered, {
        "detected": True, "x": x, "y": y, "recovered_size": list(recovered.size),
        "warning": "Experimental periodic-grid candidate; compare against the original.",
    }
