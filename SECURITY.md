# Aibot security and release policy

- Never commit `*.p12`, `*.jks`, `*.keystore`, `local.properties`, `.env`, owner tokens, backups or Bridge `bridge.json`.
- Release APK signing credentials belong only in GitHub Actions repository Secrets: `JARVIS_SIGNING_KEYSTORE_BASE64` and `JARVIS_SIGNING_PASSWORD`. Do not write their values into build logs or artifacts.
- Without those secrets, CI may create an isolated **ephemeral-signed** `com.aibot.agent.ci` preview; this cannot replace an existing Aibot install.
- Bind Relay only to `127.0.0.1` behind TLS Nginx. Use HTTPS remotely and revoke compromised device identities.
- Desktop Bridge allows only declared project directories; Codex uses workspace-write sandbox. Experimental DSH is OFF until explicit approval and does not yet enforce per-command approval.
- Report exploitable vulnerabilities privately; never paste secrets into GitHub issues.
