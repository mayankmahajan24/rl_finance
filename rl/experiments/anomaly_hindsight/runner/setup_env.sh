#!/bin/bash
# Local stand-in for the task image (environment/Dockerfile): a Python 3.12 venv with exactly the pinned packages.
# Task runs put it first on PATH (run.sh); grade with its python too, since the grader runs the solution with the
# interpreter it was started with. Usage: setup_env.sh [DIR] (default /home/user/venvpin)
set -euo pipefail
V=${1:-/home/user/venvpin}
uv venv -q --python 3.12 "$V"
VIRTUAL_ENV="$V" uv pip install -q --no-deps -r "$(dirname "$0")/../environment/requirements.lock"
"$V/bin/python" -c "import pandas, ruptures, Rbeast, prophet, statsforecast, statsmodels, sklearn, matplotlib; print('ok')"
