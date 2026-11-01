import math
from PIL import Image, ImageDraw, ImageFilter

def create_thermalright_icon():
    # Render at 1024x1024 with supersampling, downscale to 512x512 for ultra-crisp edges
    S = 1024
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = S // 2, S // 2

    # 1. Subtle Outer Ambient Glow (ARGB Cyan / Electric Blue)
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    for r in range(480, 360, -10):
        alpha = int(25 * (1.0 - (r - 360) / 120.0))
        glow_draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 200, 255, alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(16))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # 2. Outer Octagonal / Rounded Bezel (Dark Titanium Armor)
    outer_r = 430
    bezel_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    b_draw = ImageDraw.Draw(bezel_layer)
    b_draw.rounded_rectangle([cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r], radius=110, fill=(18, 22, 30, 255), outline=(45, 55, 75, 255), width=8)
    
    # Inner metallic ring on bezel
    b_draw.rounded_rectangle([cx - outer_r + 16, cy - outer_r + 16, cx + outer_r - 16, cy + outer_r - 16], radius=96, fill=(10, 13, 18, 255), outline=(30, 38, 52, 255), width=4)
    img = Image.alpha_composite(img, bezel_layer)
    draw = ImageDraw.Draw(img)

    # 3. Four Bezel Screws / Hardware Accents in corners
    screw_offset = outer_r - 50
    for sx, sy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
        px, py = cx + sx * screw_offset, cy + sy * screw_offset
        draw.ellipse([px - 14, py - 14, px + 14, py + 14], fill=(32, 40, 56, 255), outline=(70, 85, 115, 255), width=3)
        draw.line([px - 8, py, px + 8, py], fill=(120, 140, 180, 255), width=3)

    # 4. AIO Circular LCD Screen Bezel (Stepped Ring)
    lcd_outer_r = 345
    # Neon ARGB Ring Accent (Cyan to Sapphire Blue Gradient)
    ring_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    r_draw = ImageDraw.Draw(ring_layer)
    r_draw.ellipse([cx - lcd_outer_r, cy - lcd_outer_r, cx + lcd_outer_r, cy + lcd_outer_r], outline=(0, 220, 255, 230), width=10)
    r_draw.ellipse([cx - lcd_outer_r + 10, cy - lcd_outer_r + 10, cx + lcd_outer_r - 10, cy + lcd_outer_r - 10], outline=(0, 110, 255, 180), width=6)
    
    # LCD Display Panel Interior (Deep Onyx Glass)
    lcd_r = 325
    r_draw.ellipse([cx - lcd_r, cy - lcd_r, cx + lcd_r, cy + lcd_r], fill=(5, 7, 11, 255), outline=(20, 30, 45, 255), width=4)
    img = Image.alpha_composite(img, ring_layer)
    draw = ImageDraw.Draw(img)

    # 5. LCD Tech HUD Elements (Tick Marks / Gauge Arc)
    for deg in range(0, 360, 15):
        rad = math.radians(deg)
        r1 = lcd_r - 12
        r2 = lcd_r - 26 if deg % 45 == 0 else lcd_r - 20
        col = (0, 230, 255, 220) if deg % 45 == 0 else (0, 160, 220, 120)
        x1, y1 = cx + r1 * math.cos(rad), cy + r1 * math.sin(rad)
        x2, y2 = cx + r2 * math.cos(rad), cy + r2 * math.sin(rad)
        draw.line([x1, y1, x2, y2], fill=col, width=4 if deg % 45 == 0 else 2)

    # 6. Central "Frozen" Crystal & Cybernetic Vortex Core
    core_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    c_draw = ImageDraw.Draw(core_layer)

    # Central Glow
    for cr in range(160, 40, -10):
        alpha = int(40 * (1.0 - (cr - 40) / 120.0))
        c_draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(0, 180, 255, alpha))

    # Hexagonal Cyber Crystal Center
    hex_r = 175
    hex_pts = []
    for i in range(6):
        a = math.radians(i * 60 - 30)
        hex_pts.append((cx + hex_r * math.cos(a), cy + hex_r * math.sin(a)))
    c_draw.polygon(hex_pts, outline=(0, 240, 255, 240), fill=(8, 22, 38, 200))

    # Inner Hexagon
    inner_hex_r = 135
    inner_pts = []
    for i in range(6):
        a = math.radians(i * 60 - 30)
        inner_pts.append((cx + inner_hex_r * math.cos(a), cy + inner_hex_r * math.sin(a)))
    c_draw.polygon(inner_pts, outline=(0, 140, 255, 180), fill=(4, 12, 24, 230))

    # 6-Blade Cybernetic Cooling Fan / Crystal Spikes
    for i in range(6):
        angle = math.radians(i * 60)
        tip_r = 230
        base_r = 60
        tx, ty = cx + tip_r * math.cos(angle), cy + tip_r * math.sin(angle)
        
        # Crystal wing points
        w1_a = angle + math.radians(16)
        w2_a = angle - math.radians(16)
        mid_r = 160
        p1 = (cx + mid_r * math.cos(w1_a), cy + mid_r * math.sin(w1_a))
        p2 = (cx + mid_r * math.cos(w2_a), cy + mid_r * math.sin(w2_a))
        center_pt = (cx + base_r * math.cos(angle), cy + base_r * math.sin(angle))
        
        # Faceted shading (one side cyan, other deep sapphire)
        c_draw.polygon([(cx, cy), p1, (tx, ty)], fill=(0, 210, 255, 190), outline=(0, 255, 255, 240))
        c_draw.polygon([(cx, cy), p2, (tx, ty)], fill=(0, 95, 215, 220), outline=(0, 180, 255, 240))

    # Center TR / Frost Shield Emblem
    center_shield_r = 65
    c_draw.ellipse([cx - center_shield_r, cy - center_shield_r, cx + center_shield_r, cy + center_shield_r], fill=(12, 18, 28, 255), outline=(0, 240, 255, 255), width=6)
    c_draw.ellipse([cx - center_shield_r + 10, cy - center_shield_r + 10, cx + center_shield_r - 10, cy + center_shield_r - 10], fill=(0, 30, 60, 255), outline=(0, 140, 255, 200), width=3)
    
    # Futuristic "T" and "R" Monogram bars in center
    # "T" bar
    c_draw.rectangle([cx - 32, cy - 26, cx + 32, cy - 14], fill=(240, 250, 255, 255))
    c_draw.rectangle([cx - 7, cy - 14, cx + 7, cy + 26], fill=(240, 250, 255, 255))
    # Subtle orange/amber accent dot
    c_draw.ellipse([cx - 5, cy + 30, cx + 5, cy + 40], fill=(255, 160, 20, 255))

    img = Image.alpha_composite(img, core_layer)
    draw = ImageDraw.Draw(img)

    # 7. High-tech diagonal glass lens sheen / reflection across LCD
    sheen = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(sheen)
    # Arc-clipped reflection polygon
    s_draw.polygon([(cx - 280, cy - 310), (cx + 100, cy - 310), (cx - 100, cy + 180), (cx - 280, cy + 180)], fill=(255, 255, 255, 14))
    sheen = sheen.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img, sheen)

    # 8. High-quality Downsampling to 512x512
    final_512 = img.resize((512, 512), Image.Resampling.LANCZOS)
    return final_512

if __name__ == "__main__":
    import os
    out_dir = r"C:\Users\Admin\.gemini\antigravity\scratch\WarframeDisplay\assets"
    os.makedirs(out_dir, exist_ok=True)
    
    icon_512 = create_thermalright_icon()
    
    # Save standard sizes
    sizes = [512, 256, 128, 64, 48, 32, 16]
    saved_images = {}
    for sz in sizes:
        resized = icon_512.resize((sz, sz), Image.Resampling.LANCZOS)
        p = os.path.join(out_dir, f"icon_{sz}.png")
        resized.save(p, format="PNG")
        saved_images[sz] = resized
        print(f"Generated {p}")
        
    # Main app_icon.png
    app_icon_png = os.path.join(out_dir, "app_icon.png")
    icon_512.save(app_icon_png, format="PNG")
    print(f"Saved primary {app_icon_png}")

    # Generate multi-size .ico (16, 24, 32, 48, 64, 128, 256)
    ico_path = os.path.join(out_dir, "app_icon.ico")
    icon_512.save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )
    print(f"Saved multi-resolution ICO {ico_path}")

    # Also save favicon.ico in web directory
    web_dir = r"C:\Users\Admin\.gemini\antigravity\scratch\WarframeDisplay\web"
    web_ico = os.path.join(web_dir, "favicon.ico")
    icon_512.save(
        web_ico,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64)]
    )
    print(f"Saved {web_ico}")

