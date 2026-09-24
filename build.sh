#!/usr/bin/env bash
# Build, test, and package the local platform binary.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "$(uname -s)" in
    Linux)  ASSET="script-runner-linux-x86_64"; BIN="script-runner" ;;
    Darwin) BIN="script-runner/script-runner"
            case "$(uname -m)" in
                arm64) ASSET="script-runner-macos-aarch64.tar.gz" ;;
                *)     ASSET="script-runner-macos-x86_64.tar.gz" ;;
            esac ;;
    MINGW*|MSYS*|CYGWIN*) ASSET="script-runner-windows-x86_64.zip"; BIN="script-runner/script-runner.exe" ;;
    *) echo "Unsupported build platform: $(uname -s)"; exit 1 ;;
esac

PY="${BUILD_PYTHON:-python3.12}"
command -v "$PY" >/dev/null || PY=python3
echo "=== Build platform: $ASSET  (interpreter: $(command -v "$PY"))"
"$PY" --version

cd "$HERE"
rm -rf .venv build dist
mkdir -p out
"$PY" -m venv .venv
VENV_PY=".venv/bin/python"
[ -x "$VENV_PY" ] || VENV_PY=".venv/Scripts/python.exe"
"$VENV_PY" -m pip install --quiet --no-deps -r requirements.txt --report out/install-report.json
"$VENV_PY" -m pip check
"$VENV_PY" release_materials.py prepare --report out/install-report.json

echo "=== PyInstaller"
"$VENV_PY" -m PyInstaller script-runner.spec --clean --noconfirm

echo "=== Smoke test"
"$VENV_PY" smoke_test.py "dist/$BIN"
# dist/script-runner is the executable, or on Windows and macOS the folder that holds it.
"$VENV_PY" release_materials.py package --asset "$ASSET" --binary "dist/script-runner"

echo "Release files: $HERE/out/release"
