#!/usr/bin/env python3
"""Build a separate Jarvis Android app ON TOP OF ExTV/rikkahub-agent.
This is a first-stage migration: Agent handles chat/memory/voice/tools; Jarvis
has a standalone neutral-themed launcher with the existing chibi pose atlas.
No automatic transfer of credentials, settings, or chat history is attempted.
"""
from pathlib import Path
import base64
import re

root=Path("app/src/main")
package=root/"java/me/rerere/rikkahub/jarvis"
package.mkdir(parents=True,exist_ok=True)
activity=package/"JarvisAgentHomeActivity.kt"
assert not activity.exists(), activity
activity.write_text(r'''package me.rerere.rikkahub.jarvis

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.painter.BitmapPainter
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.imageResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import me.rerere.rikkahub.R
import me.rerere.rikkahub.RouteActivity
import me.rerere.rikkahub.data.datastore.SettingsStore
import me.rerere.rikkahub.data.datastore.getCurrentAssistant
import org.koin.android.ext.android.inject
import java.util.UUID
import kotlin.math.sin

/**
 * App-only active session. RikkaHub Agent persists all actual conversations
 * and its own long-term memory in its database.
 */
object JarvisSession {
    var conversationId: String = UUID.randomUUID().toString()
        private set
    var latestTurn by mutableStateOf("")
        private set
    var assistantName by mutableStateOf("默认助手")
        private set
    fun onColdHomeStart() {
        conversationId = UUID.randomUUID().toString()
        latestTurn = ""
    }
    fun syncChat(id: String) { conversationId = id }
    fun receiveCompletedTurn(id: String, agent: String, user: String, answer: String) {
        if (id != conversationId) return
        assistantName = agent
        latestTurn = "你：" + user + "\n" + agent + "：" + answer
    }
}

class JarvisAgentHomeActivity : ComponentActivity() {
    private val settingsStore by inject<SettingsStore>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (savedInstanceState == null && isTaskRoot) JarvisSession.onColdHomeStart()
        setContent { Home() }
    }

    private fun openChat() {
        startActivity(Intent(this, RouteActivity::class.java).apply {
            putExtra("conversationId", JarvisSession.conversationId)
        })
    }

    @Composable
    private fun Home() {
        val preferences = remember { getSharedPreferences("jarvis_agent_home", MODE_PRIVATE) }
        var night by remember { mutableStateOf(preferences.getBoolean("night", true)) }
        var drawer by remember { mutableStateOf(false) }
        val settings by settingsStore.settingsFlow.collectAsStateWithLifecycle()
        val active = settings.getCurrentAssistant().name.ifBlank { "默认助手" }
        val background = if (night) Color(0xFF111114) else Color(0xFFF8F8F7)
        val foreground = if (night) Color(0xFFF4F4F3) else Color(0xFF1F201F)
        val muted = if (night) Color(0xFFA4A5A7) else Color(0xFF686A6B)
        val card = if (night) Color(0xFF222225) else Color.White
        val accent = if (night) Color(0xFFA7C7AD) else Color(0xFF62816B)
        Box(Modifier.fillMaxSize().background(background)) {
            Column(
                Modifier.fillMaxSize().verticalScroll(rememberScrollState())
                    .padding(horizontal = 22.dp, vertical = 20.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Row(
                    Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        Modifier.size(49.dp).clip(RoundedCornerShape(15.dp))
                            .background(card).clickable { drawer = true },
                        contentAlignment = Alignment.Center
                    ) { Text("☰", color = foreground, fontSize = 25.sp) }
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)) {
                        Text(active, color = foreground, fontSize = 24.sp,
                            fontWeight = FontWeight.Bold, maxLines = 1,
                            overflow = TextOverflow.Ellipsis)
                        Text("贾维斯 · RikkaHub Agent 底座",
                            fontSize = 11.sp, color = muted)
                    }
                }
                Spacer(Modifier.height(30.dp))
                val atlas = ImageBitmap.imageResource(id = R.drawable.jarvis_mascot_atlas)
                val cellWidth = atlas.width / 3
                val cellHeight = atlas.height / 2
                val transition = rememberInfiniteTransition(label = "jarvis-breath")
                val breath by transition.animateFloat(
                    initialValue = 0f, targetValue = 1f,
                    animationSpec = infiniteRepeatable(
                        animation = tween(2600, easing = LinearEasing),
                        repeatMode = RepeatMode.Reverse
                    ), label = "breath"
                )
                val painter = remember(atlas) {
                    BitmapPainter(atlas, srcOffset = IntOffset.Zero,
                        srcSize = IntSize(cellWidth, cellHeight))
                }
                Image(
                    painter = painter, contentDescription = "贾维斯动态角色",
                    contentScale = ContentScale.Fit,
                    modifier = Modifier.fillMaxWidth().height(310.dp)
                        .graphicsLayer {
                            translationY = sin(breath * 3.14159f) * 5.dp.toPx()
                            rotationZ = sin(breath * 3.14159f) * 1.1f
                        }
                )
                Text("随时为你提供帮助", color = muted, fontSize = 13.sp)
                Spacer(Modifier.height(25.dp))
                Column(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(23.dp))
                        .background(card).clickable { openChat() }.padding(18.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("最近对话", color = foreground, fontSize = 16.sp,
                            fontWeight = FontWeight.SemiBold,
                            modifier = Modifier.weight(1f))
                        Text("查看完整聊天 ›", color = muted, fontSize = 12.sp)
                    }
                    Spacer(Modifier.height(12.dp))
                    Text(JarvisSession.latestTurn.ifBlank {
                        "新会话已经准备好。开始打字、语音或拍照，最近一轮回复将在这里显示。"
                    }, color = if (JarvisSession.latestTurn.isBlank()) muted else foreground,
                        fontSize = 13.sp, lineHeight = 22.sp)
                }
                Spacer(Modifier.height(26.dp))
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Box(Modifier.size(58.dp).clip(CircleShape)
                            .background(card).clickable { openChat() },
                            contentAlignment = Alignment.Center) {
                            Text("☷", color = foreground, fontSize = 25.sp)
                        }
                        Text("聊天", color = muted, fontSize = 12.sp)
                    }
                    Box(Modifier.size(82.dp).clip(CircleShape).background(accent)
                        .clickable { openChat() }, contentAlignment = Alignment.Center) {
                        Text("◉", color = background, fontSize = 30.sp)
                    }
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Box(Modifier.size(58.dp).clip(CircleShape)
                            .background(card).clickable { drawer = true },
                            contentAlignment = Alignment.Center) {
                            Text("⊞", color = foreground, fontSize = 25.sp)
                        }
                        Text("更多", color = muted, fontSize = 12.sp)
                    }
                }
                Spacer(Modifier.height(15.dp))
                Text("语音和手机工具由 Agent 聊天页提供",
                    color = muted, fontSize = 11.sp)
                Spacer(Modifier.height(15.dp))
                Text("贾维斯 Agent 1.0 迁移测试版", fontSize = 10.sp, color = muted)
            }
            if (drawer) {
                Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = .58f))
                    .clickable { drawer = false })
                Column(
                    Modifier.fillMaxHeight().fillMaxWidth(.84f)
                        .background(card, RoundedCornerShape(topEnd = 25.dp, bottomEnd = 25.dp))
                        .verticalScroll(rememberScrollState())
                        .padding(22.dp).align(Alignment.CenterStart)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("贾维斯", fontWeight = FontWeight.Bold, fontSize = 23.sp,
                            color = foreground, modifier = Modifier.weight(1f))
                        Text("✕", color = muted, fontSize = 25.sp,
                            modifier = Modifier.clickable { drawer = false })
                    }
                    Spacer(Modifier.height(22.dp))
                    Text("智能体 · " + active, color = muted, fontSize = 13.sp)
                    Spacer(Modifier.height(12.dp))
                    MenuEntry("切换智能体 / 历史会话", card, foreground) {
                        drawer = false; openChat()
                    }
                    Spacer(Modifier.height(20.dp))
                    Text("外观", color = muted, fontSize = 13.sp)
                    Spacer(Modifier.height(10.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        listOf("☀ 白天", "☾ 夜间").forEachIndexed { index, title ->
                            val selected = night == (index == 1)
                            Box(Modifier.weight(1f)
                                .clip(RoundedCornerShape(14.dp))
                                .background(if (selected) accent.copy(alpha = .3f)
                                    else background)
                                .clickable {
                                    night = index == 1
                                    preferences.edit().putBoolean("night", night).apply()
                                }.padding(vertical = 12.dp), contentAlignment=Alignment.Center) {
                                Text(title, color = foreground, fontSize = 13.sp)
                            }
                        }
                    }
                    Spacer(Modifier.height(24.dp))
                    Text("Agent 功能中心", color = muted, fontSize = 13.sp)
                    Spacer(Modifier.height(11.dp))
                    listOf(
                        "手机操作 · 读屏、点击、滑动",
                        "图像识别 · 照片、文件",
                        "工具中心 · MCP / Local Tools",
                        "任务计划 · 定时自动化",
                        "长期记忆与上下文压缩"
                    ).forEach { title ->
                        MenuEntry(title, background, foreground) {
                            drawer = false; openChat()
                        }
                    }
                    Spacer(Modifier.height(12.dp))
                    Text("先从 Agent 聊天页授权工具，所有能力默认遵循原分支安全设置。",
                        color = muted, fontSize = 11.sp, lineHeight = 18.sp)
                }
            }
        }
    }
}

@Composable
private fun MenuEntry(
    title: String, fill: Color, ink: Color, onClick: () -> Unit
) {
    Text(
        title + "  ›", color = ink, fontSize = 13.sp,
        modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp)
            .clip(RoundedCornerShape(14.dp)).background(fill)
            .clickable(onClick=onClick).padding(13.dp)
    )
}
''',encoding="utf-8")

# Configure new isolated APK; never clobber previous Jarvis or original Agent app.
gradle=Path("app/build.gradle.kts")
g=gradle.read_text(encoding="utf-8")
for old,new in (
    ('applicationId = "excp.rikkahub"', 'applicationId = "com.jarvis.agent.preview"'),
    ('versionCode = 187', 'versionCode = 1000'),
    ('versionName = "2.5.1"', 'versionName = "1.0.0-agent-preview"'),
    ('abiFilters += listOf("arm64-v8a", "x86_64")',
     'abiFilters += listOf("arm64-v8a")')
):
    if g.count(old)!=1:raise SystemExit("Agent gradle mismatch: "+old)
    g=g.replace(old,new,1)
# Github runners provide the SDK 37.2 minor API platform, not android-37.
assert 'compileSdk = 37' in g
g=g.replace('compileSdk = 37',
    'compileSdk {\n        version = release(37) {\n            minorApiLevel = 2\n        }\n    }',1)
# Gradle debug is signed with debug keystore; avoid multiple split APKs.
assert 'isEnable = !isBuildingBundle' in g
g=g.replace('isEnable = !isBuildingBundle', 'isEnable = false',1)
gradle.write_text(g,encoding="utf-8")

manifest=root/"AndroidManifest.xml"
m=manifest.read_text(encoding="utf-8")
route_needle='''    <activity
      android:name=".RouteActivity"'''
assert m.count(route_needle)==1
# Move launcher to Jarvis while keeping RikkaHub deep links fully functional.
start=m.index(route_needle)
end=m.index('    </activity>',start)+len('    </activity>')
segment=m[start:end]
intent=re.compile(r'      <intent-filter>\s*<action android:name="android.intent.action.MAIN"\s*/>\s*<category android:name="android.intent.category.LAUNCHER"\s*/>\s*</intent-filter>',re.S)
segment,n=intent.subn('',segment,count=1)
if n!=1:raise SystemExit("Agent launcher intent-filter mismatch")
m=m[:start]+segment+m[end:]
entry='''    <activity android:name=".jarvis.JarvisAgentHomeActivity"
      android:exported="true"
      android:theme="@style/Theme.Rikkahub">
      <intent-filter>
        <action android:name="android.intent.action.MAIN" />
        <category android:name="android.intent.category.LAUNCHER" />
      </intent-filter>
    </activity>
'''
assert route_needle in m
m=m.replace(route_needle,entry+route_needle,1)
# Another LAUNCHER category also exists inside <queries> for package visibility.
assert m.count('<category android:name="android.intent.category.LAUNCHER" />')==2
manifest.write_text(m,encoding="utf-8")

# Set Chinese display name without editing upstream string translations.
namefile=root/"res/values/strings.xml"
strings=namefile.read_text(encoding="utf-8")
import re as _re
strings,count=_re.subn(r'<string name="app_name">[^<]*</string>',
    '<string name="app_name">贾维斯 Agent</string>',strings,count=1)
if count!=1:raise SystemExit("app_name resource anchor missing")
namefile.write_text(strings,encoding="utf-8")

# Import the EXISTING user-approved six-pose atlas from the previous Jarvis overlay.
atlas=Path("../mascot_v083/xiaoliu_atlas.b64")
if not atlas.exists():raise SystemExit("Jarvis pose atlas source missing")
target=root/"res/drawable-nodpi/jarvis_mascot_atlas.webp"
target.parent.mkdir(parents=True,exist_ok=True)
binary=base64.b64decode(atlas.read_text(encoding="ascii"))
assert binary[:4]==b"RIFF"
target.write_bytes(binary)

# Add the Agent-native chat's return-to-Jarvis action and a latest-turn sync.
chat=Path("app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt")
c=chat.read_text(encoding="utf-8")
def once(a,b,label):
    global c
    if c.count(a)!=1:raise SystemExit("Agent ChatPage "+label+": "+str(c.count(a)))
    c=c.replace(a,b,1)
once('import android.net.Uri','''import android.net.Uri
import android.content.Intent
import me.rerere.ai.core.MessageRole
import me.rerere.rikkahub.jarvis.JarvisAgentHomeActivity
import me.rerere.rikkahub.jarvis.JarvisSession''',"new imports")
once('''    val assistant = setting.getCurrentAssistant()
    var showFilesSheet''',
'''    val assistant = setting.getCurrentAssistant()
    LaunchedEffect(conversation.id) {
        JarvisSession.syncChat(conversation.id.toString())
    }
    LaunchedEffect(conversation.currentMessages, loadingJob) {
        if (loadingJob != null) return@LaunchedEffect
        val messages = conversation.currentMessages
        val reply = messages.lastOrNull() ?: return@LaunchedEffect
        if (reply.role != MessageRole.ASSISTANT) return@LaunchedEffect
        val question = messages.dropLast(1).lastOrNull {
            it.role == MessageRole.USER
        } ?: return@LaunchedEffect
        fun visible(parts: List<UIMessagePart>): String = parts
            .filterIsInstance<UIMessagePart.Text>()
            .joinToString(" ") { it.text }.trim()
        val userText = visible(question.parts).ifBlank { "（图片或附件）" }
        val replyText = visible(reply.parts)
        if (replyText.isNotBlank()) JarvisSession.receiveCompletedTurn(
            conversation.id.toString(), assistant.name.ifBlank { "默认助手" },
            userText, replyText
        )
    }
    var showFilesSheet''',"latest turn mirror")
once('''        actions = {
            IconButton(
                onClick = {
                    onClickMenu()
                }
            )''',
'''        actions = {
            val homeContext = LocalContext.current
            IconButton(onClick = {
                homeContext.startActivity(
                    Intent(homeContext, JarvisAgentHomeActivity::class.java).apply {
                        flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or
                            Intent.FLAG_ACTIVITY_SINGLE_TOP
                    }
                )
            }) {
                Text("主页", fontSize = 12.sp)
            }
            IconButton(
                onClick = {
                    onClickMenu()
                }
            )''',"home navigation")
chat.write_text(c,encoding="utf-8")

print("Jarvis Agent V1.0.0 base migration patch installed: Agent backend, new launcher, mascot, Q&A preview, home button")
