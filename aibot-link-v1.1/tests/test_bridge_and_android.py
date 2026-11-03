import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aibot_link.bridge import parse_projects, codex_command, capabilities

ROOT=Path(__file__).resolve().parents[1]

class BuildTests(unittest.TestCase):
    def test_project_allowlist(self):
        with tempfile.TemporaryDirectory() as d:
            projects=parse_projects(['football='+d])
            self.assertEqual(Path(projects['football']),Path(d).resolve())
            with self.assertRaises(ValueError):parse_projects(['no=/bad/nonexistent/path'])
    def test_codex_sandbox_never_bypass(self):
        args=codex_command('/workspace','fix tests')
        self.assertIn('workspace-write',args)
        self.assertIn('--json',args)
        self.assertIn('never',args)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',args)
        self.assertNotIn('--yolo',args)
    def test_android_patch_has_exact_entry_and_identity(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            src=base/'src';home=src/'app/src/main/java/me/rerere/rikkahub/jarvis/JarvisAgentHomeActivity.kt'
            home.parent.mkdir(parents=True)
            home.write_text('''import android.content.Intent
class JarvisAgentHomeActivity {
                JarvisMenuLine("Agent 应用设置", "↗", ink, subtle) {
                    menuOpen = false
                    openChat()
                }
}
''')
            manifest=src/'app/src/main/AndroidManifest.xml'
            manifest.write_text('''<application>
    <activity android:name=".jarvis.JarvisAgentHomeActivity" />
</application>''')
            gradle=src/'app/build.gradle.kts'
            gradle.write_text('''applicationId = "com.jarvis.agent.v104preview"
versionCode = 1005
versionName = "1.0.5-aibot"
signingConfig = signingConfigs.getByName("release")
''')
            android=base/'aibot_link/android';android.mkdir(parents=True)
            (android/'AibotLinkActivity.kt').write_bytes((ROOT/'android/AibotLinkActivity.kt').read_bytes())
            cp=subprocess.run([sys.executable,str(ROOT/'android/patch_aibot_v110.py')],cwd=src,capture_output=True,text=True)
            self.assertEqual(cp.returncode,0,cp.stderr+cp.stdout)
            self.assertIn('我的设备 · Aibot Link',home.read_text())
            self.assertIn('android:exported="false"',manifest.read_text())
            self.assertIn('versionCode = 1100',gradle.read_text())
            self.assertIn('com.jarvis.agent.v104preview',gradle.read_text())
            self.assertTrue((home.parent/'AibotLinkActivity.kt').is_file())
            cp2=subprocess.run([sys.executable,str(ROOT/'android/patch_aibot_v110.py')],cwd=src,capture_output=True,text=True)
            self.assertNotEqual(cp2.returncode,0,'Patch must refuse a second unsafe run')

if __name__=='__main__':unittest.main()
