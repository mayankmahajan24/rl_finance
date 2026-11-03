#!/bin/bash
# Create .oauth.env so Harbor can run Claude Code on your Claude subscription instead of the API.
# The token is read at a hidden prompt and written straight to the file; it is never echoed.
set -euo pipefail
cd "$(dirname "$0")"
echo "Step 1/2: log in to your Claude account. When it finishes, copy the token it prints (starts with sk-ant-oat)."
claude setup-token
echo
read -rs -p "Step 2/2: paste the token here and press Enter (input is hidden): " T
echo
case "$T" in
  sk-ant-oat*) ;;
  *) echo "That doesn't look like a setup-token (expected it to start with sk-ant-oat). Nothing saved."; exit 1 ;;
esac
umask 077
printf 'CLAUDE_CODE_OAUTH_TOKEN=%s\n' "$T" > .oauth.env
unset T
echo "saved to $(pwd)/.oauth.env (permissions 600, git-ignored)"
