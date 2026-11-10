"""Crate item images for Voxel Front, following RoWorld's tools/assets/make_flags.py and
make_skin_previews.py (same SVG sources, sizes and preview colours).
Usage: python make_crate_images.py <rw_flags_dir> <Cosmetics.luau> <out_dir>
(Reads the downloaded files only as data; no downloaded code is run.)
"""
import io
import json
import os
import re
import sys

import resvg_py
from PIL import Image

FLAGS_DIR, COSMETICS, OUT = sys.argv[1:4]


class ps:
    """The parts of RoWorld's preview_skins.py used here (crate skins only)."""
    ALPHA, ALPHA2 = 150, 190

    @staticmethod
    def skins():
        s = open(COSMETICS, encoding="utf-8").read()
        out = []
        pat = (r'\{\s*id = "([a-z_]+)",\s*name = "([^"]+)",\s*rarity = "(\w+)",\s*scale = (\d),'
               r'\s*(tone|accent) = ([-0-9.x A-F]+),\s*mask = \{(.*?)\},?\s*\}')
        for m in re.finditer(pat, s, re.S):
            rows = re.findall(r'"([#.]+)"', m.group(7))
            v = m.group(6).strip().rstrip(",")
            out.append(dict(id=m.group(1), name=m.group(2), rarity=m.group(3), scale=int(m.group(4)),
                            tone=float(v) if m.group(5) == "tone" else None,
                            accent=int(v, 16) if m.group(5) == "accent" else None, rows=rows))
        return out

    @staticmethod
    def tile_color(sk, row_s, mx, own, s2):
        k = 1 if (mx < len(row_s) and row_s[mx] == "#") else 0
        return (s2, ps.ALPHA2) if k else (own, ps.ALPHA)

    @staticmethod
    def second(sk, r, g, b):
        if sk["accent"] is not None:
            a = sk["accent"]
            return ((a >> 16) & 255) / 255, ((a >> 8) & 255) / 255, (a & 255) / 255
        t = sk["tone"]
        if t >= 0:
            return r + (1 - r) * t, g + (1 - g) * t, b + (1 - b) * t
        return r * (1 + t), g * (1 + t), b * (1 + t)

# ---- flags (RoWorld make_flags.py) ----
FLAG_W, FLAG_H = 116, 76
CELL_W, CELL_H = 120, 80
COLS, ROWS = 8, 8
PER = COLS * ROWS


def render_flag(path):
    svg = open(path, encoding="utf-8").read()
    png = bytes(resvg_py.svg_to_bytes(svg_string=svg, width=FLAG_W * 3))
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    box = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if box:
        im = im.crop(box)
    im.thumbnail((FLAG_W, FLAG_H), Image.LANCZOS)
    return im


names = json.load(open(os.path.join(FLAGS_DIR, "names.json"), encoding="utf-8"))
have = [c for c in names if os.path.exists(os.path.join(FLAGS_DIR, c + ".svg"))]
codes = sorted(c for c in have if len(c) == 2) + sorted(c for c in have if len(c) != 2)
fdir = os.path.join(OUT, "flags")
os.makedirs(fdir, exist_ok=True)
rects = []
for a in range((len(codes) + PER - 1) // PER):
    sheet = Image.new("RGBA", (COLS * CELL_W, ROWS * CELL_H), (0, 0, 0, 0))
    chunk = codes[a * PER:(a + 1) * PER]
    for k, code in enumerate(chunk):
        im = render_flag(os.path.join(FLAGS_DIR, code + ".svg"))
        cx, cy = (k % COLS) * CELL_W, (k // COLS) * CELL_H
        x, y = cx + (CELL_W - im.width) // 2, cy + (CELL_H - im.height) // 2
        sheet.alpha_composite(im, (x, y))
        rects.append((code, names[code], a + 1, x, y, im.width, im.height))
    used = (len(chunk) + COLS - 1) // COLS
    sheet = sheet.crop((0, 0, COLS * CELL_W, used * CELL_H))
    sheet.save(os.path.join(fdir, f"flags_{a + 1}.png"), optimize=True)

L = ["-- Crate country flags (Wikimedia Commons, public domain; same set as RoWorld's Assets/Flags).",
     "-- Upload flags_1..N.png and put their ids in `atlases` (in order). Each flag's rect in its atlas:",
     "-- ImageRectOffset = x, y; ImageRectSize = w, h.",
     "return {", "\tatlases = {"]
for a in range(max(r[2] for r in rects)):
    L.append(f'\t\t"", -- flags_{a + 1}.png')
L += ["\t},", "\tflags = {"]
for code, name, a, x, y, w, h in rects:
    nm = name.replace('"', '\\"')
    L.append(f'\t\t{{ code = "{code}", name = "{nm}", atlas = {a}, x = {x}, y = {y}, w = {w}, h = {h} }},')
L += ["\t},", "}"]
open(os.path.join(fdir, "Flags.luau"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print(f"{len(rects)} flags in {max(r[2] for r in rects)} atlases")

# ---- skin previews (RoWorld make_skin_previews.py), crate skins only ----
PREVIEW_COLOR = (64, 132, 230)
TILES, SCALE, GAP, SCOLS = 24, 4, 4, 7
TERRAIN = (221, 205, 160)


def render_skin(s):
    n = TILES
    r, g, b = (c / 255 for c in PREVIEW_COLOR)
    sr, sg, sb = ps.second(s, r, g, b)
    w = max(len(row) for row in s["rows"])
    h = len(s["rows"])
    im = Image.new("RGBA", (n, n))
    px = im.load()
    for y in range(n):
        for x in range(n):
            if x in (0, n - 1) or y in (0, n - 1):
                cr, cg, cb, al = r * 0.875, g * 0.875, b * 0.875, 1.0
            else:
                row = s["rows"][(y >> s["scale"]) % h]
                mx = (x >> s["scale"]) % w
                (cr, cg, cb), al = ps.tile_color(s, row, mx, (r, g, b), (sr, sg, sb))
                al /= 255
            t = [v / 255 for v in TERRAIN]
            px[x, y] = tuple(int((t[i] * (1 - al) + c * al) * 255 + 0.5) for i, c in enumerate((cr, cg, cb))) + (255,)
    return im.resize((TILES * SCALE, TILES * SCALE), Image.NEAREST)


skins = [s for s in ps.skins() if s["rarity"] in ("common", "rare", "epic", "legendary")]
sdir = os.path.join(OUT, "skins")
os.makedirs(sdir, exist_ok=True)
cell = TILES * SCALE
rows = (len(skins) + SCOLS - 1) // SCOLS
sheet = Image.new("RGBA", (SCOLS * (cell + GAP), rows * (cell + GAP)), (0, 0, 0, 0))
L = ["-- Crate territory skin previews (patterns as RoWorld's Data/Cosmetics). Upload skin_previews.png,",
     "-- put its id in `image`; each skin's rect: ImageRectOffset = x, y; ImageRectSize = w, h.",
     "-- Draw with ResampleMode Pixelated.", "return {", '\timage = "",', "\tcells = {"]
for i, s in enumerate(skins):
    x, y = (i % SCOLS) * (cell + GAP), (i // SCOLS) * (cell + GAP)
    im = render_skin(s)
    sheet.alpha_composite(im, (x, y))
    L.append(f"\t\t{s['id']} = {{ {x}, {y}, {cell}, {cell} }}, -- {s['name']} ({s['rarity']})")
L += ["\t},", "}"]
sheet.save(os.path.join(sdir, "skin_previews.png"), optimize=True)
open(os.path.join(sdir, "SkinPreviews.luau"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print(f"{len(skins)} skins")
