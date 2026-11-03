#!/usr/bin/env python3
"""Pack the tested stdlib Bridge client as a Windows or macOS source distribution.

This is NOT an executable installer: Python 3.10+ and local Codex are prerequisites.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import argparse


def package(root: Path, target: str, output: Path):
    if target not in {'Windows', 'Mac'}:
        raise ValueError('unknown target')
    source = root / 'aibot-link-v1.1'
    required = [
        'README.md', 'aibot_link/__init__.py', 'aibot_link/bridge.py',
        'aibot_link/desktop.html',
        'start_windows.cmd' if target == 'Windows' else 'start_mac.command',
    ]
    assert all((source / p).is_file() for p in required), 'Bridge sources incomplete'
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, 'w', ZIP_DEFLATED, compresslevel=6) as z:
        for name in required:
            z.write(source / name, 'Aibot-Link/' + name)
        z.writestr('Aibot-Link/INSTALL.txt',
                   'Aibot Link V1.1 - ' + target + '\n'
                   'Requirements: Python 3.10+, Codex CLI installed and logged in.\n'
                   'Read README.md and pair with your own HTTPS Relay before starting.\n'
                   'This is a Python Bridge source bundle, not an EXE/APP installer.\n')
    with ZipFile(output) as z:
        assert z.testzip() is None, 'corrupt archive'
    print(f'Packaged {output} ({output.stat().st_size} bytes)')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--target', choices=['Windows', 'Mac'], required=True)
    p.add_argument('--root', type=Path, default=Path('.'))
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    name = args.output or Path('dist') / f'Aibot-Link-V1.1-{args.target}.zip'
    package(args.root, args.target, name)
