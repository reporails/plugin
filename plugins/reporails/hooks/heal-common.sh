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
