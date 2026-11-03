#!/usr/bin/env python3
"""Jarvis Agent V1.0.4: inline voice, assistant drawer, and chat bubbles.
Run after the V1.0.3 permanent-signed setup; no separate package or signing.
"""
from pathlib import Path

base=Path("app/src/main")
home=base/"java/me/rerere/rikkahub/jarvis/JarvisAgentHomeActivity.kt"
s=home.read_text(encoding="utf-8")

def once(a,b,label):
    global s
    n=s.count(a)
    assert n==1, (label,n)
    s=s.replace(a,b,1)

imports=[
    "import android.Manifest",
    "import android.content.pm.PackageManager",
    "import android.speech.RecognitionListener",
    "import android.speech.RecognizerIntent",
    "import android.speech.SpeechRecognizer",
    "import android.speech.tts.TextToSpeech",
    "import androidx.activity.compose.rememberLauncherForActivityResult",
    "import androidx.activity.result.contract.ActivityResultContracts",
    "import androidx.core.content.ContextCompat",
    "import kotlinx.coroutines.launch",
    "import me.rerere.ai.core.MessageRole",
    "import me.rerere.ai.ui.UIMessagePart",
    "import me.rerere.rikkahub.ui.pages.chat.ChatVM",
    "import org.koin.androidx.compose.koinViewModel",
    "import org.koin.core.parameter.parametersOf",
    "import java.util.Locale",
]
for imp in imports:
    if imp not in s:
        s=s.replace("import android.content.Intent",imp+"\nimport android.content.Intent",1)

once(
    '''    val agentSettings by settingsStore.settingsFlow.collectAsStateWithLifecycle()
    val activeName = agentSettings.getCurrentAssistant().name.ifBlank { "默认助手" }''',
    '''    val agentSettings by settingsStore.settingsFlow.collectAsStateWithLifecycle()
    val activeName = agentSettings.getCurrentAssistant().name.ifBlank { "默认助手" }

    // Jarvis Home is now a first-class chat surface backed by the SAME
    // RikkaHub Agent ChatVM/ChatService as its normal chat page.
    val vm: ChatVM = koinViewModel(
        parameters = { parametersOf(JarvisSession.conversationId) }
    )
    val agentConversation by vm.conversation.collectAsStateWithLifecycle()
    val agentLoading by vm.conversationJob.collectAsStateWithLifecycle()
    val uiScope = rememberCoroutineScope()

    var voiceStatus by remember { mutableStateOf("轻触麦克风，直接说话") }
    var voiceListening by remember { mutableStateOf(false) }
    var awaitingVoiceReply by remember { mutableStateOf(false) }
    var lastVoiceAnswerId by remember { mutableStateOf("") }
    var ttsReady by remember { mutableStateOf(false) }
    val speaker = remember(context) {
        TextToSpeech(context) { status ->
            ttsReady = status == TextToSpeech.SUCCESS
        }
    }
    DisposableEffect(speaker) {
        onDispose {
            speaker.stop()
            speaker.shutdown()
        }
    }

    val speechRecognizer = remember(context) {
        if (SpeechRecognizer.isRecognitionAvailable(context))
            SpeechRecognizer.createSpeechRecognizer(context)
        else null
    }
    DisposableEffect(speechRecognizer, vm) {
        speechRecognizer?.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: android.os.Bundle?) {
                voiceListening = true
                voiceStatus = "正在听，请说话…"
            }
            override fun onBeginningOfSpeech() { voiceStatus = "正在听你说话…" }
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {
                voiceListening = false
                voiceStatus = "识别中…"
            }
            override fun onError(error: Int) {
                voiceListening = false
                voiceStatus = when (error) {
                    SpeechRecognizer.ERROR_NO_MATCH -> "没有听清，再试一次"
                    SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "未检测到语音，再试一次"
                    SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "请先授予麦克风权限"
                    SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "语音识别正在使用中"
                    else -> "语音识别失败（" + error + "），再试一次"
                }
            }
            override fun onResults(results: android.os.Bundle?) {
                voiceListening = false
                val spoken = results
                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull().orEmpty().trim()
                if (spoken.isBlank()) {
                    voiceStatus = "没有听清，再试一次"
                    return
                }
                lastVoiceAnswerId = vm.conversation.value.currentMessages
                    .lastOrNull { it.role == MessageRole.ASSISTANT }
                    ?.id?.toString().orEmpty()
                awaitingVoiceReply = true
                voiceStatus = "已听到：" + spoken.take(65) + " · 正在回答…"
                vm.handleMessageSend(listOf(UIMessagePart.Text(text = spoken)))
            }
            override fun onPartialResults(partialResults: android.os.Bundle?) {
                val partial = partialResults
                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull().orEmpty()
                if (partial.isNotBlank()) voiceStatus = "正在听：" + partial.take(60)
            }
            override fun onEvent(eventType: Int, params: android.os.Bundle?) {}
        })
        onDispose {
            speechRecognizer?.cancel()
            speechRecognizer?.destroy()
        }
    }

    val beginVoice = {
        if (speechRecognizer == null) {
            voiceStatus = "未找到系统语音识别服务，请启用语音输入"
        } else {
            speaker.stop()
            try {
                val request = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(
                        RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                        RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
                    )
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN")
                    putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                    putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
                }
                voiceStatus = "准备聆听…"
                voiceListening = true
                speechRecognizer.startListening(request)
            } catch (e: Exception) {
                voiceListening = false
                voiceStatus = "麦克风启动失败：" + (e.localizedMessage ?: "请重试")
            }
        }
    }
    val microphonePermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) beginVoice()
        else voiceStatus = "需要允许麦克风权限才能语音聊天"
    }
    val onMicrophoneTap = {
        if (voiceListening) {
            speechRecognizer?.stopListening()
            voiceListening = false
            voiceStatus = "正在识别…"
        } else if (
            ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO)
            == PackageManager.PERMISSION_GRANTED
        ) {
            beginVoice()
        } else {
            microphonePermission.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    // Speak the newly completed answer only for messages prompted by voice.
    LaunchedEffect(agentConversation.currentMessages, agentLoading, awaitingVoiceReply) {
        if (!awaitingVoiceReply || agentLoading != null) return@LaunchedEffect
        val newest = agentConversation.currentMessages
            .lastOrNull { it.role == MessageRole.ASSISTANT }
            ?: return@LaunchedEffect
        if (newest.id.toString() == lastVoiceAnswerId) return@LaunchedEffect
        val answer = newest.parts.filterIsInstance<UIMessagePart.Text>()
            .joinToString(" ") { it.text }.trim()
        if (answer.isNotBlank()) {
            awaitingVoiceReply = false
            voiceStatus = "回答完成，轻触麦克风继续"
            if (ttsReady) {
                speaker.language = Locale.SIMPLIFIED_CHINESE
                speaker.speak(answer.take(1200), TextToSpeech.QUEUE_FLUSH,
                    null, "jarvis-v104-answer")
            }
        }
    }''',
    "Agent voice state"
)

# Replace duplicate navigation entries with the full, live assistant list.
a=s.index('''                JarvisMenuLine("当前智能体 · " + activeName,''')
b=s.index('''                Spacer(Modifier.height(20.dp))''',a)
s=s[:a]+'''                if (agentSettings.assistants.isEmpty()) {
                    Text("还没有智能体，请先在 Agent 设置中创建。",
                        color = muted, fontSize = 12.sp)
                }
                agentSettings.assistants.forEach { assistant ->
                    val selected = assistant.id == agentSettings.assistantId
                    Row(
                        Modifier.fillMaxWidth()
                            .clip(RoundedCornerShape(17.dp))
                            .background(if (selected) green.copy(alpha = 0.17f) else subtle)
                            .clickable {
                                vm.moveConversationToAssistant(agentConversation, assistant.id)
                                uiScope.launch { settingsStore.updateAssistant(assistant.id) }
                                menuOpen = false
                            }
                            .padding(horizontal = 12.dp, vertical = 12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Box(
                            Modifier.size(36.dp).clip(CircleShape)
                                .background(if (selected) green.copy(alpha = 0.25f) else surface),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(assistant.name.ifBlank { "AI" }.take(1),
                                color = ink, fontSize = 16.sp,
                                fontWeight = FontWeight.SemiBold)
                        }
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(assistant.name.ifBlank { "默认助手" },
                                color = ink, fontSize = 14.sp,
                                fontWeight = if (selected)
                                    FontWeight.Bold else FontWeight.Normal,
                                maxLines = 1, overflow = TextOverflow.Ellipsis)
                            Text(if (selected) "当前智能体" else "轻触切换",
                                color = muted, fontSize = 11.sp)
                        }
                        Text(if (selected) "✓" else "›",
                            color = if (selected) green else muted, fontSize = 18.sp)
                    }
                    Spacer(Modifier.height(8.dp))
                }
'''+s[b:]

# Replace the huge single recent-turn card with actual chat bubbles.
old='''                    if (displayDialog.isBlank()) {
                        Text("开始和贾维斯聊天，最新一轮问答会显示在这里。",
                            color = muted, fontSize = 13.sp, lineHeight = 20.sp)
                    } else {
                        // Full most recent exchange; parent page scrolls for long responses.
                        Text(displayDialog, color = ink, fontSize = 13.sp,
                            lineHeight = 22.sp, softWrap = true)
                    }'''
new='''                    val previewMessages = agentConversation.currentMessages
                        .filter { it.role == MessageRole.USER || it.role == MessageRole.ASSISTANT }
                        .takeLast(4)
                    if (previewMessages.isEmpty()) {
                        Text("对话会在这里以消息气泡显示。点麦克风即可说话。",
                            color = muted, fontSize = 13.sp, lineHeight = 20.sp)
                    } else {
                        previewMessages.forEach { message ->
                            val sentByMe = message.role == MessageRole.USER
                            val content = message.parts.filterIsInstance<UIMessagePart.Text>()
                                .joinToString("\\n") { it.text }.trim()
                            if (content.isNotBlank()) {
                                Row(
                                    Modifier.fillMaxWidth().padding(vertical = 4.dp),
                                    horizontalArrangement = if (sentByMe)
                                        Arrangement.End else Arrangement.Start
                                ) {
                                    Column(
                                        Modifier.fillMaxWidth(0.86f)
                                            .clip(
                                                RoundedCornerShape(
                                                    topStart = 17.dp, topEnd = 17.dp,
                                                    bottomEnd = if (sentByMe) 5.dp else 17.dp,
                                                    bottomStart = if (sentByMe) 17.dp else 5.dp
                                                )
                                            )
                                            .background(
                                                if (sentByMe) green.copy(alpha = 0.21f) else subtle
                                            )
                                            .padding(horizontal = 13.dp, vertical = 10.dp)
                                    ) {
                                        Text(if (sentByMe) "你" else activeName,
                                            color = if (sentByMe) green else muted,
                                            fontSize = 10.sp,
                                            fontWeight = FontWeight.SemiBold)
                                        Spacer(Modifier.height(3.dp))
                                        Text(content, color = ink, fontSize = 13.sp,
                                            lineHeight = 20.sp, softWrap = true)
                                    }
                                }
                            }
                        }
                        if (agentLoading != null) {
                            Text(activeName + " 正在回复…",
                                color = muted, fontSize = 12.sp)
                        }
                    }'''
once(old,new,"bubble display")

# Explicitly keep speaking in the Jarvis Home activity.
needle='''.clickable(onClick = { openChat() }),'''
mic=s.index('''Modifier.size(92.dp).clip(CircleShape)''')
idx=s.index(needle,mic)
s=s[:idx]+s[idx:].replace(needle,'''.clickable(onClick = { onMicrophoneTap() }),''',1)

once('''                "语音、拍照和手机操作通过 Agent 聊天页开启",''',
     '''                voiceStatus,''',"voice status text")
once('''Text("贾维斯 Agent 1.0.2 · 精简界面",''',
     '''Text("贾维斯 Agent 1.0.4 · 原生语音版",''',"footer label")
home.write_text(s,encoding="utf-8")

# Android 11+ service visibility for on-device system SpeechRecognizer.
manifest=base/"AndroidManifest.xml"
m=manifest.read_text(encoding="utf-8")
anchor='''  <queries>
'''
assert m.count(anchor)==1
m=m.replace(anchor,'''  <queries>
    <intent><action android:name="android.speech.RecognitionService" /></intent>
''',1)
manifest.write_text(m,encoding="utf-8")

# Fixed package name AND exact same certificate as V1.0.3 allow in-place update.
gradle=Path("app/build.gradle.kts")
g=gradle.read_text(encoding="utf-8")
for a,b in (
    ('versionCode = 1003','versionCode = 1004'),
    ('versionName = "1.0.3-stable-signing"',
     'versionName = "1.0.4-inline-voice"'),
):
    assert g.count(a)==1,(a,g.count(a))
    g=g.replace(a,b,1)
assert 'applicationId = "com.jarvis.agent"' in g
assert 'signingConfig = signingConfigs.getByName("release")' in g
gradle.write_text(g,encoding="utf-8")
assert "vm.handleMessageSend" in s
assert "agentSettings.assistants.forEach" in s
assert "onMicrophoneTap()" in s
print("Jarvis Agent V1.0.4: real assistant list, native chat bubbles, home speech ASR -> Agent ChatVM -> TTS, permanent signed upgrade")
