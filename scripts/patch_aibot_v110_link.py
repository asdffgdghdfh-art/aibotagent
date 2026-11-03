#!/usr/bin/env python3
"""Apply Aibot Link V1.1 native entry after patch_aibot_v105.py.

Expects aibot_link/android/AibotLinkActivity.kt from the standalone Aibot Link
source package to be present alongside the existing Android patch scripts.
"""
from pathlib import Path

root = Path("app/src/main")
package = root / "java/me/rerere/rikkahub/jarvis"
home = package / "JarvisAgentHomeActivity.kt"
manifest = root / "AndroidManifest.xml"
gradle = Path("app/build.gradle.kts")
source = Path("../aibot_link/android/AibotLinkActivity.kt")
if not source.is_file():
    raise SystemExit("Missing standalone AibotLinkActivity.kt (see docs/aibot-link-v110-architecture.md)")
activity = package / "AibotLinkActivity.kt"
if activity.exists():
    raise SystemExit("AibotLinkActivity already exists; refusing to apply twice")

s = home.read_text(encoding="utf-8")
anchor = '''                JarvisMenuLine("进入 RikkaHub Agent（聊天与设置）",
                    "⚙", ink, subtle) {
                    menuOpen = false
                    openChat()
                }
'''
assert s.count(anchor) == 1, ("drawer anchor changed", s.count(anchor))
replacement = anchor + '''                Spacer(Modifier.height(7.dp))
                JarvisMenuLine("我的设备 · Aibot Link", "⌘", ink, subtle) {
                    menuOpen = false
                    startActivity(Intent(this@JarvisAgentHomeActivity, AibotLinkActivity::class.java))
                }
'''
home.write_text(s.replace(anchor,replacement,1),encoding="utf-8")

m = manifest.read_text(encoding="utf-8")
anchor = '''    <activity android:name=".jarvis.JarvisAgentHomeActivity"'''
assert m.count(anchor) == 1
m = m.replace(anchor,'''    <activity
      android:name=".jarvis.AibotLinkActivity"
      android:exported="false"
      android:theme="@style/Theme.Rikkahub" />
''' + anchor,1)
manifest.write_text(m,encoding="utf-8")

g = gradle.read_text(encoding="utf-8")
assert g.count("versionCode = 1005") == 1
assert g.count('versionName = "1.0.5-aibot"') == 1
g = g.replace("versionCode = 1005","versionCode = 1100",1)
g = g.replace('versionName = "1.0.5-aibot"','versionName = "1.1.0-aibot-link"',1)
assert 'applicationId = "com.jarvis.agent.v104preview"' in g or 'applicationId = "com.jarvis.agent"' in g
assert 'signingConfig = signingConfigs.getByName("release")' in g
gradle.write_text(g,encoding="utf-8")

activity.write_bytes(source.read_bytes())
print("Aibot V1.1: My Devices entry, secure HTTPS WebView, version 1100; package/signature unchanged")
