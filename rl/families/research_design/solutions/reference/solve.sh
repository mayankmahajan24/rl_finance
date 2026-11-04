#!/bin/bash
# Reference for Harbor's oracle: the build writes gold's answer into response.json beside this script.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "${APP_DIR:-/app}/output"
cp "$DIR/response.json" "${APP_DIR:-/app}/output/response.json"
