"""Generate AlphaLens favicon/OG assets from the site's own brand colors.

Run with: python3 apps/web/scripts/generate_brand_assets.py
Regenerate whenever the mark or brand colors in styles.css change.
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

NAVY = (10, 31, 51, 255)
CREAM = (251, 249, 251, 255)
ORANGE = (217, 120, 66, 255)
TEAL = (65, 116, 126, 255)

OUT = Path(__file__).resolve().parent.parent / "public"
OUT.mkdir(parents=True, exist_ok=True)


def rounded_square(size: int, radius_ratio: float = 0.22) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * radius_ratio), fill=NAVY)
    return image


def draw_mark(image: Image.Image, cx: float, cy: float, scale: float) -> None:
    """A magnifying glass (the 'lens') over a rising equity curve (the 'alpha')."""
    draw = ImageDraw.Draw(image)
    lens_radius = 0.30 * scale
    ring_width = max(2, round(0.052 * scale))

    # Equity curve, clipped to the lens interior via a separate layer + mask.
    curve_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    curve_draw = ImageDraw.Draw(curve_layer)
    points = [
        (cx - 0.20 * scale, cy + 0.12 * scale),
        (cx - 0.06 * scale, cy - 0.02 * scale),
        (cx + 0.06 * scale, cy + 0.05 * scale),
        (cx + 0.20 * scale, cy - 0.16 * scale),
    ]
    curve_draw.line(points, fill=ORANGE, width=max(3, round(0.052 * scale)), joint="curve")
    dot_r = max(2, round(0.045 * scale))
    curve_draw.ellipse(
        [points[-1][0] - dot_r, points[-1][1] - dot_r, points[-1][0] + dot_r, points[-1][1] + dot_r],
        fill=ORANGE,
    )
    mask = Image.new("L", image.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    inner_r = lens_radius - ring_width * 0.5
    mask_draw.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r], fill=255)
    image.paste(curve_layer, (0, 0), Image.composite(curve_layer, Image.new("RGBA", image.size, (0, 0, 0, 0)), mask))

    # Lens ring.
    draw.ellipse(
        [cx - lens_radius, cy - lens_radius, cx + lens_radius, cy + lens_radius],
        outline=CREAM, width=ring_width,
    )

    # Handle.
    angle = math.radians(45)
    handle_len = 0.34 * scale
    start_r = lens_radius + ring_width * 0.3
    x0, y0 = cx + start_r * math.cos(angle), cy + start_r * math.sin(angle)
    x1, y1 = cx + (start_r + handle_len) * math.cos(angle), cy + (start_r + handle_len) * math.sin(angle)
    draw.line([(x0, y0), (x1, y1)], fill=CREAM, width=ring_width + max(1, round(0.012 * scale)))
    cap_r = (ring_width + max(1, round(0.012 * scale))) / 2
    for px, py in ((x0, y0), (x1, y1)):
        draw.ellipse([px - cap_r, py - cap_r, px + cap_r, py + cap_r], fill=CREAM)


def make_icon(size: int) -> Image.Image:
    image = rounded_square(size)
    draw_mark(image, cx=size * 0.44, cy=size * 0.44, scale=size)
    return image


def save_png(image: Image.Image, name: str, size: int | None = None) -> None:
    out = image if size is None else image.resize((size, size), Image.LANCZOS)
    out.save(OUT / name)
    print(f"wrote {OUT / name} ({out.size[0]}x{out.size[1]})")


def make_og_image() -> Image.Image:
    width, height = 1200, 630
    image = Image.new("RGBA", (width, height), NAVY)
    icon_size = 340
    icon = make_icon(icon_size)
    image.alpha_composite(icon, (86, (height - icon_size) // 2))

    draw = ImageDraw.Draw(image)
    text_x = 86 + icon_size + 56
    # Apple SD Gothic Neo covers Hangul + Latin from a single collection, so the
    # Korean tagline renders correctly instead of falling back to tofu boxes.
    korean_capable_font = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
    try:
        title_font = ImageFont.truetype(korean_capable_font, 84, index=6)  # Bold
        subtitle_font = ImageFont.truetype(korean_capable_font, 36, index=4)  # SemiBold
        tagline_font = ImageFont.truetype(korean_capable_font, 32, index=0)  # Regular
    except OSError:
        title_font = subtitle_font = tagline_font = ImageFont.load_default()

    draw.text((text_x, 220), "AlphaLens", font=title_font, fill=CREAM)
    draw.text((text_x, 336), "Strategy Desk", font=subtitle_font, fill=ORANGE)
    draw.text(
        (text_x, 400),
        "AI가 해석한 전략을, 검증된 엔진으로 백테스트.",
        font=tagline_font, fill=(198, 205, 214, 255),
    )
    return image


def main() -> None:
    # Favicons (multi-context: browser tab, bookmarks, PWA/home-screen).
    save_png(make_icon(512), "icon-512.png")
    save_png(make_icon(512), "favicon-32x32.png", 32)
    save_png(make_icon(512), "favicon-16x16.png", 16)
    save_png(make_icon(512), "apple-touch-icon.png", 180)
    make_icon(512).save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"wrote {OUT / 'favicon.ico'}")

    # Open Graph / social share preview.
    make_og_image().convert("RGB").save(OUT / "og-image.png", quality=92)
    print(f"wrote {OUT / 'og-image.png'} (1200x630)")


if __name__ == "__main__":
    main()
