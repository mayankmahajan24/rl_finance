#!/bin/bash
# Claude Code shell prefix (CLAUDE_CODE_SHELL_PREFIX) for task runs: every command the agent runs has no network at all.
# Claude Code passes the whole command line as one string.
exec unshare -n -- /bin/bash -c "$*"
