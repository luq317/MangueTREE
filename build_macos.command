#!/bin/bash
# Build MangueTREE for macOS. Requires Python 3.11+.
# To run: in Terminal, "chmod +x build_macos.command" and then double-click it,
# or run "bash build_macos.command" inside this folder.
set -e
cd "$(dirname "$0")"
echo "=== MangueTREE - macOS build ==="
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt pyinstaller
python3 -m pip install --no-deps .
pyinstaller --noconfirm MangueTREE.spec
echo ""
echo "Done! The application is at: dist/MangueTREE.app"
echo "Compress MangueTREE.app to distribute it."
