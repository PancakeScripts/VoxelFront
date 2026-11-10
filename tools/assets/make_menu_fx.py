#!/usr/bin/env python3
"""Draws the main menu's vignette (dark edges, clear middle) and the warm glow behind the title, as white-on-alpha
images tinted in game (ImageColor3).

usage: make_menu_fx.py <output dir>   -> vignette.png, title_glow.png
"""
import os
import sys

import numpy as np
from PIL import Image


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def save(alpha, path):
    rgba = np.zeros(alpha.shape + (4,), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = np.clip(alpha * 255 + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").save(path, optimize=True)


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    # vignette: elliptical, stretched to the screen; clear inside 45% of the half-diagonal, 85% dark at the corners
    n = 256
    y, x = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    d = np.sqrt(x * x + y * y) / np.sqrt(2)
    save(smoothstep(0.45, 1.0, d) * 0.85, os.path.join(out, "vignette.png"))
    # title glow: soft ellipse, strongest in the middle
    w, h = 512, 256
    y, x = np.mgrid[0:h, 0:w]
    dx, dy = (x - (w - 1) / 2) / (w / 2), (y - (h - 1) / 2) / (h / 2)
    save(np.exp(-(dx * dx + dy * dy) * 3.2) * (1 - smoothstep(0.85, 1.0, np.sqrt(dx * dx + dy * dy))), os.path.join(out, "title_glow.png"))


if __name__ == "__main__":
    main()
