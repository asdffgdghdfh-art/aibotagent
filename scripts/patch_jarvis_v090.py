#!/usr/bin/env python3
"""Jarvis 0.9.0: clean light/dark home and unified drawer.
Applied after V0.8.5. Keeps original backend, chat and camera flows.
"""
from pathlib import Path

robot = Path("app/src/main/java/me/rerere/rikkahub/robot/RobotActivity.kt")
text = robot.read_text(encoding="utf-8")
anchor = "@Composable\nprivate fun RobotHome("
marker = "/** One source of truth:"
assert text.count(anchor) == 1, "RobotHome not uniquely located"
start = text.index(anchor)
end = text.index(marker, start)
signature_end = text.index(") {", start) + len(") {")
signature = text[start:signature_end]
required = ["feedText: String", "onScreen: () -> Unit", "onVision: () -> Unit",
            "onCamera: () -> Unit", "voiceRepliesOn: Boolean", "speechStatus: String"]
for key in required:
    if key not in signature:
        raise SystemExit("Missing existing RobotHome parameter " + key)

body = r'''
    val context = LocalContext.current
    val defaults = context.getSharedPreferences("jarvis_home_v090", android.content.Context.MODE_PRIVATE)
    val systemDark = isSystemInDarkTheme()
    var night by remember { mutableStateOf(defaults.getBoolean("night", systemDark)) }
    var menuOpen by remember { mutableStateOf(false) }
    val bg = if (night) Color(0xFF111114) else Color(0xFFF8F9F7)
    val surface = if (night) Color(0xFF202023) else Color.White
    val subtle = if (night) Color(0xFF29292C) else Color(0xFFF1F2F0)
    val ink = if (night) Color(0xFFF4F4F1) else Color(0xFF212321)
    val muted = if (night) Color(0xFFA7A8A5) else Color(0xFF747975)
    val green = if (night) Color(0xFFA8C7AC) else Color(0xFF547C5A)
    val hairline = if (night) Color(0xFF35363A) else Color(0xFFE6E9E5)
    val config = LocalConfiguration.current
    val landscape = config.screenWidthDp > config.screenHeightDp
    val activeName = currentAssistant.name.ifBlank { "默认助手" }
    SideEffect {
        (context as? Activity)?.window?.let { w ->
            w.navigationBarColor = bg.toArgb()
            WindowCompat.getInsetsController(w, w.decorView)
                .isAppearanceLightNavigationBars = !night
        }
    }
    val currentDialog = if ((mood == RobotMood.LISTENING || mood == RobotMood.THINKING)
                        && transcript.isNotBlank()) transcript
                        else feedText.ifBlank { transcript }
    val displayDialog = currentDialog.replace("小六：", "贾维斯：")
        .replace("小六:", "贾维斯:")
    Box(Modifier.fillMaxSize().background(bg)) {
        Column(
            modifier = Modifier.fillMaxSize().navigationBarsPadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 22.dp).padding(bottom = 28.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Spacer(Modifier.height(18.dp))
            Row(
                Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    Modifier.size(46.dp).clip(RoundedCornerShape(15.dp))
                        .background(surface).clickable { menuOpen = true },
                    contentAlignment = Alignment.Center
                ) { Text("☰", color = ink, fontSize = 25.sp) }
                Spacer(Modifier.width(14.dp))
                Column(Modifier.weight(1f)) {
                    Text("贾维斯", color = ink, fontSize = 24.sp,
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
                }
            }

            Spacer(Modifier.height(if (landscape) 12.dp else 28.dp))
            // The same six-state animated avatar is preserved, with clean neutral surroundings.
            BoxWithConstraints(
                Modifier.fillMaxWidth().height(if (landscape) 185.dp else
                    if (config.screenHeightDp < 740) 248.dp else 292.dp),
                contentAlignment = Alignment.Center
            ) {
                val figure = maxWidth.coerceAtMost(if (landscape) 185.dp else 300.dp)
                Box(Modifier.size(figure), contentAlignment = Alignment.Center) {
                    XiaoLiuAnimatedMascot(
                        mood = mood,
                        speaking = speechStatus == "正在播报回复",
                        modifier = Modifier.fillMaxSize()
                    )
                }
            }
            Spacer(Modifier.height(3.dp))
            if (displayDialog.isBlank()) {
                Text("你好，我是贾维斯", color = ink,
                    fontWeight = FontWeight.Bold, fontSize = 25.sp,
                    textAlign = TextAlign.Center)
                Spacer(Modifier.height(7.dp))
                Text("你的智能 AI 助手", color = muted, fontSize = 13.sp)
            } else {
                Text("随时为你提供帮助", color = muted, fontSize = 13.sp)
            }
            Spacer(Modifier.height(25.dp))

            Box(
                Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp))
                    .background(surface).clickable(onClick = onChat)
                    .padding(18.dp)
            ) {
                Column {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("◉  最近对话", color = ink, fontWeight = FontWeight.SemiBold,
                            fontSize = 15.sp, modifier = Modifier.weight(1f))
                        Text("查看全部  ›", color = muted, fontSize = 12.sp)
                    }
                    Spacer(Modifier.height(12.dp))
                    if (displayDialog.isBlank()) {
                        Text("开始和贾维斯聊天，最新一轮问答会显示在这里。",
                            color = muted, fontSize = 13.sp, lineHeight = 20.sp)
                    } else {
                        // Full most recent exchange; parent page scrolls for long responses.
                        Text(displayDialog, color = ink, fontSize = 13.sp,
                            lineHeight = 22.sp, softWrap = true)
                    }
                }
            }
            Spacer(Modifier.height(28.dp))

            Row(
                Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Box(
                        Modifier.size(54.dp).clip(CircleShape).background(surface)
                            .clickable(onClick = onChat),
                        contentAlignment = Alignment.Center
                    ) { Text("☷", color = ink, fontSize = 24.sp) }
                    Spacer(Modifier.height(6.dp))
                    Text("聊天", color = muted, fontSize = 12.sp)
                }
                Box(
                    Modifier.size(84.dp).clip(CircleShape).background(green)
                        .clickable(onClick = onVoice),
                    contentAlignment = Alignment.Center
                ) { Text("🎙", fontSize = 31.sp, color = if (night) bg else Color.White) }
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Box(
                        Modifier.size(54.dp).clip(CircleShape).background(surface)
                            .clickable { menuOpen = true },
                        contentAlignment = Alignment.Center
                    ) { Text("⊞", color = ink, fontSize = 26.sp) }
                    Spacer(Modifier.height(6.dp))
                    Text("更多", color = muted, fontSize = 12.sp)
                }
            }
            Spacer(Modifier.height(17.dp))
            Text(
                if (wakeActive) wakeLabel else "轻触麦克风对话 · 更多功能在左上角",
                color = muted, fontSize = 11.sp, maxLines = 2,
                textAlign = TextAlign.Center
            )
            Spacer(Modifier.height(8.dp))
            Text("贾维斯 0.9.0", color = muted.copy(alpha = 0.72f),
                fontSize = 10.sp)
        }

        if (menuOpen) {
            Box(
                Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.55f))
                    .clickable { menuOpen = false }
            )
            Column(
                Modifier.fillMaxHeight().fillMaxWidth(0.86f)
                    .clip(RoundedCornerShape(topEnd = 28.dp, bottomEnd = 28.dp))
                    .background(surface).navigationBarsPadding()
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 20.dp, vertical = 22.dp)
                    .align(Alignment.CenterStart)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("贾维斯", color = ink, fontSize = 25.sp,
                        fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                    Text("✕", color = muted, fontSize = 23.sp,
                        modifier = Modifier.clip(CircleShape).clickable { menuOpen = false }
                            .padding(9.dp))
                }
                Spacer(Modifier.height(5.dp))
                Text("智能助手控制中心", color = muted, fontSize = 12.sp)
                Spacer(Modifier.height(25.dp))
                Text("智能体", color = muted, fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(10.dp))
                assistants.forEach { assistant ->
                    val chosen = assistant.id == currentAssistant.id
                    Row(
                        Modifier.fillMaxWidth()
                            .clip(RoundedCornerShape(17.dp))
                            .background(if (chosen) subtle else surface)
                            .clickable {
                                onSelectAssistant(assistant)
                                menuOpen = false
                            }
                            .padding(10.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        UIAvatar(name = assistant.name.ifBlank { "智能体" },
                            value = assistant.avatar, modifier = Modifier.size(38.dp))
                        Spacer(Modifier.width(11.dp))
                        Column(Modifier.weight(1f)) {
                            Text(assistant.name.ifBlank { "默认助手" },
                                fontSize = 14.sp, color = ink, maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                                fontWeight = if (chosen) FontWeight.SemiBold else FontWeight.Normal)
                            Text(if (chosen) "当前选中" else "点击切换", fontSize = 11.sp,
                                color = muted)
                        }
                        Text(if (chosen) "✓" else "›", color = if (chosen) green else muted,
                            fontSize = 19.sp)
                    }
                }
                Spacer(Modifier.height(20.dp))
                Box(Modifier.fillMaxWidth().height(1.dp).background(hairline))
                Spacer(Modifier.height(18.dp))

                Text("外观", color = muted, fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(11.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    listOf("☼  白天", "☾  夜间").forEachIndexed { index, label ->
                        val selected = night == (index == 1)
                        Box(
                            Modifier.weight(1f).clip(RoundedCornerShape(14.dp))
                                .background(if (selected) green.copy(alpha = 0.19f) else subtle)
                                .clickable {
                                    night = index == 1
                                    defaults.edit().putBoolean("night", night).apply()
                                }
                                .padding(vertical = 13.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(label, color = if (selected) green else ink,
                                fontSize = 13.sp,
                                fontWeight = if (selected) FontWeight.SemiBold
                                    else FontWeight.Normal)
                        }
                    }
                }
                Spacer(Modifier.height(22.dp))
                Box(Modifier.fillMaxWidth().height(1.dp).background(hairline))
                Spacer(Modifier.height(18.dp))

                Text("功能中心", color = muted, fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    JarvisFeatureTile("▣", "屏幕理解", ink, subtle,
                        Modifier.weight(1f)) { menuOpen = false; onScreen() }
                    JarvisFeatureTile("▯", "操作手机", ink, subtle,
                        Modifier.weight(1f)) { menuOpen = false; onScreen() }
                }
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    JarvisFeatureTile("▹", "实时视觉", ink, subtle,
                        Modifier.weight(1f)) { menuOpen = false; onVision() }
                    JarvisFeatureTile("◎", "拍照识别", ink, subtle,
                        Modifier.weight(1f)) { menuOpen = false; onCamera() }
                }
                Spacer(Modifier.height(10.dp))
                Text("打开完整功能中心  ›", color = green, fontSize = 12.sp,
                    modifier = Modifier.clickable {
                        menuOpen = false
                        onFeatureCenter()
                    }.padding(vertical = 9.dp))
                Spacer(Modifier.height(14.dp))
                Box(Modifier.fillMaxWidth().height(1.dp).background(hairline))
                Spacer(Modifier.height(15.dp))

                Text("语音与设置", color = muted, fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(12.dp))
                JarvisMenuLine(if (wakeActive) "关闭贾维斯语音唤醒" else "开启贾维斯语音唤醒",
                    "◉", ink, subtle) { onWakeToggle() }
                Spacer(Modifier.height(7.dp))
                JarvisMenuLine(if (backgroundMode) "后台唤醒：开" else "后台唤醒：关",
                    "◷", ink, subtle) { onBackgroundToggle() }
                Spacer(Modifier.height(7.dp))
                JarvisMenuLine(if (voiceRepliesOn) "Agent 语音播报：开" else "Agent 语音播报：关",
                    "♫", ink, subtle) { onVoiceReplyToggle() }
                Spacer(Modifier.height(7.dp))
                JarvisMenuLine("应用设置", "⚙", ink, subtle) {
                    menuOpen = false
                    onSettings()
                }
                Spacer(Modifier.height(7.dp))
                JarvisMenuLine("检查更新", "↗", ink, subtle) {
                    menuOpen = false
                    onVersionInfo()
                }
            }
        }
    }
'''

helpers = r'''
@Composable
private fun JarvisFeatureTile(
    glyph: String, title: String, ink: Color, fill: Color,
    modifier: Modifier = Modifier, onClick: () -> Unit
) {
    Column(
        modifier.clip(RoundedCornerShape(17.dp))
            .background(fill).clickable(onClick = onClick)
            .padding(vertical = 16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(glyph, color = ink, fontSize = 27.sp)
        Spacer(Modifier.height(6.dp))
        Text(title, color = ink, fontSize = 12.sp)
    }
}

@Composable
private fun JarvisMenuLine(
    title: String, symbol: String, ink: Color, fill: Color,
    onClick: () -> Unit
) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(15.dp))
            .background(fill).clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 13.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(symbol, color = ink, fontSize = 17.sp)
        Spacer(Modifier.width(11.dp))
        Text(title, color = ink, fontSize = 13.sp,
            modifier = Modifier.weight(1f))
        Text("›", color = ink, fontSize = 16.sp)
    }
}
'''
text = text[:start] + signature + "\n" + body + "\n}\n" + helpers + "\n" + text[end:]
robot.write_text(text, encoding="utf-8")
print("Jarvis homepage replaced with responsive white/charcoal layout and unified drawer")

# New display name only; internal class identifiers/package stay stable for upgrades.
manifest = Path("app/src/main/AndroidManifest.xml")
m = manifest.read_text(encoding="utf-8")
if m.count('android:label="小六 Robot"') == 1:
    m = m.replace('android:label="小六 Robot"', 'android:label="贾维斯"')
elif 'android:label="贾维斯"' not in m:
    raise SystemExit("Unknown launcher app label; refusing to guess")
manifest.write_text(m, encoding="utf-8")

# Retain the old wake phrase as fallback; experiment with the new phrase using Vosk.
wake = Path("app/src/main/java/me/rerere/rikkahub/robot/WakeVoiceService.kt")
w = wake.read_text(encoding="utf-8")
old = 'val grammar = """["小六小六", "小六 小六", "小刘小刘", "你好小六", "小六你好", "[unk]"]"""'
new = 'val grammar = """["贾维斯", "贾 维 斯", "贾维斯贾维斯", "你好贾维斯", "小六小六", "小六 小六", "小刘小刘", "你好小六", "小六你好", "[unk]"]"""'
assert w.count(old) == 1, "Wake phrase grammar changed"
w = w.replace(old, new)
old = 'return words.contains("小六小六") || words.contains("小刘小刘") ||'
assert w.count(old) == 1, "Wake phrase match anchor changed"
w = w.replace(old, 'return words.contains("贾维斯") || words.contains("小六小六") || words.contains("小刘小刘") ||')
w = w.replace('等待唤醒：“小六小六”', '等待唤醒：“贾维斯”')
w = w.replace('离线监听“小六小六” · 点击通知打开小六', '离线监听“贾维斯” · 点击通知打开贾维斯')
w = w.replace('小六 · 离线唤醒监听中', '贾维斯 · 离线唤醒监听中')
w = w.replace('小六语音唤醒', '贾维斯语音唤醒')
w = w.replace('请先允许小六使用麦克风', '请先允许贾维斯使用麦克风')
w = w.replace('"小六：$shortAnswer"', '"贾维斯：$shortAnswer"')
wake.write_text(w, encoding="utf-8")

# Both names in visible UI; DO NOT rename internal storage keys or Java classes.
for file in [Path("app/src/main/java/me/rerere/rikkahub/robot/XiaoLiuFeatureCenterActivity.kt")]:
    if file.exists():
        t = file.read_text(encoding="utf-8")
        t = t.replace('小六功能中心', '贾维斯功能中心')
        file.write_text(t, encoding="utf-8")
print("Jarvis V0.9.0 patch complete; existing RikkaHub storage preserved")
