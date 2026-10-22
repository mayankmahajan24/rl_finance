#!/bin/bash
set -euo pipefail
APP="${APP_DIR:-/app}"; DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$APP/solution"
cp "$DIR/score.py" "$DIR/anomaly_model.py" "$APP/solution/"
