#!/bin/bash
# One Opus task run that can see nothing but its own run folder and the instruction. Usage: run_blind.sh RUN [PROMPT]
#   RUN     folder name under $R (default /home/user/anomaly_hard_runs) holding app/data, app/solution, app/output
#   PROMPT  text to send instead of $R/prompt-RUN.txt (used by the self-check, which asks the agent what it can see)
#   MODEL   (environment) the model to run; default claude-opus-5-5
#
# On top of run.sh (subscription login, no web tools, every shell command in its own empty network namespace):
#   * the whole agent process, not only its shell, runs in a private mount namespace in which these are empty:
#       the repository (grader, builder, answer keys, every solution), every other run's folder and transcript,
#       /tmp (other sessions' scratch files and their messaging sockets) and Claude Code's saved transcripts;
#   * it also has its own process namespace, so no other process (and no other process's view of the disk) is
#     reachable through /proc;
#   * the agent has six tools and no others (--tools): no skills, no sub-agents, no messaging, no connectors;
#   * the folders it may not see are checked from inside the namespace before the agent starts; the run aborts
#     if any of them still has content.
set -euo pipefail
t=$1
R=${R:-/home/user/anomaly_hard_runs}
REPO=${REPO:-/home/user/rl_finance}
prompt=${2:-$(cat "$R/prompt-$t.txt")}
out=${OUT:-$R/stream-$t.jsonl}
err=${ERR:-$R/stderr-$t.txt}
export BLIND_MODEL="${MODEL:-claude-opus-5-5}" BLIND_RUN="$R/$t" BLIND_R="$R" BLIND_REPO="$REPO" BLIND_PROMPT="$prompt" BLIND_VENV="${VENV:-/home/user/venvpin}"
# the transcript and error log are opened here, outside the namespace, so they land in the real folder
exec unshare -m -p -f --mount-proc -- /bin/bash -c '
  set -euo pipefail
  mount --make-rprivate /
  mkdir -p /mnt/blind_run /mnt/blind_sh
  mount --bind "$BLIND_RUN" /mnt/blind_run                      # keep hold of the run folder and the shell prefix
  cp "$BLIND_R/offline.sh" /mnt/blind_sh.tmp && chmod +x /mnt/blind_sh.tmp
  for d in "$BLIND_REPO" "$BLIND_R" /tmp /root/.claude/projects /root/.claude/backups /root/.claude/shell-snapshots; do
    [ -d "$d" ] && mount -t tmpfs -o mode=1777 tmpfs "$d"
  done
  mkdir -p "$BLIND_RUN" && mount --bind /mnt/blind_run "$BLIND_RUN"
  cp /mnt/blind_sh.tmp "$BLIND_R/offline.sh"
  for d in "$BLIND_REPO" /root/.claude/projects; do            # nothing of ours may be left in view
    [ -z "$(ls -A "$d" 2>/dev/null)" ] || { echo "not blind: $d has content" >&2; exit 97; }
  done
  [ "$(ls "$BLIND_R")" = "$(printf "offline.sh\n%s" "$(basename "$BLIND_RUN")")" ] || { echo "not blind: other runs in view" >&2; exit 97; }
  cd "$BLIND_RUN"
  env -u ANTHROPIC_API_KEY -u CLAUDE_ADDITIONAL_DIRECTORIES -u CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD \
    -u BLIND_MODEL -u BLIND_PROMPT -u BLIND_REPO -u BLIND_R -u BLIND_RUN -u BLIND_VENV \
    PATH="$BLIND_VENV/bin:$PATH" CLAUDE_CODE_SHELL_PREFIX="$BLIND_R/offline.sh" \
    timeout 4h claude -p --model "$BLIND_MODEL" --tools "Bash,Read,Write,Edit,Glob,Grep" \
    --allowedTools "Bash Read Write Edit Glob Grep" --disallowedTools "WebFetch,WebSearch" \
    --output-format stream-json --verbose -- "$BLIND_PROMPT" < /dev/null
  echo "exit $?" >&2
' > "$out" 2> "$err"
