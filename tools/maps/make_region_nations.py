#!/usr/bin/env python3
"""Places the World map's nations on the continent maps. The World list is the only source of nations (no other
names); a continent map gets:
  * the World nations whose World spot falls on it, at the same place on Earth;
  * EDGE_NATIONS: spot just off the map while their land shows, placed at the map's edge nearest their spot;
  * every other World nation (a whole country in Natural Earth) with at least MIN_VISIBLE land tiles on the map, placed
    at the middle of that visible land.

usage: make_region_nations.py <world nations tsv> <ne countries geojson> <regions dir> [map id ...]
<world nations tsv>: name <tab> x <tab> y per line, the spots of Shared.Maps.WorldNations (2000x1000 World map).
Reads <regions dir>/<id>/chunks and writes <regions dir>/<id>/nations.txt (the Luau lines of the nations table).
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

import make_map_thumbs as thumbs
import make_region_maps as regions
import make_world_map as world

WORLD_W = 2000
WORLD_PPD = WORLD_W / 360.0
WORLD_LON0 = -180.0 + 65 / WORLD_PPD
WORLD_LAT_TOP = 90.0 - 10 / WORLD_PPD
MAX_MOVE = 25  # a spot this many tiles from any land on the continent map is not on it
EDGE_MARGIN = 12  # start circles must fit on the map: nations placed at least this far from its edge
EDGE_MOVE = 60
EDGE_NATIONS = {
    "europe": ["Morocco"],
    "asia": ["Russia", "Siberia"],
    "namerica": ["Greenland"],
}
MIN_VISIBLE = 100
# Natural Earth country of a World nation, where the names differ
NE_NAMES = {"United States": "United States of America", "DR Congo": "Democratic Republic of the Congo"}
# land of a World nation that is not that nation on this map (overseas territory)
NOT_HERE = {"samerica": ["France"], "namerica": ["France"]}


def world_lonlat(x, y):
    lon = WORLD_LON0 + (x + 0.5) / WORLD_PPD
    if lon > 180.0:
        lon -= 360.0
    return lon, WORLD_LAT_TOP - (y + 0.5) / WORLD_PPD


def country_mask(feature, w, h):
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    g = feature["geometry"]
    for rings in g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]:
        for i, ring in enumerate(rings):
            a = np.asarray(ring)
            x, y = regions.m.project(a[:, 0], a[:, 1])
            if len(a) >= 3:
                d.polygon(list(zip(x.tolist(), y.tolist())), fill=1 if i == 0 else 0)
    return np.asarray(img, dtype=bool)


def main():
    tsv, ne_path, root = sys.argv[1], sys.argv[2], sys.argv[3]
    spots = []
    for line in open(tsv, encoding="utf-8"):
        parts = line.rstrip("\n").split("\t")
        if len(parts) == 3:
            spots.append((parts[0], int(parts[1]), int(parts[2])))
    with open(ne_path, encoding="utf-8") as f:
        countries = {feat["properties"]["ADMIN"]: feat for feat in json.load(f)["features"]}
    for region in sys.argv[4:] or regions.REGIONS:
        regions.setup(region)
        w, h = world.W, world.H
        grid = thumbs.decode(os.path.join(root, region), w * h).reshape(h, w)
        inner = grid.copy()
        inner[:EDGE_MARGIN, :] = 0
        inner[-EDGE_MARGIN:, :] = 0
        inner[:, :EDGE_MARGIN] = 0
        inner[:, -EDGE_MARGIN:] = 0
        inland = ((inner & world.LAND) != 0) & ((inner & world.SHORE) == 0)
        placed, skipped = [], []
        for name, x, y in spots:
            lon, lat = world_lonlat(x, y)
            rx, ry = regions.m.project(lon, lat)
            rx, ry = int(rx), int(ry)
            edge = name in EDGE_NATIONS.get(region, [])
            if not (0 <= rx < w and 0 <= ry < h):
                if not edge:
                    continue
                rx, ry = min(max(rx, EDGE_MARGIN), w - 1 - EDGE_MARGIN), min(max(ry, EDGE_MARGIN), h - 1 - EDGE_MARGIN)
            p = world.nearest_inland(inner if edge else grid, rx, ry, EDGE_MOVE if edge else MAX_MOVE)
            if p is None:
                skipped.append(name)
                continue
            placed.append((name, p[0], p[1], "moved %d" % p[2] if p[2] else ""))
        have = {p[0] for p in placed}
        for name, _, _ in spots:
            feat = countries.get(NE_NAMES.get(name, name))
            if name in have or feat is None or name in NOT_HERE.get(region, []):
                continue
            mask = country_mask(feat, w, h) & inland
            if int(mask.sum()) < MIN_VISIBLE:
                continue
            dist = ndimage.distance_transform_edt(mask)
            yy, xx = np.unravel_index(int(np.argmax(dist)), dist.shape)
            placed.append((name, int(xx), int(yy), "visible land %d" % int(mask.sum())))
        with open(os.path.join(root, region, "nations.txt"), "w", encoding="utf-8") as f:
            for name, x, y, _ in placed:
                f.write('\t\t{ name = "%s", x = %d, y = %d },\n' % (name, x, y))
        print(region, len(placed), ", ".join("%s%s" % (n, " (%s)" % note if note else "") for n, _, _, note in placed))
        if skipped:
            print("  on the map but no land nearby:", ", ".join(skipped))


if __name__ == "__main__":
    main()
