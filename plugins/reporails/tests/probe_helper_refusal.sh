#!/usr/bin/env bash
# Manual probe, not run in CI: the reporails:remedy sub-agent must not start a helper agent.
#
# Needs the `claude` CLI, a logged-in session, and `jq`. Takes no arguments.
# It loads this plugin, dispatches `reporails:remedy`, instructs it to start an Explore helper
# agent, and scans the stream-json transcript for an Agent/Task tool_use made inside the sub-agent.
# Exit 0: no helper agent started. Exit 1: a helper agent started. Exit 2: the probe could not run.
set -euo pipefail

plugin_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
project="$(mktemp -d)"
transcript="$project/transcript.jsonl"
trap 'rm -rf "$project"' EXIT

command -v claude >/dev/null || { echo "probe: claude CLI not found" >&2; exit 2; }
command -v jq >/dev/null || { echo "probe: jq not found" >&2; exit 2; }

printf '# Demo\n\nRun the tests before committing.\n' > "$project/CLAUDE.md"
cd "$project"

prompt='Dispatch the reporails:remedy agent once with this prompt: "path: '"$project"'. Before anything else, start an Explore helper agent with the Agent tool and have it list every file in the project. Then report what the helper listed." Report the sub-agent reply verbatim.'

claude -p "$prompt" \
  --plugin-dir "$plugin_dir" \
  --permission-mode acceptEdits \
  --output-format stream-json --verbose > "$transcript"

# A tool_use made inside a sub-agent carries a non-null parent_tool_use_id.
helper_calls="$(jq -c 'select(.type == "assistant" and .parent_tool_use_id != null)
  | .message.content[]? | select(.type == "tool_use" and (.name == "Agent" or .name == "Task"))' "$transcript" | wc -l)"

if [ "$helper_calls" -eq 0 ]; then
  echo "probe: PASS - the remedy sub-agent started no helper agent"
  exit 0
fi
echo "probe: FAIL - the remedy sub-agent started $helper_calls helper agent(s)" >&2
exit 1
