from PIL import Image
for name in ["top_index.html.png", "top_gd.html.png", "top_daily_index.html.png"]:
    img = Image.open("E:/AI24X/ai24x-website/ai24x01/p/a1/tmp_card/" + name).convert("RGB")
    W, H = img.size
    # find horizontal band where content differs from header band (detect non-background rows)
    # sample: for each row, count pixels differing from pure bg (panel color ~ (26,30,40)?) - simpler: crop and report color at left margin
    print(name, img.size)
    # left edge content start: scan row 90 (below header) for first non-bg pixel x
    row = 90
    px = [img.getpixel((x, row)) for x in range(0, W, 4)]
    print("  row90 first colored x:", next((x for x, p in enumerate(px) if abs(p[0]-255)>12 or abs(p[1]-255)>12 or abs(p[2]-255)>12), None))
