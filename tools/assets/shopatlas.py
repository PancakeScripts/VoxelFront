import sys, os
from PIL import Image
src, outdir = sys.argv[1], sys.argv[2]
names = [("silver_eagle","epic.png"),("golden_drake","epic2.png"),("amethyst_crown","epic3.png"),("golden_stag","epic4.png"),("white_wolf","epic5.png"),("blue_comet","epic6.png"),("crimson_howl","epic7.png"),("royal_blades","epic8.png"),("golden_lion","epic9.png"),("celestial_phoenix","legendary.png"),("blazing_lion","legendary2.png"),("crimson_dragon","legendary3.png"),("storm_trident","legendary4.png")]
FW, FH, CW, CH, COLS = 232, 152, 240, 160, 4
rows = (len(names) + COLS - 1) // COLS
sheet = Image.new("RGBA", (COLS * CW, rows * CH), (0, 0, 0, 0))
for k, (key, f) in enumerate(names):
    im = Image.open(os.path.join(src, f)).convert("RGBA")
    im.thumbnail((FW, FH), Image.LANCZOS)
    cx, cy = (k % COLS) * CW, (k // COLS) * CH
    x, y = cx + (CW - im.width) // 2, cy + (CH - im.height) // 2
    sheet.alpha_composite(im, (x, y))
    print(f'{key} {x} {y} {im.width} {im.height}')
os.makedirs(outdir, exist_ok=True)
sheet.save(os.path.join(outdir, "shop_flags.png"), optimize=True)
print(sheet.size)
