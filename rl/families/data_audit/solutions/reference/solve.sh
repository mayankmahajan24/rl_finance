#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
python "$DIR/audit.py"
APP="${APP_DIR:-/app}"; mkdir -p "$APP/output"; cp "$DIR/writeup.md" "$APP/output/"
