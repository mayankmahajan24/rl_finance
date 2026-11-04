#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
python "$DIR/naive.py" --params "$DIR/params.json"
