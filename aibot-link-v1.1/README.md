# Aibot Link V1.1 — 跨设备 Agent（可运行 MVP）

> 状态：**核心协议与电脑 Bridge 可运行，移动端 Web 控制台可运行，Android V1.1 集成补丁已准备，但 APK 尚未编译。** 还没有连接用户自己的 ECS/Windows/Mac。请勿把它当作已经上线的正式版本。

目标：你在手机的 Aibot 下达任务，服务器只负责设备发现/任务队列/审批/日志，Windows 或 Mac 的 Bridge 在本机运行已有的 Codex（可选实验性 DSH），并把进度同步回手机。

## 组件

- `aibot_link/relay.py` — Python 标准库 + SQLite 的中央任务中继，建议运行于你已有的阿里云 ECS，Nginx HTTPS 反向代理。
- `aibot_link/bridge.py` — Windows/Mac/Linux 本机执行端，主动轮询 Relay，不需要电脑开放任何公网入站端口。
- `aibot_link/mobile.html` + `mobile.js` — 手机响应式控制台：设备状态、配对、Agent 选择、任务日志、手动审批、取消、跨设备接力。
- `aibot_link/desktop.html` — 电脑本地控制面板 `http://127.0.0.1:8766`。
- `android/patch_aibot_v110.py` + `AibotLinkActivity.kt` — 将「我的设备 · Aibot Link」接入现有 Android Aibot 抽屉，使用仅限 HTTPS 的安全 WebView 展示同一控制台，版本号更新至 `1100`。

## 0. 你需要什么

- 服务器：Linux + Python 3.10+ + Nginx + HTTPS 域名。Python 服务不依赖第三方包。
- 电脑：Windows/macOS、Python 3.10+，本机已登录 Codex CLI。DSH 是明确启用的实验性选项。
- 手机：访问部署的 HTTPS 网址。Android native 集成补丁需要下次通过 Android SDK 构建后才能进入 APK。
- 不需要购买额外模型 API；仍可能消耗你当前 Codex/DSH 订阅的额度，服务器和流量也可能有正常费用。

## 1. 先在电脑本机体验（不访问外网）

Windows PowerShell：

```powershell
$env:AIBOT_OWNER_TOKEN = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
Write-Host "保存主人密钥：$env:AIBOT_OWNER_TOKEN"
py -3 -m aibot_link.relay --host 127.0.0.1 --port 8787
```

macOS/Linux：

```bash
export AIBOT_OWNER_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
printf '请保存主人密钥：%s\n' "$AIBOT_OWNER_TOKEN"
python3 -m aibot_link.relay --host 127.0.0.1 --port 8787
```

在浏览器打开 `http://127.0.0.1:8787` 输入主人密钥。**不要把 `AIBOT_OWNER_TOKEN` 写进代码仓库或截图分享。**

另开终端，执行：

```bash
python3 -m aibot_link.bridge pair --server http://127.0.0.1:8787 --name "My Windows" --project football=/你的/绝对路径/项目
```

在手机页面「我的设备」输入它给出的 8 位验证码。配对成功后再执行：

```bash
python3 -m aibot_link.bridge run
```

电脑打开 `http://127.0.0.1:8766` 查看 Bridge 控制面板。

注意：上面的 `localhost` 演示页面只能由**同一台电脑**访问；手机异地连接必须部署 HTTPS Relay。`--project` 后面的路径必须换成真实项目文件夹；电脑不会暴露整个磁盘。

## 2. 部署到自己的阿里云 ECS

项目根目录运行：

```bash
sudo bash deploy/install_relay.sh
```

安装脚本会创建隔离系统账号、随机主人密钥、systemd 服务；Python Relay **仅监听 127.0.0.1:8787**。

复制 `deploy/nginx-aibot.conf.example` 的 HTTPS 反代配置到已有 Nginx 站点。先为你控制的域名配置有效 TLS 证书、检查防火墙，然后测试并重载 Nginx：

```bash
sudo nginx -t && sudo systemctl reload nginx
sudo systemctl status aibot-link-relay
sudo cat /etc/aibot-link/owner-token
```

手机打开 `https://你的域名/`，输入该主人密钥。不要在浏览器或公开聊天中分享它。

## 3. 在 Windows 绑定 Codex 和项目

确认已安装并登录 Codex CLI（运行 `codex --version` 和 `codex login status`）。之后在项目文件夹以外的终端：

```powershell
py -3 -m aibot_link.bridge pair --server https://你的域名 --name "Windows PC" --project football="D:\\Projects\\football"
py -3 -m aibot_link.bridge run
```

手机的「我的设备 → 配对」输入电脑打印的验证码。仅允许授权 `football` 目录，任务中的目录名不是文件路径。Mac 的指令相同，项目路径换成 `/Users/xxx/projects/...`。

如果 Windows 目前没有 Python，先安装官方 Python 3；当前包是源代码便携版，**尚不是单击安装的 EXE**。

## 4. 自主调度与安全边界

- `device_id=auto`：服务器自动选择具备项目权限、在线且待处理任务较少的设备。
- `provider=auto`：优先选择 Codex；若仅有已明确启用的 DSH，则分配 DSH。
- Codex 默认走 `workspace-write` 沙箱、`approval=never`（不自动授予沙箱之外的权限）；不会使用 `--dangerously-bypass-approvals-and-sandbox`。
- `DSH` **默认禁用**。只有 Bridge 以 `--enable-dsh` 配对，且主人在手机对**每个任务单独审批**后才会启动。此 MVP **尚不支持 DSH 进程内部逐条高危命令审批**，因此不要授权其访问敏感目录，不要将它当作严格沙箱。在完成细粒度审批之前，建议只运行 Codex。
- 任务可以暂停？**暂不支持真正的暂停/恢复**。支持取消运行中的 Agent，取消依赖子进程能够响应终止信号。
- 完成/失败的任务可以点「跨设备继续」。Relay 自动带上原始任务和摘要创建一个新任务。这是**上下文接力**，不是迁移正在运行的进程状态。
- Relay 保存设备名称、任务文本与运行日志；它不会收到电脑的 Codex/DSH 登录凭据。任务和日志可能包含敏感内容，务必使用 HTTPS、保护服务器和数据库。
- 手机端访问密钥存于浏览器当前标签页 `sessionStorage`，不上传到第三方站点。桌面 Bridge 的设备密钥保存在本机 `~/.aibot-link/bridge.json`。
- 配对码 8 位，10 分钟有效、一次性；删除设备立即使设备 token 失效。
- 原有 Android Aibot 的 RikkaHub 聊天记录**目前尚未同步**。V1.1 只做跨端任务状态、摘要和执行控制。

## 5. 测试

```bash
python3 -m unittest discover -s tests -v
node --check aibot_link/mobile.js
```

## 6. 与 Android 项目对接

在已有 `xiaoliu-android` 的稳定签名分支中，原有构建顺序最后增加：

```bash
python3 ../scripts/patch_aibot_v105.py
python3 ../aibot_link/android/patch_aibot_v110.py
```

注意本安装包的目录结构和远程 GitHub 仓库不同：请把 `aibot_link/android/` 放在仓库对应目录，才可运行该补丁。V1.1 仅在**取得 V1.0.5 相同签名证书**且构建验收通过后，才能覆盖旧版。不要用新的签名覆盖原应用。

---

这是一个可以联调的工程切片，不代表 Android APK、云端部署、Codex/DSH 实机联动全部完成。下一阶段可增加 WebSocket、任务中心长连接、设备级细粒度审批、完整会话持久化与助手能力注册表。
