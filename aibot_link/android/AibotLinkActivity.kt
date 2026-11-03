package me.rerere.rikkahub.jarvis

import android.annotation.SuppressLint
import android.net.Uri
import android.os.Bundle
import android.net.http.SslError
import android.webkit.CookieManager
import android.webkit.SslErrorHandler
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.WebSettings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView

/** Aibot Link V1.1 - same owner-authenticated mobile console as the desktop relay.
 * No Codex/DSH login secrets are copied into Android. HTTPS only.
 */
class AibotLinkActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { AibotLinkScreen() }
    }
}

private fun safeRelayUrl(raw: String): String? {
    val u = Uri.parse(raw.trim().trimEnd('/'))
    if (u.scheme?.lowercase() != "https" || u.userInfo != null || u.host.isNullOrBlank()) return null
    return u.toString()
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
private fun AibotLinkScreen() {
    val context = LocalContext.current
    val preferences = remember { context.getSharedPreferences("aibot_link_v110", android.content.Context.MODE_PRIVATE) }
    var relayUrl by rememberSaveable { mutableStateOf(preferences.getString("relay_url", "") ?: "") }
    var connected by rememberSaveable { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    var browser by remember { mutableStateOf<WebView?>(null) }

    BackHandler(enabled = connected) {
        val view = browser
        if (view != null && view.canGoBack()) view.goBack() else connected = false
    }
    DisposableEffect(connected) {
        onDispose {
            browser?.stopLoading()
            browser?.destroy()
            browser = null
        }
    }

    Column(Modifier.fillMaxSize().background(Color(0xFF0D0F15))) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(Modifier.weight(1f)) {
                Text("Aibot Link", fontSize = 22.sp, fontWeight = FontWeight.Bold, color = Color.White)
                Text("我的设备 · 任务同步 · 审批", fontSize = 11.sp, color = Color(0xFFB0B8C6))
            }
            if (connected) OutlinedButton(onClick = { connected = false }) { Text("更换服务器") }
        }

        if (connected) {
            val safeUrl = safeRelayUrl(relayUrl)
            if (safeUrl == null) {
                connected = false
            } else {
                val permittedHost = Uri.parse(safeUrl).host
                AndroidView(
                    modifier = Modifier.fillMaxSize(),
                    factory = { ctx ->
                        WebView(ctx).apply {
                            settings.javaScriptEnabled = true
                            settings.domStorageEnabled = true
                            settings.allowFileAccess = false
                            settings.allowContentAccess = false
                            settings.javaScriptCanOpenWindowsAutomatically = false
                            settings.setSupportMultipleWindows(false)
                            settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
                            CookieManager.getInstance().setAcceptThirdPartyCookies(this, false)
                            webViewClient = object : WebViewClient() {
                                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                                    val target = request.url
                                    return !(target.scheme == "https" && target.host == permittedHost)
                                }
                                override fun onReceivedSslError(view: WebView?, handler: SslErrorHandler?, sslError: SslError?) {
                                    handler?.cancel()
                                    error = "服务器 TLS 证书无效，已停止连接"
                                }
                            }
                            browser = this
                            loadUrl(safeUrl)
                        }
                    },
                    update = { view -> if (view.url == null) view.loadUrl(safeUrl) }
                )
            }
        } else {
            Column(
                Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(22.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                Text("一个 Aibot，连接所有设备。", color = Color.White,
                    fontSize = 24.sp, fontWeight = FontWeight.Bold, lineHeight = 33.sp)
                Text("接入你自己的 Aibot Relay 后，手机即可查看 Windows、Mac 的在线状态，调用本机 Codex，并同步执行结果。",
                    color = Color(0xFFB9C1D0), fontSize = 14.sp, lineHeight = 22.sp)
                OutlinedTextField(
                    value = relayUrl, onValueChange = { relayUrl = it; error = "" },
                    label = { Text("Relay HTTPS 地址") },
                    placeholder = { Text("https://aibot.your-domain.com") },
                    singleLine = true, modifier = Modifier.fillMaxWidth()
                )
                if (error.isNotEmpty()) Text(error, color = Color(0xFFFF9E98), fontSize = 12.sp)
                Button(modifier = Modifier.fillMaxWidth(), onClick = {
                    val normalized = safeRelayUrl(relayUrl)
                    if (normalized == null) {
                        error = "仅允许有效 HTTPS 地址；请先配置自己服务器的 TLS 证书"
                    } else {
                        preferences.edit().putString("relay_url", normalized).apply()
                        relayUrl = normalized
                        connected = true
                    }
                }) { Text("连接设备网络") }
                Spacer(Modifier.height(9.dp))
                Text("安全说明", color = Color.White, fontWeight = FontWeight.SemiBold)
                Text("· 电脑主动连接 Relay，无需暴露本机公网端口。\n" +
                     "· 电脑 Codex / DSH 登录凭据不复制到手机。\n" +
                     "· DSH 任务需单独审批，敏感目录默认禁用。\n" +
                     "· V1.1 首版同步任务和摘要，不自动上传原有聊天记录。",
                    color = Color(0xFFAEB7C5), fontSize = 13.sp, lineHeight = 22.sp)
            }
        }
    }
}
