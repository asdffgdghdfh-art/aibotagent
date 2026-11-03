#!/usr/bin/env python3
"""Switch Jarvis Agent to a permanent release package and signing identity.
Apply after migrate_agent_v100.py, restore_jarvis_ui_v101.py and
polish_jarvis_v102.py. Credentials are read from local.properties in CI,
never committed as source code.
"""
from pathlib import Path
gradle=Path("app/build.gradle.kts")
s=gradle.read_text(encoding="utf-8")
for old,new in (
    ('applicationId = "com.jarvis.agent.ui102"','applicationId = "com.jarvis.agent"'),
    ('versionCode = 1002','versionCode = 1003'),
    ('versionName = "1.0.2-classic-ui"','versionName = "1.0.3-stable-signing"'),
):
    assert s.count(old)==1,(old,s.count(old))
    s=s.replace(old,new,1)
assert 'signingConfig = signingConfigs.getByName("release")' in s
# Release APK is intentionally unshrunk for initial reliable migration.
# R8 full-program optimization is not needed for functionality, and on hosted
# CI could delay this enormous Agent build for tens of minutes.
anchor='''        release {
            signingConfig = signingConfigs.getByName("release")
            optimization {
                enable = true
            }'''
replacement='''        release {
            signingConfig = signingConfigs.getByName("release")
            optimization {
                enable = false
            }'''
assert s.count(anchor)==1, ("release optimization",s.count(anchor))
s=s.replace(anchor,replacement,1)

gradle.write_text(s,encoding="utf-8")
print("Jarvis stable identity: com.jarvis.agent, versionCode 1003")
