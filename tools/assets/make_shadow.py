#!/usr/bin/env python3
"""Draws the soft panel shadow used with 9-slice (Client.Shadow): a black box with RADIUS-rounded corners, dark under
the panel and fading out over PAD px outside, so a rounded panel never uncovers a darker square corner.

usage: make_shadow.py <output png>
The image is 2*(PAD + RADIUS) + 4 px wide. The panel's edge lies PAD px in from the image's edge; the middle 4x4 px is
the stretchable centre (SliceCenter PAD + RADIUS .. PAD + RADIUS + 4).
"""
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

PAD = 32  # shadow reach outside the panel, px
RADIUS = 20  # corner rounding, about the menu cards' own
EDGE = 0.85  # darkness at the panel's edge (1 = full)
SCALE = 4  # drawn larger, then reduced: smooth edges


def main():
    size = (2 * (PAD + RADIUS) + 4) * SCALE
    box = Image.new("L", (size, size), 0)
    ImageDraw.Draw(box).rounded_rectangle([PAD * SCALE, PAD * SCALE, size - PAD * SCALE - 1, size - PAD * SCALE - 1], RADIUS * SCALE, fill=255)
    inside = np.asarray(box) > 127
    t = np.clip(1 - ndimage.distance_transform_edt(~inside) / (PAD * SCALE), 0, 1)
    alpha = t * t * (3 - 2 * t) * EDGE
    small = Image.fromarray((alpha * 255 + 0.5).astype(np.uint8)).resize((size // SCALE, size // SCALE), Image.LANCZOS)
    rgba = np.zeros((size // SCALE, size // SCALE, 4), np.uint8)
    rgba[..., 3] = np.asarray(small)
    Image.fromarray(rgba, "RGBA").save(sys.argv[1], optimize=True)


if __name__ == "__main__":
    main()
