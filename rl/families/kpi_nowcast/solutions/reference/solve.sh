#!/bin/bash
# Reference for Harbor's oracle: the build writes the gold forecast into answer.md beside this script.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "${APP_DIR:-/app}/output"
cp "$DIR/answer.md" "${APP_DIR:-/app}/output/answer.md"
