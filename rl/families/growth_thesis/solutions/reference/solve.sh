#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
python "$DIR/thesis.py" --params "$DIR/params.json"
