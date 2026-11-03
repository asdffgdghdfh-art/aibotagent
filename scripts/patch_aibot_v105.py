#!/usr/bin/env python3
"""Aibot V1.0.5 branding update: keep package/signing identity, restore bunny icon."""
from pathlib import Path
import re
import io
import xml.etree.ElementTree as ET
from PIL import Image
import cairosvg

app = Path("app")
src = app / "src/main"
res = src / "res"
gradle = app / "build.gradle.kts"
s = gradle.read_text(encoding="utf-8")
if s.count("versionCode = 1004") != 1:
    raise RuntimeError("Expected versionCode 1004 exactly once")
s = s.replace("versionCode = 1004", "versionCode = 1005", 1)
for old in ('versionName = "1.0.4-inline-voice-preview"', 'versionName = "1.0.4-inline-voice"'):
    if old in s:
        s = s.replace(old, 'versionName = "1.0.5-aibot"', 1)
        break
else:
    raise RuntimeError("Expected V1.0.4 versionName")
if 'applicationId = "com.jarvis.agent"' not in s and 'applicationId = "com.jarvis.agent.v104preview"' not in s:
    raise RuntimeError("Unexpected package: refusing to change the signing identity")
gradle.write_text(s, encoding="utf-8")

labels = 0
for file in res.glob("values*/strings.xml"):
    raw = file.read_text(encoding="utf-8")
    updated, count = re.subn(r'(<string name="app_name">)[^<]*(</string>)', r'\g<1>Aibot\g<2>', raw)
    if count:
        file.write_text(updated, encoding="utf-8")
        labels += count
if labels < 1:
    raise RuntimeError("No app_name string resources found")

home = src / "java/me/rerere/rikkahub/jarvis/JarvisAgentHomeActivity.kt"
text = home.read_text(encoding="utf-8")
old = '贾维斯 Agent 1.0.4 · 原生语音版'
if text.count(old) != 1:
    raise RuntimeError("Home version subtitle mismatch")
text = text.replace(old, 'Aibot 1.0.5 · 原生语音版', 1)
old2 = 'Text("贾维斯", color = ink, fontSize = 25.sp,'
if text.count(old2) != 1:
    raise RuntimeError("Home brand title mismatch")
text = text.replace(old2, 'Text("Aibot", color = ink, fontSize = 25.sp,', 1)
home.write_text(text, encoding="utf-8")

# Use the original black-background, white-bunny vector already preserved
# in V1.0.2, but expose it under a new resource ID so Samsung One UI refreshes
# the actual launcher icon instead of continuing to show an old cached bitmap.
original = res / "drawable/jarvis_launcher_foreground.xml"
foreground = res / "drawable/aibot_launcher_foreground.xml"
foreground.write_bytes(original.read_bytes())
adaptive = res / "mipmap-anydpi-v26/aibot_launcher.xml"
adaptive.write_text('''<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@android:color/black"/>
    <foreground android:drawable="@drawable/aibot_launcher_foreground"/>
    <monochrome android:drawable="@drawable/aibot_launcher_foreground"/>
</adaptive-icon>
''', encoding="utf-8")

manifest = src / "AndroidManifest.xml"
m = manifest.read_text(encoding="utf-8")
if m.count('android:icon="@mipmap/ic_launcher"') != 1:
    raise RuntimeError("Unexpected launcher resource in manifest")
m = m.replace('android:icon="@mipmap/ic_launcher"', 'android:icon="@mipmap/aibot_launcher"', 1)
manifest.write_text(m, encoding="utf-8")

ns = "{http://schemas.android.com/apk/res/android}"
paths = []
for path in ET.parse(original).getroot().findall("path"):
    paths.append((path.attrib[ns + "pathData"], path.attrib[ns + "fillColor"]))
if len(paths) < 3:
    raise RuntimeError("Bunny icon paths missing")
svgpaths = []
for i, (d, fill) in enumerate(paths):
    if i == 0: fill = "url(#bunny)"
    svgpaths.append(f'<path d="{d}" fill="{fill}"/>')
body = "".join(svgpaths)
base = '''<defs><linearGradient id="bunny" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#D5D5D9"/><stop offset=".52" stop-color="#F8F8F8"/>
<stop offset="1" stop-color="#D0D0D4"/></linearGradient></defs>'''
def render(size, legacy=False):
    if legacy:
        shape = '<rect x="0" y="0" width="108" height="108" rx="25" fill="#131418"/>'
        shape += '<g transform="translate(-22 -22) scale(1.41)">' + body + '</g>'
    else:
        shape = body
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108" width="108" height="108">{base}{shape}</svg>'
    raster = cairosvg.svg2png(bytestring=svg.encode(),output_width=size*3,output_height=size*3)
    return Image.open(io.BytesIO(raster)).convert("RGBA").resize((size,size),Image.Resampling.LANCZOS)

sizes = {"mdpi":48,"hdpi":72,"xhdpi":96,"xxhdpi":144,"xxxhdpi":192}
for density, size in sizes.items():
    folder = res / ("mipmap-" + density)
    folder.mkdir(exist_ok=True)
    render(size, True).save(folder / "aibot_launcher.png", optimize=True)

print(f"Aibot V1.0.5 prepared: labels={labels}, launcher density PNGs={len(sizes)}, " +
      "package/signing unchanged; manifest launcher resource is @mipmap/aibot_launcher")
