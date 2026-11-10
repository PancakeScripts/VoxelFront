#!/usr/bin/env python3
"""Draws each map's image for the map picker with the game's terrain colours (MapPalette), at most 1024 px per side.

usage: make_map_thumbs.py <map data dir> <output dir>
Reads <map data dir>/out/chunks (World) and <map data dir>/regions/<id>/chunks; writes <output dir>/<id>.png.
"""
import base64
import glob
import os
import sys

import numpy as np
from PIL import Image

MAPS = {"world": ("out", 2000, 1000), "europe": ("regions/europe", 1335, 1124), "asia": ("regions/asia", 1522, 985),
        "africa": ("regions/africa", 1225, 1225), "namerica": ("regions/namerica", 1413, 1061), "samerica": ("regions/samerica", 1020, 1471)}
MAX_SIDE = 1024
FADE = 0.035  # share of the longer side
SEA = (61, 123, 171)  # MapPalette's deepest water


def clamp(v):
    return max(0, min(255, v))


def color_of(tb):
    land, shore, m = tb & 0x80, tb & 0x40, tb & 0x1F
    if land:
        if shore:
            return 204, 203, 158
        if m < 10:
            return 190, clamp(220 - 2 * m), 138
        if m < 20:
            k = m - 10
            return clamp(220 + 2 * k), clamp(203 + 2 * k), clamp(158 + 2 * k)
        k = m // 2
        return clamp(230 + k), clamp(230 + k), clamp(230 + k)
    if shore:
        return 126, 170, 203
    d = min(m, 10)
    return clamp(71 - d), clamp(133 - d), clamp(181 - d)


PALETTE = np.array([color_of(i) for i in range(256)], np.uint8)


def decode(folder, size):
    text = "".join(open(p, encoding="ascii").read() for p in sorted(glob.glob(os.path.join(folder, "chunks", "*.txt"))))
    data = base64.b64decode(text)
    out = np.zeros(size, np.uint8)
    pos = i = 0
    while i < len(data):
        value = data[i]
        i += 1
        n = shift = 0
        while True:
            b = data[i]
            i += 1
            n |= (b & 0x7F) << shift
            shift += 7
            if b < 0x80:
                break
        out[pos:pos + n + 1] = value
        pos += n + 1
    assert pos == size
    return out


def fade_edges(img):
    """Blends the outer FADE of the image into the open-sea colour, so land cut by the edge melts into the card's sea."""
    a = np.asarray(img, np.float32)
    h, w = a.shape[:2]
    n = max(4, round(max(w, h) * FADE))
    ramp = lambda size: np.clip(np.minimum(np.arange(size), np.arange(size)[::-1]) / n, 0, 1)
    t = np.minimum.outer(ramp(h), ramp(w))
    t = (t * t * (3 - 2 * t))[..., None]
    return Image.fromarray((a * t + np.array(SEA, np.float32) * (1 - t) + 0.5).astype(np.uint8))


def main():
    src, dst = sys.argv[1], sys.argv[2]
    os.makedirs(dst, exist_ok=True)
    for name, (folder, w, h) in MAPS.items():
        grid = decode(os.path.join(src, folder), w * h).reshape(h, w)
        img = Image.fromarray(PALETTE[grid])
        k = MAX_SIDE / max(w, h)
        if k < 1:
            img = img.resize((round(w * k), round(h * k)), Image.LANCZOS)
        img = fade_edges(img)
        img.save(os.path.join(dst, name + ".png"), optimize=True)
        print(name, img.size, os.path.getsize(os.path.join(dst, name + ".png")))


if __name__ == "__main__":
    main()
