#!/bin/bash
# One Opus task run on the subscription (ANTHROPIC_API_KEY unset). Airgapped: web tools disabled, and every shell
# command the agent runs goes through offline.sh (its own network namespace: nothing reachable, proxy or not).
t=$1; R=/home/user/anomaly_hard_runs; cd $R/$t
env -u ANTHROPIC_API_KEY -u CLAUDE_ADDITIONAL_DIRECTORIES -u CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD \
  CLAUDE_CODE_SHELL_PREFIX=$R/offline.sh \
  timeout 4h claude -p --model claude-opus-5-5 --allowedTools "Bash Read Write Edit Glob Grep" \
  --disallowedTools "WebFetch,WebSearch" --output-format stream-json --verbose \
  -- "$(cat $R/prompt-$t.txt)" > $R/stream-$t.jsonl 2> $R/stderr-$t.txt < /dev/null
echo "exit $?" >> $R/stderr-$t.txt
