# Aibot Agent · 跨设备智能体

> Android Aibot + Windows/macOS Bridge + Aibot Link Relay，共享设备状态、任务、日志和审批。
>
> **开发状态：V1.1 MVP。** Relay 与桌面 Bridge 可运行；Android 集成代码已准备，APK 构建和真实设备联调以 Actions 日志/Artifacts 为准。此仓库不包含任何私人账号凭据。

## 架构

```
Aibot Android / 手机浏览器
     │ HTTPS
     ▼
Aibot Link Relay (Python / SQLite / Nginx TLS)
     ▲                    ▲
     │ outbound HTTPS     │ outbound HTTPS
Windows Bridge       macOS Bridge
Codex CLI / DSH      Codex CLI / DSH
```

- [跨设备工程与使用说明](aibot-link-v1.1/README.md)：中继服务、手机控制台、Windows/Mac Bridge、测试和部署。
- [Android 补丁脚本](scripts/)：在指定版本的 [RikkaHub Agent](https://github.com/ExTV/rikkahub-agent) 源码上复现 Aibot V1.1。
- [自动构建](.github/workflows/)：跨设备协议单元测试、桌面安装包，以及 Android 可安装测试包。
- [安全约束](SECURITY.md)：不公开密钥、限制可执行项目、保留人工批准机制。

### 下载构建产物

打开本仓库的 **Actions**，进入最近一次成功执行的 Android/Bridge 工作流，在页面底部 **Artifacts** 下载对应 APK 或 Windows/Mac 压缩包。

**关于覆盖升级：** 若 GitHub Secrets 尚未配置既有签名，CI 生成的是独立测试包，不能覆盖你此前安装的 Aibot V1.0.5。千万不要卸载旧版来“强制升级”。正式版需要相同应用 ID 和兼容的永久签名证书。

### 技术范围

当前已支持设备配对、心跳、项目目录白名单、自动选设备、任务队列、Codex 沙箱执行、状态日志、取消任务和上下文接力。DSH 默认关闭，不能把 MVP 当作已实现进程内部的逐命令权限审批。原有手机 RikkaHub 聊天历史尚未同步。

## 构建与开发

Python 3.10+（Relay/Bridge）；Android 需 JDK 21、Bun、pnpm、Android SDK。CI 会拉取固定的上游 tag，按顺序应用本仓库的补丁，不上传私人用户文件。

```sh
cd aibot-link-v1.1
python3 -m unittest discover -s tests -v
node --check aibot_link/mobile.js
```

## 开源许可与声明

Android 底座基于 [ExTV/rikkahub-agent](https://github.com/ExTV/rikkahub-agent)，它继承 RikkaHub 的 **GNU AGPL-3.0** 许可证。保留上游版权及许可条款；本仓库相应衍生修改按 AGPL-3.0 提供。项目与上游维护者无关联，属于非官方改造。详见 [LICENSE](LICENSE) 和 [NOTICE.md](NOTICE.md)。

请勿将个人服务令牌、签名私钥、`local.properties`、`.env` 或聊天/运行日志提交到公开仓库。
