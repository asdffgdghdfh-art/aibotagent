#!/usr/bin/env python3
"""Build the permanent com.jarvis.agent package with the fast debug task,
but with the *same persistent release signing certificate* as future releases.
The APK is debuggable, so it is for initial internal rollout, not store release.
"""
from pathlib import Path
p=Path("app/build.gradle.kts")
s=p.read_text(encoding="utf-8")
old='''        debug {
            applicationIdSuffix = ".debug"'''
new='''        debug {
            applicationIdSuffix = ""
            signingConfig = signingConfigs.getByName("release")'''
assert s.count(old)==1,("debug build type",s.count(old))
s=s.replace(old,new,1)
assert 'applicationId = "com.jarvis.agent"' in s
assert 'versionCode = 1003' in s
p.write_text(s,encoding="utf-8")
print("Jarvis V1.0.3 fast build: fixed com.jarvis.agent, release certificate, assembleDebug")
