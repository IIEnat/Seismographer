#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.9+ not found."; exit 1
fi
python3 -m pip install --upgrade pip >/dev/null
python3 -m pip install -r requirements.txt
python3 app_launcher.py
