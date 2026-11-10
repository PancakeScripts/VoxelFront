# Voxel Front

Voxel Front is a Roblox real-time strategy game: grow your nation on a pixel map of the world, attack
your neighbours, build cities, ports and missile silos, and conquer 80% of the land. Play solo against
AI nations or in public free-for-all and team matches.

Voxel Front is a modified version of [OpenFront](https://github.com/openfrontio/OpenFrontIO), and parts of
it are adapted from [RoWorld](https://github.com/lukechatton/roworld). It is not affiliated with or
endorsed by OpenFront.

## What is in this repository

| Path | What it is |
| --- | --- |
| `Voxel Front v0.1.rbxlx` | The complete game: every script, the UI and all other instances (Roblox Studio XML place file). |
| `tools/maps/` | Python tools that generate the world and continent maps, their nations and thumbnails. |
| `tools/assets/` | Python tools that generate the crate images, the shop flag atlas, shadows and menu effects. |
| `assets/` | Images made by those tools and the source art of the shop flags. |
| `LICENSE` | GNU AGPL v3.0 with additional terms (section 7). |
| `LICENSE-ASSETS` | CC BY-SA 4.0 and notes for data and images. |

## Open the game

1. Install [Roblox Studio](https://create.roblox.com/).
2. Open `Voxel Front v0.1.rbxlx` (File > Open from File).
3. Press Play to test a solo match.

Code layout inside the place:

- `ServerScriptService.Server`: server (matches, lobbies, parties, wallet, analytics).
  Tests are in `ServerScriptService.Server.Dev` and run in Studio during Play (server side).
- `ReplicatedStorage.Shared`: shared game logic (`Shared.Core` is the simulation) and data.
- `StarterPlayer.StarterPlayerScripts.Client`: client (map renderer, HUD, menus).
- `StarterGui`: the UI.

Image, sound and product ids in `ReplicatedStorage.Shared.Assets` point to the original experience's uploads.

## Tools

```bash
pip install -r tools/requirements.txt
python tools/maps/make_world_map.py <source dir> <output dir>
```

The map tools need public-domain source data that is not stored here:

- Natural Earth 1:10m Land and Lakes, and 1:50m Admin 0 Countries (GeoJSON): https://www.naturalearthdata.com/
- NOAA ETOPO1 global relief (NetCDF, saved as `etopo.nc`): https://www.ncei.noaa.gov/products/etopo-global-relief-model

Each tool explains its arguments at the top of the file.

## Credits and license

- © OpenFront and Contributors. OpenFront is licensed under the GNU AGPL v3.0 with additional terms.
- Parts adapted from RoWorld, © 2026 Snick Co. (GNU AGPL v3.0).
- Nation list adapted from OpenFront (CC BY-SA 4.0).
- Maps made with Natural Earth and NOAA ETOPO1 data (public domain). Flags from Wikimedia Commons.

Voxel Front is free software: you can redistribute it and/or modify it under the terms of the GNU Affero
General Public License, version 3, with the additional terms in [LICENSE](LICENSE). It comes with
ABSOLUTELY NO WARRANTY. See [LICENSE](LICENSE) and [LICENSE-ASSETS](LICENSE-ASSETS).
