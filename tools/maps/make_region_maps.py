#!/usr/bin/env python3
"""Builds Frontline's continent maps (about 1.5M tiles each) from public-domain data: Natural Earth (land, lakes,
countries) and NOAA ETOPO1 (elevation). Uses the helpers of make_world_map.py.

usage: make_region_maps.py <source dir> <output dir> [map id ...]
Reads ne_10m_land.geojson, ne_10m_lakes.geojson, ne_50m_admin_0_countries.geojson and etopo.nc from <source dir>; writes
<output dir>/<id>/chunks/001.txt..., nations.txt, size.txt and preview.png.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.io import netcdf_file

import make_world_map as m

TILES = 1_500_000
SS = m.SS
MIN_NATION_TILES = 250
# id: lon0, lon1, lat0 (south), lat1 (north)
REGIONS = {
    "europe": (-25.0, 50.0, 34.0, 72.0),
    "asia": (25.0, 150.0, -11.0, 62.0),
    "africa": (-20.0, 55.0, -37.0, 38.0),
    "namerica": (-170.0, -50.0, 7.0, 75.0),
    "samerica": (-85.0, -33.0, -56.0, 14.0),
}
EXTRA_STRAITS = [[(-6.4, 35.95), (-5.6, 35.97), (-4.9, 36.05)]]
# Water that must stay connected: (name, lon, lat) pairs, the first of each map being the open ocean.
SEAS = {
    "europe": [("Atlantic", -15, 45), ("Mediterranean", 5, 38), ("Black Sea", 34, 43), ("Azov", 36.8, 46), ("Baltic", 19, 58), ("North Sea", 3, 56)],
    "asia": [("Indian", 70, 5), ("Mediterranean", 30, 34), ("Black Sea", 35, 43), ("Red Sea", 38, 20), ("Persian Gulf", 51, 27), ("Pacific", 140, 30), ("South China Sea", 113, 12), ("Java Sea", 112, -5)],
    "africa": [("Atlantic", -15, 10), ("Mediterranean", 15, 35), ("Red Sea", 38, 20), ("Indian", 50, -10)],
    "namerica": [("Pacific", -120, 20), ("Atlantic", -60, 30), ("Gulf of Mexico", -90, 25), ("Caribbean", -75, 15), ("Hudson Bay", -85, 60)],
    "samerica": [("Pacific", -80, -20), ("Atlantic", -35, -20), ("Caribbean", -75, 13)],
}
# Natural Earth names too long for a label, and overseas land named after what it is.
ALIASES = {
    "Democratic Republic of the Congo": "DR Congo", "Republic of the Congo": "Congo", "United States of America": "United States",
    "Bosnia and Herzegovina": "Bosnia", "Central African Republic": "Central Africa", "United Republic of Tanzania": "Tanzania",
    "Republic of Serbia": "Serbia", "North Macedonia": "Macedonia", "Dominican Republic": "Dominican Rep.", "United Arab Emirates": "UAE",
    "Ivory Coast": "Ivory Coast", "Equatorial Guinea": "Eq. Guinea", "Czechia": "Czechia", "South Sudan": "South Sudan",
}
OVERSEAS = {("samerica", "France"): "French Guiana"}


def setup(region):
    lon0, lon1, lat0, lat1 = REGIONS[region]
    cosine = math.cos(math.radians((lat0 + lat1) / 2))
    aspect = (lon1 - lon0) * cosine / (lat1 - lat0)
    h = int(round(math.sqrt(TILES / aspect)))
    w = int(round(h * aspect))
    m.W, m.H = w, h
    sx, sy = w / (lon1 - lon0), h / (lat1 - lat0)

    def project(lon, lat):
        return (np.asarray(lon, dtype=np.float64) - lon0) * sx, (lat1 - np.asarray(lat, dtype=np.float64)) * sy

    m.project = project
    return lon0, lat1, sx, sy


def draw_rings(draw, rings, fill, hole_fill):
    for i, ring in enumerate(rings):
        a = np.asarray(ring)
        x, y = m.project(a[:, 0], a[:, 1])
        if x.max() < -5 or x.min() > m.W + 5 or y.max() < -5 or y.min() > m.H + 5:
            continue
        pts = list(zip((x * SS).tolist(), (y * SS).tolist()))
        if len(pts) >= 3:
            draw.polygon(pts, fill=fill if i == 0 else hole_fill)


def land_samples(src):
    img = Image.new("L", (m.W * SS, m.H * SS), 0)
    draw = ImageDraw.Draw(img)
    for _, rings in sorted(m.polygons(os.path.join(src, "ne_10m_land.geojson")), key=lambda p: -m.ring_area(p[1][0])):
        draw_rings(draw, rings, 1, 0)
    lakes = [p for p in m.polygons(os.path.join(src, "ne_10m_lakes.geojson")) if (p[0].get("scalerank") or 99) <= m.LAKE_RANK]
    for _, rings in sorted(lakes, key=lambda p: -m.ring_area(p[1][0])):
        draw_rings(draw, rings, 0, 1)
    return np.array(img, dtype=bool)


def elevation_samples(src, lon0, lat1, sx, sy):
    with netcdf_file(os.path.join(src, "etopo.nc"), "r", mmap=False) as nc:
        lats = np.array(nc.variables["latitude"][:], dtype=np.float64)
        lons = np.array(nc.variables["longitude"][:], dtype=np.float64)
        alt = np.array(nc.variables["altitude"][:], dtype=np.float64)
    lon = lon0 + (np.arange(m.W * SS) + 0.5) / SS / sx
    lat = lat1 - (np.arange(m.H * SS) + 0.5) / SS / sy
    i = np.clip(np.rint((lat - lats[0]) / (lats[1] - lats[0])).astype(int), 0, len(lats) - 1)
    j = np.clip(np.rint((lon - lons[0]) / (lons[1] - lons[0])).astype(int), 0, len(lons) - 1)
    return alt[i[:, None], j[None, :]]


def carve(land):
    for line in m.STRAITS + EXTRA_STRAITS:
        x, y = m.project([p[0] for p in line], [p[1] for p in line])
        prev = None
        for i in range(len(line) - 1):
            steps = int(max(abs(x[i + 1] - x[i]), abs(y[i + 1] - y[i])) * 5) + 1
            for s in range(steps + 1):
                tx = int(x[i] + (x[i + 1] - x[i]) * s / steps)
                ty = int(y[i] + (y[i + 1] - y[i]) * s / steps)
                if 0 <= tx < m.W and 0 <= ty < m.H:
                    land[ty, tx] = False
                    if prev is not None and prev[0] != tx and prev[1] != ty and 0 <= prev[1] < m.H:
                        land[prev[1], tx] = False  # keep the channel 4-connected
                    prev = (tx, ty)


def nations(region, src, grid):
    """A nation per country with enough land on this map, placed at the point farthest from its border and the sea."""
    land = (grid & m.LAND) != 0
    with open(os.path.join(src, "ne_50m_admin_0_countries.geojson"), encoding="utf-8") as f:
        feats = json.load(f)["features"]
    out = []
    for feat in feats:
        props, g = feat["properties"], feat["geometry"]
        if g is None or props.get("TYPE") == "Dependency" and props.get("ADMIN") != "Greenland":
            continue
        img = Image.new("L", (m.W, m.H), 0)
        draw = ImageDraw.Draw(img)
        for rings in g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]:
            for i, ring in enumerate(rings):
                a = np.asarray(ring)
                x, y = m.project(a[:, 0], a[:, 1])
                if x.max() < 0 or x.min() > m.W or y.max() < 0 or y.min() > m.H or len(a) < 3:
                    continue
                draw.polygon(list(zip(x.tolist(), y.tolist())), fill=1 if i == 0 else 0)
        mask = (np.array(img, dtype=bool)) & land
        count = int(mask.sum())
        if count < MIN_NATION_TILES:
            continue
        dist = ndimage.distance_transform_edt(mask)
        y, x = np.unravel_index(int(np.argmax(dist)), dist.shape)
        name = props.get("ADMIN") or props.get("NAME")
        name = OVERSEAS.get((region, name), ALIASES.get(name, name))
        out.append((count, name, int(x), int(y)))
    out.sort(key=lambda n: -n[0])
    return out


def preview(grid, placed, path):
    mag = grid & 0x1F
    img = np.zeros((m.H, m.W, 3), np.uint8)
    water = (grid & m.LAND) == 0
    img[water] = (40, 90, 150)
    img[water & ((grid & m.OCEAN) == 0)] = (90, 170, 230)
    lm = ~water
    img[lm] = np.stack([70 + mag[lm].astype(int) * 5, 130 - mag[lm].astype(int), 60 + mag[lm].astype(int) * 2], -1).clip(0, 255)
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    for _, name, x, y in placed:
        d.rectangle([x - 3, y - 3, x + 3, y + 3], fill=(255, 255, 255))
        d.text((x + 5, y - 6), name, fill=(255, 255, 255))
    im.save(path)


def check_seas(region, grid):
    water = (grid & m.LAND) == 0
    lab, _ = ndimage.label(water, structure=m.FOUR)
    ids = []
    report = []
    for name, lon, lat in SEAS[region]:
        x, y = m.project(lon, lat)
        c = lab[int(y), int(x)]
        ids.append(c)
        report.append("%s:%s" % (name, "ok" if c != 0 and c == ids[0] else "CUT(%d)" % c))
    return " ".join(report)


def build(region, src, dst):
    lon0, lat1, sx, sy = setup(region)
    out = os.path.join(dst, region)
    os.makedirs(os.path.join(out, "chunks"), exist_ok=True)
    land_s = land_samples(src)
    elev_s = elevation_samples(src, lon0, lat1, sx, sy)
    land = land_s.reshape(m.H, SS, m.W, SS).mean(axis=(1, 3)) > 0.5
    carve(land)
    filled = m.tidy(land)
    count = land_s.reshape(m.H, SS, m.W, SS).sum(axis=(1, 3))
    elev = np.where(land_s, elev_s, 0).reshape(m.H, SS, m.W, SS).sum(axis=(1, 3)) / np.maximum(count, 1)
    mag = m.magnitude(elev)
    for _ in range(6):
        near = ndimage.grey_dilation(np.where(filled, 0, mag), footprint=m.FOUR)
        mag = np.where(filled, np.maximum(mag, near), mag)
    grid = m.finish(np.where(land, m.LAND | mag, 0).astype(np.uint8))

    text = m.encode(grid)
    for name in os.listdir(os.path.join(out, "chunks")):
        os.remove(os.path.join(out, "chunks", name))
    n = 0
    for i in range(0, len(text), m.CHUNK):
        n += 1
        with open(os.path.join(out, "chunks", "%03d.txt" % n), "w", encoding="ascii") as f:
            f.write(text[i:i + m.CHUNK])

    placed = nations(region, src, grid)
    with open(os.path.join(out, "nations.txt"), "w", encoding="utf-8") as f:
        for _, name, x, y in placed:
            f.write('\t\t{ name = "%s", x = %d, y = %d },\n' % (name, x, y))
    with open(os.path.join(out, "size.txt"), "w", encoding="ascii") as f:
        f.write("%d %d %d %d" % (m.W, m.H, int(land.sum()), n))
    preview(grid, placed, os.path.join(out, "preview.png"))
    print(region, "%dx%d" % (m.W, m.H), "land", int(land.sum()), "chunks", n, "chars", len(text), "nations", len(placed))
    print("  seas:", check_seas(region, grid))
    print("  names:", ", ".join(p[1] for p in placed))


def main():
    src, dst = sys.argv[1], sys.argv[2]
    for region in sys.argv[3:] or REGIONS:
        build(region, src, dst)


if __name__ == "__main__":
    main()
