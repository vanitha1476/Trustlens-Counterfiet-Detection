import os
from pathlib import Path
from PIL import Image, ImageDraw

def create_icon(size: int, output_path: Path):
    # Create an RGBA image with a transparent background
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Outer circle: modern vibrant cyan-indigo gradient look
    padding = max(1, size // 16)
    # Background circle
    draw.ellipse(
        [padding, padding, size - padding, size - padding],
        fill=(14, 165, 233, 255) # Modern electric cyan/blue
    )
    
    # Inner lens ring
    ring_pad = max(2, size // 5)
    draw.ellipse(
        [ring_pad, ring_pad, size - ring_pad, size - ring_pad],
        outline=(255, 255, 255, 255),
        width=max(1, size // 12)
    )
    
    # Trust shield / checkmark or target center
    center = size // 2
    r = max(2, size // 8)
    draw.ellipse(
        [center - r, center - r, center + r, center + r],
        fill=(255, 255, 255, 255)
    )
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    print(f"Generated {output_path} ({size}x{size})")

if __name__ == "__main__":
    icon_dir = Path(__file__).resolve().parent.parent / "extension" / "icons"
    for s in [16, 48, 128]:
        create_icon(s, icon_dir / f"icon{s}.png")
