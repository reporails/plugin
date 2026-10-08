#!/bin/sh
# Sourced by the heal hooks. One owner for reading a hook's JSON input
# (no jq: it must run under Git Bash on Windows too).

# heal_is_remedy <input>: succeeds when the input is for the reporails:remedy agent.
heal_is_remedy() {
  printf '%s' "$1" | grep -Eq '"(subagent_type|agentType)"[[:space:]]*:[[:space:]]*"reporails:remedy"'
}

# heal_session <input>: the session id, safe to use in a file name.
heal_session() {
  _session=$(printf '%s' "$1" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1 | tr -c 'A-Za-z0-9_-' '_')
  [ -n "$_session" ] || _session=nosession
  printf '%s' "$_session"
}

# heal_event <input>: Pre or Post, empty for any other hook event.
heal_event() {
  printf '%s' "$1" | grep -Eo '"hook_event_name"[[:space:]]*:[[:space:]]*"(Pre|Post)ToolUse"' | head -n 1 | sed -E 's/.*"(Pre|Post)ToolUse"$/\1/'
}

# heal_tool_use_id <input>: the call's id, safe to use in a file name.
heal_tool_use_id() {
  printf '%s' "$1" | grep -Eo '"tool_use_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 | sed -E 's/.*:[[:space:]]*"//; s/"$//' | tr -c 'A-Za-z0-9_-' '_'
}

# heal_prompt_field <input> <key>: the value of a "key: value" line of the dispatch prompt (escaped in the JSON).
heal_prompt_field() {
  printf '%s' "$1" | grep -Eo "\\\\n$2:[[:space:]]*[A-Za-z0-9_.-]+" | head -n 1 | sed "s/^.*$2:[[:space:]]*//"
}
