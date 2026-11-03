#!/usr/bin/env python3
"""Script to extract and render Gambar 4 (PDC Dual-Layer Sequence Diagram) to PNG and JPG."""
import os
import base64
import urllib.request
from PIL import Image

OUT_DIRS = [
    "/www/wwwroot/riset-blockchain-pdc/figures",
    "/root/.gemini/antigravity-cli/brain/4365535c-86e9-4982-99cb-ba3281252ff9/figures"
]
for d in OUT_DIRS:
    os.makedirs(d, exist_ok=True)

# Read mermaid block from markdown
MD_PATH = "/www/wwwroot/riset-blockchain-pdc/HASIL_EKSPERIMEN_PDC_TM2_AGENTIC_AI.md"
with open(MD_PATH, "r", encoding="utf-8") as f:
    content = f.read()

marker = "sequenceDiagram"
start = content.find(marker)
if start == -1:
    raise ValueError("sequenceDiagram not found in markdown!")
fence_end = content.find("```", start)
diagram = content[start:fence_end].strip()

print(f"Extracted mermaid diagram ({len(diagram)} chars):\n{diagram}\n")

# Prepare mermaid.ink URL
encoded = base64.urlsafe_b64encode(diagram.encode("utf-8")).decode("ascii")
url = f"https://mermaid.ink/img/{encoded}?type=png"

print(f"Fetching from: {url[:60]}...")
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

png_temp = "/tmp/fig4_raw.png"
with urllib.request.urlopen(req, timeout=20) as resp:
    data = resp.read()
    with open(png_temp, "wb") as f:
        f.write(data)

print(f"Raw PNG downloaded: {len(data)} bytes.")

# Open with Pillow to ensure high quality and produce both PNG and JPG
im = Image.open(png_temp)
print(f"Image dimensions: {im.size}, mode: {im.mode}")

# Create white background version for JPG (if RGBA)
if im.mode == "RGBA":
    bg = Image.new("RGB", im.size, (255, 255, 255))
    bg.paste(im, mask=im.split()[3]) # 3 is alpha channel
    rgb_im = bg
else:
    rgb_im = im.convert("RGB")

for d in OUT_DIRS:
    png_path = os.path.join(d, "fig4_tm2_pdc_dual_layer.png")
    jpg_path = os.path.join(d, "fig4_tm2_pdc_dual_layer.jpg")
    
    # Save PNG (original crispness)
    im.save(png_path, "PNG", optimize=True)
    # Save JPG (high quality 95)
    rgb_im.save(jpg_path, "JPEG", quality=95, optimize=True)
    
    print(f"Saved: {png_path} ({os.path.getsize(png_path)} bytes)")
    print(f"Saved: {jpg_path} ({os.path.getsize(jpg_path)} bytes)")

print("\nGambar 4 successfully extracted and rendered to PNG and JPG!")
