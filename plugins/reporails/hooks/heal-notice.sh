#!/bin/sh
# PreToolUse hook: shows the heal write-scope notice once, before the first
# remedy agent starts. Never blocks; prints nothing on any other input.
exec 2>/dev/null
input=$(cat) || exit 0

printf '%s' "$input" | grep -Eq '"subagent_type"[[:space:]]*:[[:space:]]*"reporails:remedy"' || exit 0

session=$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1 | tr -c 'A-Za-z0-9_-' '_')
[ -n "$session" ] || session=nosession

# Project path as it appears (already JSON-escaped) in the dispatch prompt's leading "path:" line.
path=$(printf '%s' "$input" | sed -n 's/.*"prompt"[[:space:]]*:[[:space:]]*"path:[[:space:]]*//p' | head -n 1 | sed 's/\\\\/@RPBS@/g; s/\\"/@RPQ@/g; s/\\n.*//; s/".*//; s/@RPBS@/\\\\/g; s/@RPQ@/\\"/g')
case "$path" in
  ''|*[![:print:]]*) path="this project" ;;
esac
# A path ending in a single (unpaired) backslash would break the JSON string.
case $(printf '%s' "$path" | sed 's/\\\\//g') in
  *\\) path="this project" ;;
esac

marker="${TMPDIR:-/tmp}/reporails-heal-notice-$session"
[ -e "$marker" ] && exit 0
: > "$marker" || exit 0

printf '{"systemMessage": "Heal is rewriting instruction files in %s. Claude Code asks before each edit to an instruction file (a CLAUDE.md or AGENTS.md, or a file under .claude/), because those files change how your agent behaves. Allowing edits for this session at the first prompt lets the run continue without a prompt for each file."}\n' "$path"
exit 0
