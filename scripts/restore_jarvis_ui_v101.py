#!/usr/bin/env python3
"""Restore the full V0.9.1 Jarvis UI on top of RikkaHub Agent v2.5.1.

Use the exact old UI source to preserve the visual design, adapting callbacks
to real Agent destinations instead of advertising not-yet-migrated services.
Apply AFTER migrate_agent_v100.py; never affect the v0.9.2 stable app.
"""
from pathlib import Path
import re

root=Path("app/src/main/java/me/rerere/rikkahub/jarvis")
target=root/"JarvisAgentHomeActivity.kt"
old=Path("../scripts/patch_jarvis_v090.py").read_text(encoding="utf-8")
kot=target.read_text(encoding="utf-8")
def section(key):
    start=old.index(key+" = r'''")+len(key+" = r'''")
    stop=old.index("'''",start)
    return old[start:stop]
body=section("body")
helpers=section("helpers")

def replace_once(s,a,b,label):
    count=s.count(a)
    if count!=1: raise RuntimeError(f"restore original Jarvis UI {label}: {count} anchors")
    return s.replace(a,b,1)

body=replace_once(body,
'''    val systemDark = isSystemInDarkTheme()
    var night by remember { mutableStateOf(defaults.getBoolean("night", systemDark)) }''',
'''    val systemDark = isSystemInDarkTheme()
    var night by remember { mutableStateOf(defaults.getBoolean("night", systemDark)) }
    val agentSettings by settingsStore.settingsFlow.collectAsStateWithLifecycle()
    val activeName = agentSettings.getCurrentAssistant().name.ifBlank { "默认助手" }
    val lastTurn = JarvisSession.latestTurn
    var poseIndex by remember { mutableIntStateOf(0) }
    LaunchedEffect(lastTurn) {
        if (lastTurn.isNotBlank()) {
            poseIndex = 3 // TALK pose briefly after a completed reply
            kotlinx.coroutines.delay(1300)
            poseIndex = 0
        }
    }''',"settings and avatar state")
body=replace_once(body,
'''    val activeName = currentAssistant.name.ifBlank { "默认助手" }''',
'''    // Assistant label comes from Agent's native model settings.''',"old assistant")
body=replace_once(body,
'''    val currentDialog = if ((mood == RobotMood.LISTENING || mood == RobotMood.THINKING)
                        && transcript.isNotBlank()) transcript
                        else feedText.ifBlank { transcript }
    val displayDialog = currentDialog.replace("小六：", "贾维斯：")
        .replace("小六:", "贾维斯:")''',
'''    val displayDialog = lastTurn''',"recent turn")
body=replace_once(body,
'''                    Text("贾维斯", color = ink, fontSize = 24.sp,
                        fontWeight = FontWeight.Bold)
                    Text("当前智能体 · " + activeName, color = muted,
                        fontSize = 11.sp, maxLines = 1,
                        overflow = TextOverflow.Ellipsis)
                }
                Box(
                    Modifier.clip(RoundedCornerShape(22.dp))
                        .background(surface).clickable { menuOpen = true }
                        .padding(horizontal = 12.dp, vertical = 10.dp)
                ) {
                    Text(if (wakeActive) "● 语音待命" else "◌ 语音关闭",
                        color = if (wakeActive) green else muted, fontSize = 11.sp)
                }''',
'''                    Text(activeName, color = ink, fontSize = 24.sp,
                        fontWeight = FontWeight.Bold, maxLines = 1,
                        overflow = TextOverflow.Ellipsis)
                    Text("当前智能体 · 你的 AI 助手", color = muted,
                        fontSize = 11.sp, maxLines = 1,
                        overflow = TextOverflow.Ellipsis)
                }''',"v091 dynamic header")
body=replace_once(body,'''Text("你好，我是贾维斯",''',
                    '''Text("你好，我是$activeName",''',"v091 dynamic greeting")
body=replace_once(body,
'''                    XiaoLiuAnimatedMascot(
                        mood = mood,
                        speaking = speechStatus == "正在播报回复",
                        modifier = Modifier.fillMaxSize()
                    )''',
'''                    JarvisClassicMascot(
                        poseIndex = poseIndex,
                        modifier = Modifier.fillMaxSize().clickable { poseIndex = 1 }
                    )''',"six pose chibi")
body=body.replace("onChat", "openChat()").replace("onVoice", "openChat()")
# Compose clickable(onClick = ...) takes a lambda, not the result of openChat().
body=body.replace(".clickable(onClick = openChat())", ".clickable(onClick = { openChat() })")
body=replace_once(body,'''                if (wakeActive) wakeLabel else "轻触麦克风对话 · 更多功能在左上角",''',
                  '''                "语音、拍照和手机操作通过 Agent 聊天页开启",''',"voice caveat")
body=replace_once(body,'''Text("贾维斯 0.9.0",''','''Text("贾维斯 Agent 1.0.1 · 经典界面",''',"version")
body=replace_once(body,'''            Text("智能助手控制中心",''',
                    '''            Text("智能助手控制中心 · RikkaHub Agent",''',"drawer tagline")

# Keep classic smart-assistant section appearance without referencing the
# previous backend's Assistant/UIAvatar classes or old save logic.
a=body.index("                assistants.forEach { assistant ->")
b=body.index("                Spacer(Modifier.height(20.dp))",a)
body=body[:a]+'''                JarvisMenuLine("当前智能体 · " + activeName,
                    "◉", ink, subtle) {
                    menuOpen = false
                    openChat()
                }
                Spacer(Modifier.height(7.dp))
                JarvisMenuLine("切换智能体 / 历史会话", "☷", ink, subtle) {
                    menuOpen = false
                    openChat()
                }
'''+body[b:]

# Four classic large grid tiles are restored. Their actions intentionally
# forward into Agent's existing chat/tool permission UI until deep links
# for each native Agent tool have been verified.
for action in ["onScreen()", "onVision()", "onCamera()", "onFeatureCenter()"]:
    body=body.replace(action,"openChat()")
body=replace_once(body,
'''                    menuOpen = false
                        openChat()
                    }.padding(vertical = 9.dp))''',
'''                    menuOpen = false
                        openChat()
                    }.padding(vertical = 9.dp))''',"full feature link")

# These three wakeup/background/TTS toggles belonged to the old RikkaHub
# service. Do not display fake controls or silently grant permissions.
a=body.index('''                JarvisMenuLine(if (wakeActive)''')
b=body.index('''            }
        }
    }
''',a)
body=body[:a]+'''                JarvisMenuLine("语音对话（Agent 聊天页）",
                    "♫", ink, subtle) {
                    menuOpen = false
                    openChat()
                }
                Spacer(Modifier.height(7.dp))
                JarvisMenuLine("手机操作与工具权限", "⚙", ink, subtle) {
                    menuOpen = false
                    openChat()
                }
                Spacer(Modifier.height(7.dp))
                JarvisMenuLine("Agent 应用设置", "↗", ink, subtle) {
                    menuOpen = false
                    openChat()
                }
                Spacer(Modifier.height(13.dp))
                Text("离线唤醒与连续摄像头功能仍在移植，暂未开放。",
                    color = muted, fontSize = 11.sp, lineHeight = 18.sp)
'''+body[b:]

# Portrait & landscape both scroll, including under system navigation bars.
body=body.replace('''        (context as? Activity)?.window?.let { w ->
            w.navigationBarColor = bg.toArgb()
            WindowCompat.getInsetsController(w, w.decorView)
                .isAppearanceLightNavigationBars = !night
        }''',
'''        (context as? Activity)?.window?.let { w ->
            @Suppress("DEPRECATION")
            w.navigationBarColor = bg.toArgb()
            @Suppress("DEPRECATION")
            w.statusBarColor = bg.toArgb()
            WindowCompat.getInsetsController(w, w.decorView).apply {
                isAppearanceLightNavigationBars = !night
                isAppearanceLightStatusBars = !night
            }
        }''')

# Current V1.0 generated source already contains real Agent chat integration.
start=kot.index('    @Composable\n    private fun Home() {')
end=kot.index('\n}\n\n@Composable\nprivate fun MenuEntry(',start)
new_class='''    @Composable
    private fun Home() {
'''+body+'''
    }
'''
# Previous original block contains the final function closing brace already
# in its extracted caller; 'body' itself has only content, so this is correct.
kot=kot[:start]+new_class+kot[end:]
kot=kot[:kot.index('@Composable\nprivate fun MenuEntry(')]+helpers
required_imports=[
    "import android.app.Activity",
    "import androidx.compose.foundation.isSystemInDarkTheme",
    "import androidx.compose.foundation.layout.BoxWithConstraints",
    "import androidx.compose.foundation.layout.navigationBarsPadding",
    "import androidx.compose.runtime.SideEffect",
    "import androidx.compose.runtime.mutableIntStateOf",
    "import androidx.compose.ui.platform.LocalConfiguration",
    "import androidx.compose.ui.platform.LocalContext",
    "import androidx.compose.ui.graphics.toArgb",
    "import androidx.core.view.WindowCompat",
]
for imp in required_imports:
    if imp not in kot: kot=kot.replace("import android.content.Intent",imp+"\nimport android.content.Intent",1)
# No hidden callback in the classic drawer may reference the unmigrated robot service.
for missing in ["onScreen()", "onVision()", "onCamera()","onWakeToggle()", "onVoiceReplyToggle()", "backgroundMode","wakeActive", "RobotMood", "XiaoLiuAnimatedMascot"]:
    assert missing not in kot, f"Old unadapted service reference: {missing}"
assert kot.count("private fun Home()")==1
assert "JarvisFeatureTile" in kot and "JarvisMenuLine" in kot
target.write_text(kot,encoding="utf-8")

# Bring back the actual original six-pose mascot animation instead of a static
# preview cell. This is a UI animation only, not restored speech recognition.
original_mascot=Path("../mascot_v083/XiaoLiuAnimatedMascot.kt").read_text(encoding="utf-8")
original_mascot=original_mascot.replace(
    "package me.rerere.rikkahub.robot","package me.rerere.rikkahub.jarvis",1
).replace("XiaoLiuAnimatedMascot(", "JarvisClassicMascot(",1)
original_mascot=replace_once(original_mascot,
'''    mood: RobotMood,
    speaking: Boolean,''',
'''    poseIndex: Int,''',"mascot parameters")
a=original_mascot.index("    val pose = when {")
b=original_mascot.index("    val timeline =",a)
original_mascot=original_mascot[:a]+'''    val pose = MascotPose.entries.getOrElse(poseIndex) { MascotPose.IDLE }
'''+original_mascot[b:]
original_mascot=original_mascot.replace("R.drawable.xiaoliu_pose_atlas",
                                        "R.drawable.jarvis_mascot_atlas")
(root/"JarvisClassicMascot.kt").write_text(original_mascot,encoding="utf-8")
print("Restored classic Jarvis V0.9.1 UI on RikkaHub Agent: 2x2 feature grid, sidebar, six-pose mascot, themes")
