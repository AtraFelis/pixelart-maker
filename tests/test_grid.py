import unittest
import numpy as np
from PIL import Image

from pixelart.grid import recover_grid
from pixelart.pixels import convert
from pixelart.request import Request


class GridTests(unittest.TestCase):
    def test_exact_integer_grid_recovery(self):
        rng = np.random.default_rng(15)
        palette = np.array([[25, 30, 50, 255], [200, 30, 40, 255], [20, 180, 60, 255]], dtype=np.uint8)
        native = Image.fromarray(palette[rng.integers(0, 3, size=(32, 32))])
        expanded = native.resize((256, 256), Image.Resampling.NEAREST)
        recovered, metadata = recover_grid(expanded)
        self.assertTrue(metadata["detected"])
        self.assertEqual(metadata["x"]["step"], 8)
        self.assertEqual(metadata["y"]["step"], 8)
        self.assertEqual(recovered.tobytes(), native.tobytes())
        candidates, _, _ = convert(expanded, Request(background="alpha", colors=3, padding=0))
        self.assertEqual(candidates["grid"].tobytes(), native.tobytes())

    def test_flat_input_does_not_invent_grid(self):
        image, metadata = recover_grid(Image.new("RGBA", (256, 256), "red"))
        self.assertIsNone(image)
        self.assertFalse(metadata["detected"])
