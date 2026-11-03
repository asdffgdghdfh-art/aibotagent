#!/usr/bin/env python3
"""Jarvis Agent V1.0.2: restore black/white bunny icon, crisp Home and
microphone glyphs, compact drawer, and three-line More button.
Applies after migrate_agent_v100.py and restore_jarvis_ui_v101.py.
RikkaHub Agent native tools and settings stay present, untouched.
"""
from pathlib import Path

BASE=Path("app/src/main")
home=BASE/"java/me/rerere/rikkahub/jarvis/JarvisAgentHomeActivity.kt"
s=home.read_text(encoding="utf-8")
def change(a,b,n):
    global s
    if s.count(a)!=1:
        raise SystemExit("V1.0.2 UI anchor "+n+": "+str(s.count(a)))
    s=s.replace(a,b,1)

# Render icons from drawable vectors, not Unicode glyphs that differ by ROM/font.
imports=[
    "import androidx.compose.ui.res.painterResource",
    "import androidx.compose.material3.Icon",
    "import androidx.compose.ui.graphics.Brush",
    "import androidx.compose.foundation.border"
]
for imp in imports:
    if imp not in s:
        s=s.replace("import android.content.Intent",imp+"\nimport android.content.Intent",1)

change('''                    ) { Text("☷", color = ink, fontSize = 24.sp) }''',
'''                    ) {
                        Icon(painter = painterResource(R.drawable.jarvis_home_icon),
                            contentDescription = "聊天", tint = ink,
                            modifier = Modifier.size(26.dp))
                    }''',"bottom left house")

change('''                    ) { Text("⊞", color = ink, fontSize = 26.sp) }''',
'''                    ) {
                        Icon(painter = painterResource(R.drawable.jarvis_menu_icon),
                            contentDescription = "更多", tint = ink,
                            modifier = Modifier.size(27.dp))
                    }''',"three horizontal lines")

change('''                Box(
                    Modifier.size(84.dp).clip(CircleShape).background(green)
                        .clickable(onClick = { openChat() }),
                    contentAlignment = Alignment.Center
                ) { Text("🎙", fontSize = 31.sp, color = if (night) bg else Color.White) }''',
'''                Box(
                    Modifier.size(92.dp).clip(CircleShape)
                        .background(green.copy(alpha = 0.15f))
                        .border(1.dp, green.copy(alpha = 0.34f), CircleShape)
                        .padding(7.dp).clip(CircleShape)
                        .background(
                            Brush.radialGradient(
                                listOf(
                                    if (night) Color(0xFF45644D) else Color(0xFF8AA68E),
                                    if (night) Color(0xFF24392D) else Color(0xFF5E8264)
                                )
                            ), CircleShape
                        )
                        .border(1.5.dp, green.copy(alpha = 0.90f), CircleShape)
                        .clickable(onClick = { openChat() }),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(painter = painterResource(R.drawable.jarvis_microphone_icon),
                        contentDescription = "打开语音对话", tint = Color.White,
                        modifier = Modifier.size(35.dp))
                }''',"modern microphone")

# Remove duplicate Agent features from the Jarvis drawer, without deleting
# their implementations, permissions or navigation in the native Agent UI.
a=s.index('''                Text("功能中心", color = muted''')
b=s.index('''                JarvisMenuLine("语音对话（Agent 聊天页）"''',a)
s=s[:a]+'''                Text("设置", color = muted, fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(12.dp))
'''+s[b:]
a=s.index('''                JarvisMenuLine("语音对话（Agent 聊天页）"''')
b=s.index('''            }
        }
    }
''',a)
s=s[:a]+'''                JarvisMenuLine("进入 RikkaHub Agent（聊天与设置）",
                    "⚙", ink, subtle) {
                    menuOpen = false
                    openChat()
                }
                Spacer(Modifier.height(12.dp))
                Text("手机操作、图片识别与 MCP 等功能在 Agent 原生页面管理。",
                    color = muted, fontSize = 11.sp, lineHeight = 18.sp)
'''+s[b:]

# Previous UI footer, unchanged navigation/voice backend semantics.
change('Text("贾维斯 Agent 1.0.1 · 经典界面",','Text("贾维斯 Agent 1.0.2 · 精简界面",',"UI version")
assert 'JarvisFeatureTile("▣"' not in s
assert 'Text("🎙"' not in s
assert 'Text("⊞"' not in s
assert 'Text("☷"' not in s
assert "settingsStore.settingsFlow" in s
home.write_text(s,encoding="utf-8")

# Restore actual pictographic home button in Agent chat header.
chat=BASE/"java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt"
c=chat.read_text(encoding="utf-8")
marker='Text("主页", fontSize = 12.sp)'
if c.count(marker)!=1:
    raise SystemExit("Agent home button text changed: "+str(c.count(marker)))
c=c.replace(marker,
'''Icon(
                    painter = painterResource(me.rerere.rikkahub.R.drawable.jarvis_home_icon),
                    contentDescription = "返回贾维斯主页",
                    modifier = Modifier.size(23.dp)
                )''',1)
if "import androidx.compose.ui.res.painterResource" not in c:
    c=c.replace("import android.net.Uri",
                "import androidx.compose.ui.res.painterResource\nimport android.net.Uri",1)
if "import androidx.compose.foundation.layout.size" not in c:
    c=c.replace("import android.net.Uri",
                "import androidx.compose.foundation.layout.size\nimport android.net.Uri",1)
chat.write_text(c,encoding="utf-8")

draw=BASE/"res/drawable"
draw.mkdir(parents=True,exist_ok=True)
def write_vector(name, paths, size="24"):
    head=('<?xml version="1.0" encoding="utf-8"?>\n'
          '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
          f'    android:width="{size}dp" android:height="{size}dp"\n'
          '    android:viewportWidth="24" android:viewportHeight="24">\n')
    (draw/(name+".xml")).write_text(head+paths+'</vector>\n',encoding="utf-8")

write_vector("jarvis_home_icon",'''    <path android:fillColor="#00000000" android:strokeColor="#FFFFFFFF"
        android:strokeWidth="1.9" android:strokeLineCap="round"
        android:strokeLineJoin="round"
        android:pathData="M3,10.5 L12,3 L21,10.5 L21,20 C21,20.6 20.6,21 20,21 L4,21 C3.4,21 3,20.6 3,20 Z M9,21 L9,14 L15,14 L15,21"/>
''')
write_vector("jarvis_menu_icon",'''    <path android:fillColor="#00000000" android:strokeColor="#FFFFFFFF"
        android:strokeWidth="2" android:strokeLineCap="round"
        android:pathData="M4,6 L20,6 M4,12 L20,12 M4,18 L20,18"/>
''')
write_vector("jarvis_microphone_icon",'''    <path android:fillColor="#00000000" android:strokeColor="#FFFFFFFF"
        android:strokeWidth="1.65" android:strokeLineCap="round"
        android:strokeLineJoin="round"
        android:pathData="M12,15 C13.66,15 15,13.66 15,12 L15,5 C15,3.34 13.66,2 12,2 C10.34,2 9,3.34 9,5 L9,12 C9,13.66 10.34,15 12,15 Z M5,10.5 L5,12 C5,15.87 8.13,19 12,19 C15.87,19 19,15.87 19,12 L19,10.5 M12,19 L12,22 M8,22 L16,22"/>
''')

# White rabbit/bunny mark following the original Jarvis launcher icon.
# Contours were redrawn as scalable paths so the Android adaptive launcher
# renders it sharply on Samsung One UI (and no third-party DEV overlay remains).
fg=draw/"jarvis_launcher_foreground.xml"
fg.write_text('''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp" android:height="108dp"
    android:viewportWidth="108" android:viewportHeight="108">
    <path android:fillColor="#FFF8F8F8"
        android:pathData="M52.6,17.2 L49.3,17.5 L55.3,42.0 L50.3,43.6 L44.3,46.8 L32.2,24.2 L30.9,24.7 L28.4,26.3 L24.6,29.9 L22.3,33.7 L21.7,35.9 L21.7,37.5 L22.4,39.5 L24.7,43.5 L33.7,57.3 L32.2,59.7 L30.6,63.3 L29.7,66.7 L29.5,69.0 L29.5,72.3 L30.0,75.0 L30.9,77.7 L32.2,80.4 L33.9,83.0 L36.0,85.3 L38.6,87.2 L40.7,88.4 L43.3,89.4 L46.2,90.2 L50.0,90.7 L53.2,90.7 L59.9,90.1 L66.7,88.4 L72.9,85.8 L77.5,82.6 L81.3,78.7 L84.1,74.0 L85.6,69.4 L86.2,65.8 L86.2,63.0 L85.8,59.1 L84.7,54.7 L83.2,51.2 L80.9,47.7 L78.9,45.6 L76.7,44.1 L73.5,42.7 L69.6,41.6 L66.2,26.8 L65.0,22.5 L64.1,20.8 L62.1,19.2 L59.9,18.2 L56.7,17.5 Z"/>
    <path android:fillColor="#FF101115"
        android:pathData="M48.3,65.8 L49.4,65.5 L50.8,65.6 L51.9,66.2 L52.6,66.9 L55.7,74.3 L56.4,76.3 L56.4,78.1 L55.6,79.9 L54.1,81.1 L52.6,81.5 L51.7,81.4 L50.0,80.6 L48.7,78.6 L46.8,73.7 L45.7,70.5 L45.7,68.9 L46.6,67.1 Z"/>
    <path android:fillColor="#FF101115"
        android:pathData="M66.3,57.9 L67.2,57.7 L68.8,57.8 L70.4,59.0 L71.2,60.5 L74.0,67.4 L74.3,68.7 L74.3,70.3 L73.5,72.1 L72.0,73.3 L70.6,73.6 L69.6,73.4 L68.6,73.0 L67.6,72.0 L64.1,63.8 L63.7,62.0 L63.9,60.4 L65.0,58.6 Z"/>
</vector>
''',encoding="utf-8")
adaptive=BASE/"res/mipmap-anydpi-v26/ic_launcher.xml"
if not adaptive.exists(): raise SystemExit("Missing adaptive icon XML")
adaptive.write_text('''<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@android:color/black"/>
    <foreground android:drawable="@drawable/jarvis_launcher_foreground"/>
    <monochrome android:drawable="@drawable/jarvis_launcher_foreground"/>
</adaptive-icon>
''',encoding="utf-8")

# Use a new side-by-side package for safe user testing, rather than upgrading
# the per-build debug signature and unexpectedly erasing Agent user data.
gpath=Path("app/build.gradle.kts")
g=gpath.read_text(encoding="utf-8")
if 'applicationId = "com.jarvis.agent.preview"' not in g:
    raise SystemExit("Expected previous V1.0.x app ID")
g=g.replace('applicationId = "com.jarvis.agent.preview"',
            'applicationId = "com.jarvis.agent.ui102"',1)
g=g.replace('versionCode = 1000','versionCode = 1002',1)
g=g.replace('versionName = "1.0.0-agent-preview"',
            'versionName = "1.0.2-classic-ui"',1)
gpath.write_text(g,encoding="utf-8")
print("Jarvis Agent V1.0.2: original style launcher icon, vector house and mic, simplified drawer, triple-bar more, new side-by-side package")
