#!/usr/bin/env python3
"""Builds Frontline's World map (2000x1000) from public-domain data: Natural Earth (land, lakes) and
NOAA ETOPO1 (elevation). Adapted from RoWorld's tools/maps/make_maps.py (AGPL-3.0, (c) 2026 Snick Co.).

usage: make_world_map.py <source dir> <output dir>
Reads ne_10m_land.geojson, ne_10m_lakes.geojson and etopo.nc from <source dir>; writes chunks/001.txt...
(base64 of MapData's RLE, the StringValues of ReplicatedStorage.Shared.MapWorld), nations.txt and
preview.png to <output dir>.

Tile byte: bit 7 land, bit 6 shoreline, bit 5 ocean, bits 0-4 height (land) / distance from shore (water).
"""
import base64
import collections
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.io import netcdf_file

W, H = 2000, 1000
SS = 3  # sample points per tile side
PPD = W / 360.0
LON0 = -180.0 + 65 / PPD  # left edge in the Bering Strait, as the old map
LAT_TOP = 90.0 - 10 / PPD
LAKE_RANK = 3
MIN_ISLAND = 21
MIN_LAKE = 21
CHUNK = 60000
FOUR = [[0, 1, 0], [1, 1, 1], [0, 1, 0]]
LAND, SHORE, OCEAN = 0x80, 0x40, 0x20
# Straits too narrow at this scale, opened as channels so the seas stay connected: lon/lat polylines.
STRAITS = [
    [(-6.4, 35.95), (-5.6, 35.97), (-4.9, 36.05)],  # Gibraltar
    [(42.9, 13.3), (43.4, 12.6), (43.9, 12.3)],  # Bab-el-Mandeb
    [(26.1, 40.0), (26.7, 40.4), (27.5, 40.7), (28.9, 40.95), (29.1, 41.3)],  # Dardanelles, Marmara, Bosphorus
    [(36.6, 45.5), (36.6, 45.1)],  # Kerch
    [(11.6, 57.0), (12.3, 56.3), (12.65, 55.9), (12.8, 55.3)],  # Kattegat, Oresund
    [(32.3, 31.7), (32.33, 30.6), (32.57, 29.6), (32.8, 29.0), (33.2, 28.3)],  # Suez Canal, Gulf of Suez
    [(-80.1, 9.8), (-79.7, 9.2), (-79.4, 8.6)],  # Panama Canal
]
# Frontline's nations and their old-map tiles; each moves to the nearest inland tile of the new map.
NATIONS = [
    ("United States", 484, 284), ("Canada", 374, 186), ("Mexico", 375, 374), ("Cuba", 500, 378),
    ("Colombia", 527, 487), ("Venezuela", 576, 466), ("Argentina", 565, 737), ("Brazil", 684, 574),
    ("Antarctica", 1280, 975), ("Greenland", 709, 57), ("Iceland", 831, 112), ("United Kingdom", 925, 186),
    ("Ireland", 887, 183), ("Spain", 908, 264), ("Italy", 1004, 250), ("France", 948, 221),
    ("Germany", 990, 195), ("Sweden", 1014, 137), ("Poland", 1031, 193), ("Belarus", 1102, 183),
    ("Romania", 1073, 230), ("Turkey", 1123, 272), ("Norway", 969, 133), ("Finland", 1082, 126),
    ("Ukraine", 1135, 210), ("Russia", 1351, 134), ("Mongolia", 1500, 203), ("China", 1527, 303),
    ("India", 1331, 353), ("Kazakhstan", 1279, 207), ("Iran", 1238, 309), ("Saudi Arabia", 1178, 351),
    ("Australia", 1679, 657), ("New Zealand", 1890, 775), ("Algeria", 957, 295), ("Libya", 1024, 340),
    ("Egypt", 1094, 340), ("Nigeria", 956, 389), ("Sudan", 1101, 400), ("DR Congo", 1051, 513),
    ("Ethiopia", 1153, 451), ("South Africa", 1075, 707), ("Madagascar", 1194, 627), ("Chad", 1036, 420),
    ("Namibia", 1039, 646), ("Philippines", 1632, 465), ("Thailand", 1502, 415), ("Taiwan", 1610, 364),
    ("Japan", 1710, 290), ("Siberia", 1626, 118), ("Nunavut", 422, 95), ("West Antarctica", 419, 975),
    ("Peru", 516, 567), ("Zambia", 1097, 598), ("Latvia", 1067, 168), ("Bhutan", 1419, 338),
    ("Indonesia", 1511, 524), ("East Antarctica", 1809, 977), ("Oman", 1255, 382), ("Morocco", 886, 327),
    ("Uruguay", 626, 704), ("Bolivia", 581, 620), ("Alaska", 95, 115), ("Yukon", 243, 131),
    ("California", 264, 276), ("Texas", 371, 299), ("Quebec", 532, 191), ("Benin", 932, 476),
    ("Senegal", 845, 425), ("Kenya", 1152, 522), ("Pakistan", 1320, 282), ("Sri Lanka", 1384, 466),
]


def project(lon, lat):
    return (np.asarray(lon, dtype=np.float64) - LON0) * PPD, (LAT_TOP - np.asarray(lat, dtype=np.float64)) * PPD


def polygons(path):
    with open(path, encoding="utf-8") as f:
        for feat in json.load(f)["features"]:
            g = feat["geometry"]
            if g is not None:
                for rings in g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]:
                    yield feat["properties"], rings


def ring_area(ring):
    a = np.asarray(ring)
    return abs(np.dot(a[:, 0], np.roll(a[:, 1], 1)) - np.dot(a[:, 1], np.roll(a[:, 0], 1))) / 2


def draw_rings(draw, rings, fill, hole_fill):
    for i, ring in enumerate(rings):
        a = np.asarray(ring)
        x, y = project(a[:, 0], a[:, 1])
        for shift in (0.0, W) if x.min() < 0 else (0.0,):  # west of the seam: again a turn of the Earth later
            pts = list(zip(((x + shift) * SS).tolist(), (y * SS).tolist()))
            if len(pts) >= 3:
                draw.polygon(pts, fill=fill if i == 0 else hole_fill)


def land_samples(src):
    img = Image.new("L", (W * SS, H * SS), 0)
    draw = ImageDraw.Draw(img)
    for _, rings in sorted(polygons(os.path.join(src, "ne_10m_land.geojson")), key=lambda p: -ring_area(p[1][0])):
        draw_rings(draw, rings, 1, 0)
    lakes = [p for p in polygons(os.path.join(src, "ne_10m_lakes.geojson")) if (p[0].get("scalerank") or 99) <= LAKE_RANK]
    for _, rings in sorted(lakes, key=lambda p: -ring_area(p[1][0])):
        draw_rings(draw, rings, 0, 1)
    out = np.array(img, dtype=bool)
    pole = int(project(0.0, -90.0)[1] * SS)
    out[max(pole - SS, 0):, :] = True  # the rows past the South Pole: Antarctica
    return out


def elevation_samples(src):
    with netcdf_file(os.path.join(src, "etopo.nc"), "r", mmap=False) as nc:
        lats = np.array(nc.variables["latitude"][:], dtype=np.float64)
        lons = np.array(nc.variables["longitude"][:], dtype=np.float64)
        alt = np.array(nc.variables["altitude"][:], dtype=np.float64)
    lon = (LON0 + (np.arange(W * SS) + 0.5) / SS / PPD + 180.0) % 360.0 - 180.0
    lat = np.maximum(LAT_TOP - (np.arange(H * SS) + 0.5) / SS / PPD, -89.95)
    i = np.clip(np.rint((lat - lats[0]) / (lats[1] - lats[0])).astype(int), 0, len(lats) - 1)
    j = np.clip(np.rint((lon - lons[0]) / (lons[1] - lons[0])).astype(int), 0, len(lons) - 1)
    return alt[i[:, None], j[None, :]]


def magnitude(elev):
    e = np.clip(elev, 0, None)
    m = np.where(e < 300, e / 300 * 10, np.where(e < 1200, 10 + (e - 300) / 900 * 10, 20 + np.clip((e - 1200) / 2800, 0, 1) * 10))
    return np.clip(np.floor(m), 0, 30).astype(np.uint8)


def carve_straits(land):
    for line in STRAITS:
        x, y = project([p[0] for p in line], [p[1] for p in line])
        prev = None
        for i in range(len(line) - 1):
            steps = int(max(abs(x[i + 1] - x[i]), abs(y[i + 1] - y[i])) * 5) + 1
            for s in range(steps + 1):
                tx = int(x[i] + (x[i + 1] - x[i]) * s / steps)
                ty = int(y[i] + (y[i + 1] - y[i]) * s / steps)
                land[ty, tx] = False
                if prev is not None and prev[0] != tx and prev[1] != ty:
                    land[prev[1], tx] = False  # keep the channel 4-connected
                prev = (tx, ty)


def edge_labels(lab):
    return set(np.unique(np.concatenate([lab[0, :], lab[-1, :], lab[:, 0], lab[:, -1]])).tolist()) - {0}


def tidy(land):
    """Drops tiny islands and fills tiny lakes in place; returns the mask of filled lake tiles."""
    lab, _ = ndimage.label(land, structure=FOUR)
    small = np.bincount(lab.ravel()) < MIN_ISLAND
    small[0] = False
    land[small[lab]] = False
    lab, _ = ndimage.label(~land, structure=FOUR)
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    small = sizes < MIN_LAKE
    small[0] = False
    small[int(np.argmax(sizes))] = False
    for e in edge_labels(lab):
        small[e] = False
    filled = small[lab]
    land[filled] = True
    return filled


def finish(typed):
    """Adds the shoreline and ocean bits, and water magnitude = ceil(distance from shore / 2), capped at 31."""
    grid = typed.reshape(H, W)
    water = (grid & LAND) == 0
    lab, n = ndimage.label(water, structure=FOUR)
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    sizes[0] = 0
    oceans = edge_labels(lab) | {int(np.argmax(sizes))}
    is_ocean = np.isin(lab, sorted(oceans)) & water
    near_water = ndimage.binary_dilation(water, structure=FOUR) & ~water
    near_land = ndimage.binary_dilation(~water, structure=FOUR) & water
    dist = np.full((H, W), -1, dtype=np.int32)
    queue = collections.deque()
    for y, x in zip(*np.nonzero(near_land)):
        dist[y, x] = 0
        queue.append((int(y), int(x)))
    while queue:
        y, x = queue.popleft()
        d = dist[y, x] + 1
        for yy, xx in ((y, x - 1), (y, x + 1), (y - 1, x), (y + 1, x)):
            if 0 <= yy < H and 0 <= xx < W and water[yy, xx] and dist[yy, xx] < 0:
                dist[yy, xx] = d
                queue.append((yy, xx))
    out = grid.copy()
    out[near_water] |= SHORE
    out[is_ocean] |= OCEAN
    out[near_land] |= SHORE
    far = water & (dist > 0)
    out[far] |= np.minimum(np.ceil(dist[far] / 2.0 - 1e-9), 31).astype(np.uint8)
    return out


def nearest_inland(grid, x, y, radius=60):
    best = None
    for r in range(radius + 1):
        for dy in range(-r, r + 1):
            for dx in (-r, r) if abs(dy) != r else range(-r, r + 1):
                xx, yy = x + dx, y + dy
                if 0 <= xx < W and 0 <= yy < H:
                    b = grid[yy, xx]
                    if b & LAND and not b & SHORE:
                        return xx, yy, r
                    if b & LAND and best is None:
                        best = (xx, yy, r)
        if best is not None and r >= 3:
            return best
    return best


def encode(grid):
    """MapData.decodeChunks' format: (value, varint length - 1) runs, then base64."""
    flat = grid.ravel()
    ends = np.nonzero(flat[1:] != flat[:-1])[0] + 1
    starts = np.concatenate([[0], ends])
    lengths = np.diff(np.concatenate([starts, [flat.size]]))
    out = bytearray()
    for s, n in zip(starts.tolist(), lengths.tolist()):
        out.append(int(flat[s]))
        n -= 1
        while n >= 0x80:
            out.append((n & 0x7F) | 0x80)
            n >>= 7
        out.append(n)
    return base64.b64encode(bytes(out)).decode("ascii")


def main():
    src, dst = sys.argv[1], sys.argv[2]
    os.makedirs(os.path.join(dst, "chunks"), exist_ok=True)
    land_s = land_samples(src)
    elev_s = elevation_samples(src)
    land = land_s.reshape(H, SS, W, SS).mean(axis=(1, 3)) > 0.5
    carve_straits(land)
    filled = tidy(land)
    count = land_s.reshape(H, SS, W, SS).sum(axis=(1, 3))
    elev = np.where(land_s, elev_s, 0).reshape(H, SS, W, SS).sum(axis=(1, 3)) / np.maximum(count, 1)
    mag = magnitude(elev)
    for _ in range(6):  # a filled lake takes the height of the land around it
        near = ndimage.grey_dilation(np.where(filled, 0, mag), footprint=FOUR)
        mag = np.where(filled, np.maximum(mag, near), mag)
    grid = finish(np.where(land, LAND | mag, 0).astype(np.uint8))

    text = encode(grid)
    for name in os.listdir(os.path.join(dst, "chunks")):
        os.remove(os.path.join(dst, "chunks", name))
    n = 0
    for i in range(0, len(text), CHUNK):
        n += 1
        with open(os.path.join(dst, "chunks", "%03d.txt" % n), "w", encoding="ascii") as f:
            f.write(text[i:i + CHUNK])

    placed = []
    moved = []
    for name, x, y in NATIONS:
        p = nearest_inland(grid, x, y)
        if p is None:
            raise SystemExit("no land near " + name)
        placed.append((name, p[0], p[1]))
        if p[2] > 0:
            moved.append("%s %d" % (name, p[2]))
    with open(os.path.join(dst, "nations.txt"), "w", encoding="utf-8") as f:
        for name, x, y in placed:
            f.write('\t\t{ name = "%s", x = %d, y = %d },\n' % (name, x, y))

    m = grid & 0x1F
    img = np.zeros((H, W, 3), np.uint8)
    water = (grid & LAND) == 0
    img[water] = np.stack([20 + 0 * m[water], 60 - m[water], 110 - m[water] * 2], -1)
    img[water & ((grid & OCEAN) == 0)] = (70, 140, 210)
    lm = ~water
    img[lm] = np.stack([70 + m[lm].astype(int) * 5, 130 - m[lm].astype(int), 60 + m[lm].astype(int) * 2], -1).clip(0, 255)
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    for name, x, y in placed:
        d.rectangle([x - 2, y - 2, x + 2, y + 2], fill=(255, 255, 255))
        d.text((x + 4, y - 6), name, fill=(255, 255, 255))
    im.save(os.path.join(dst, "preview.png"))

    lab, _ = ndimage.label(water, structure=FOUR)
    print("land", int(land.sum()), "water bodies", int(lab.max()), "lake tiles", int((water & ((grid & OCEAN) == 0)).sum()),
          "chunks", n, "chars", len(text))
    print("moved:", ", ".join(moved) or "none")


if __name__ == "__main__":
    main()
