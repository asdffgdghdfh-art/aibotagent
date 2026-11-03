package me.rerere.rikkahub.jarvis

import android.annotation.SuppressLint
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.webkit.CookieManager
import android.webkit.SslErrorHandler
import android.net.http.SslError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.viewinterop.AndroidView

/** Aibot Link - integrated phone surface for owner-authenticated cross-device tasks.
 * Browser session token is entered directly into the self-hosted portal; no model tokens
 * are passed through the Android bridge or persisted in SharedPreferences.
 */
class AibotLinkActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { AibotLinkScreen() }
    }
}

private fun safeRelayUrl(raw: String): String? {
    val u = Uri.parse(raw.trim().trimEnd('/'))
    val scheme = u.scheme?.lowercase()
    if (u.userInfo != null || u.host.isNullOrBlank()) return null
    return if (scheme == "https") u.toString() else null
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
private fun AibotLinkScreen() {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("aibot_link_v110", android.content.Context.MODE_PRIVATE) }
    var url by rememberSaveable { mutableStateOf(prefs.getString("relay_url", "") ?: "") }
    var active by rememberSaveable { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    var webView by remember { mutableStateOf<WebView?>(null) }
    BackHandler(enabled = active) {
        val w = webView
        if (w != null && w.canGoBack()) w.goBack() else active = false
    }
    DisposableEffect(active) {
        onDispose {
            webView?.stopLoading()
            webView?.destroy()
            webView = null
        }
    }
    Column(Modifier.fillMaxSize().background(Color(0xFF0D0F15))) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(Modifier.weight(1f)) {
                Text("Aibot Link", fontSize = 22.sp, fontWeight = FontWeight.Bold, color = Color.White)
                Text("我的设备 · 任务同步 · 审批", fontSize = 11.sp, color = Color(0xFFB0B8C6))
            }
            if (active) OutlinedButton(onClick = { active = false }) { Text("更换服务器") }
        }
        if (active) {
            val trusted = safeRelayUrl(url)
            if (trusted == null) {
                active = false
            } else {
                val allowedHost = Uri.parse(trusted).host
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
                            settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
                            CookieManager.getInstance().setAcceptThirdPartyCookies(this, false)
                            webViewClient = object : WebViewClient() {
                                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                                    val dest = request.url
                                    return !(dest.scheme == "https" && dest.host == allowedHost)
                                }
                                override fun onReceivedSslError(view: WebView?, handler: SslErrorHandler?, sslError: SslError?) {
                                    handler?.cancel()  // Never bypass TLS certificate errors.
                                    error = "服务器证书无效，已停止连接"
                                }
                            }
                            webView = this
                            loadUrl(trusted)
                        }
                    },
                    update = { view -> if (view.url == null) view.loadUrl(trusted) }
                )
            }
        } else {
            Column(
                Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(22.dp),
                verticalArrangement = Arrangement.spacedBy(15.dp)
            ) {
                Text("同一个 Aibot，跨设备继续工作。", color = Color.White,
                    fontSize = 24.sp, fontWeight = FontWeight.Bold, lineHeight = 33.sp)
                Text("连接你自己部署的 Aibot Relay，即可看到 Windows、Mac、服务器的在线状态，并远程分配 Codex / DSH 任务。",
                    color = Color(0xFFB9C1D0), fontSize = 14.sp, lineHeight = 22.sp)
                OutlinedTextField(
                    value = url, onValueChange = { url = it; error = "" },
                    label = { Text("Relay HTTPS 地址") },
                    placeholder = { Text("https://aibot.your-domain.com") },
                    singleLine = true, modifier = Modifier.fillMaxWidth()
                )
                if (error.isNotBlank()) Text(error, color = Color(0xFFFF9E98), fontSize = 12.sp)
                Button(modifier = Modifier.fillMaxWidth(),onClick = {
                    val normalized = safeRelayUrl(url)
                    if (normalized == null) {
                        error = "必须填写有效的 HTTPS 地址（不可使用不安全的 HTTP）"
                    } else {
                        prefs.edit().putString("relay_url", normalized).apply()
                        url = normalized
                        active = true
                    }
                }) { Text("连接设备网络") }
                Spacer(Modifier.height(10.dp))
                Text("安全说明", color = Color.White, fontWeight = FontWeight.SemiBold)
                Text("· 电脑不开放公网端口，Bridge 主动连接 Relay。\n· 不在手机应用中保存电脑 Codex / DSH 的登录密钥。\n· 重要操作需要你的明确审批。\n· V1.1 首版同步任务，不自动上传所有聊天记录。",
                    color = Color(0xFFAEB7C5), fontSize = 13.sp, lineHeight = 22.sp)
            }
        }
    }
}
