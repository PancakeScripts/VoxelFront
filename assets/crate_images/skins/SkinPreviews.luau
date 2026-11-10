-- Crate territory skin previews (patterns as RoWorld's Data/Cosmetics). Upload skin_previews.png,
-- put its id in `image`; each skin's rect: ImageRectOffset = x, y; ImageRectSize = w, h.
-- Draw with ResampleMode Pixelated.
return {
	image = "",
	cells = {
		stripes = { 0, 0, 96, 96 }, -- Stripes (common)
		bands = { 100, 0, 96, 96 }, -- Bands (common)
		checker = { 200, 0, 96, 96 }, -- Checker (common)
		diagonal = { 300, 0, 96, 96 }, -- Diagonal (common)
		dots = { 400, 0, 96, 96 }, -- Dots (common)
		grid = { 500, 0, 96, 96 }, -- Grid (common)
		bricks = { 600, 0, 96, 96 }, -- Bricks (rare)
		waves = { 0, 100, 96, 96 }, -- Waves (rare)
		diamonds = { 100, 100, 96, 96 }, -- Diamonds (rare)
		crosshatch = { 200, 100, 96, 96 }, -- Crosshatch (rare)
		zigzag = { 300, 100, 96, 96 }, -- Zigzag (rare)
		cobble = { 400, 100, 96, 96 }, -- Cobble (rare)
		stars = { 500, 100, 96, 96 }, -- Starfield (epic)
		camo = { 600, 100, 96, 96 }, -- Camouflage (epic)
		circuit = { 0, 200, 96, 96 }, -- Circuit (epic)
		hex = { 100, 200, 96, 96 }, -- Hive (epic)
		tartan = { 200, 200, 96, 96 }, -- Tartan (epic)
		gilded = { 300, 200, 96, 96 }, -- Gilded (legendary)
		frost = { 400, 200, 96, 96 }, -- Frost (legendary)
		obsidian = { 500, 200, 96, 96 }, -- Obsidian (legendary)
		ember = { 600, 200, 96, 96 }, -- Ember (legendary)
	},
}
