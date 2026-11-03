#!/usr/bin/env python3
"""Prepare pinned Aibot Android source for a public CI runner.

All design patches run first. CI has two modes:
  ephemeral: use temporary CI key + isolated package identity to prevent false upgrades
  persistent: only with a private signing certificate from GitHub Actions secrets

Must run with src/ as current directory. Never reads or prints keystore passwords.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


def prepare(root: Path, mode: str):
    if mode not in {"ephemeral", "persistent"}:
        raise ValueError("mode must be ephemeral or persistent")
    gradle = root / "app/build.gradle.kts"
    content = gradle.read_text(encoding="utf-8")
    assert content.count('applicationId = "com.jarvis.agent"') == 1, "unexpected app id"
    assert content.count('versionCode = 1100') == 1, "unexpected version code"
    assert content.count('versionName = "1.1.0-aibot-link"') == 1, "unexpected version name"
    assert 'signingConfig = signingConfigs.getByName("release")' in content, "release signing not configured"
    assert (root / 'local.properties').is_file(), "CI did not provision local signing configuration"
    if mode == "ephemeral":
        content = content.replace('applicationId = "com.jarvis.agent"',
                                  'applicationId = "com.aibot.agent.ci"', 1)
        content = content.replace('versionName = "1.1.0-aibot-link"',
                                  'versionName = "1.1.0-aibot-link-ci"', 1)
    gradle.write_text(content, encoding="utf-8")
    changed = 0
    for g in root.rglob('build.gradle.kts'):
        if any(x in g.parts for x in ('.gradle', 'build', 'node_modules')):
            continue
        original = g.read_text(encoding="utf-8")
        after = original.replace('abiFilters += listOf("arm64-v8a", "x86_64")',
                                 'abiFilters += listOf("arm64-v8a")')
        if after != original:
            g.write_text(after, encoding="utf-8")
            changed += 1
    if mode == "ephemeral":
        labels = 0
        for strings in (root / 'app/src/main/res').glob('values*/strings.xml'):
            original = strings.read_text(encoding='utf-8')
            updated, n = re.subn(r'(<string name="app_name">)Aibot(</string>)',
                                 r'\1Aibot CI\2', original)
            if n:
                strings.write_text(updated, encoding='utf-8')
                labels += 1
        assert labels, "Aibot launcher label not found"
    print(f"CI Android mode={mode}, ABI=arm64-v8a, Gradle modules modified={changed}")
    print("Package identity:", "com.aibot.agent.ci" if mode == "ephemeral" else "com.jarvis.agent")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('ephemeral', 'persistent'), required=True)
    args = parser.parse_args()
    prepare(Path('.'), args.mode)
