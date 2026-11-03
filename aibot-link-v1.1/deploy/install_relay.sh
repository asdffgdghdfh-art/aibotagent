#!/usr/bin/env bash
set -euo pipefail
if [[ "$EUID" -ne 0 ]]; then echo 'Run: sudo bash deploy/install_relay.sh'; exit 1; fi
HERE="$(cd "$(dirname "$0")/.." && pwd)"
command -v python3 >/dev/null || { echo 'Python 3 not installed'; exit 1; }
id aibotlink >/dev/null 2>&1 || useradd --system --home-dir /var/lib/aibot-link --shell /usr/sbin/nologin aibotlink
install -d -m 0755 /opt/aibot-link
install -d -m 0700 -o aibotlink -g aibotlink /var/lib/aibot-link
install -d -m 0700 /etc/aibot-link
cp -R "$HERE/aibot_link" /opt/aibot-link/
find /opt/aibot-link/aibot_link -type f -exec chmod 0644 {} +
if [[ ! -s /etc/aibot-link/env ]]; then
  TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(40))')"
  printf 'AIBOT_OWNER_TOKEN=%s\n' "$TOKEN" > /etc/aibot-link/env
  printf '%s\n' "$TOKEN" > /etc/aibot-link/owner-token
  chmod 0600 /etc/aibot-link/env /etc/aibot-link/owner-token
  echo 'New owner token saved to /etc/aibot-link/owner-token (root-only).'
else
  echo 'Existing owner token preserved.'
fi
install -m 0644 "$HERE/deploy/aibot-link-relay.service" /etc/systemd/system/aibot-link-relay.service
systemctl daemon-reload
systemctl enable --now aibot-link-relay
systemctl restart aibot-link-relay
systemctl --no-pager status aibot-link-relay | head -n 17
echo 'Relay installed on 127.0.0.1:8787. Configure Nginx HTTPS separately.'
