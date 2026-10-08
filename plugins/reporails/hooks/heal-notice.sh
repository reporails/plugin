#!/bin/sh
# PreToolUse hook: shows the heal write-scope notice once, before the first
# remedy agent starts. Never blocks; prints nothing on any other input.
exec 2>/dev/null
input=$(cat) || exit 0
common="$(dirname "$0")/heal-common.sh"
# A missing helper must not abort the hook: exit 2 from a PreToolUse hook blocks the dispatch.
[ -r "$common" ] || exit 0
. "$common"

heal_is_remedy "$input" || exit 0
session=$(heal_session "$input")

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

printf '{"systemMessage": "Heal is rewriting instruction files in %s. Claude Code asks before each edit under .claude/, and outside accept-edits mode before each edit to a CLAUDE.md or AGENTS.md, because those files change how your agent behaves. At the first prompt for a .claude/ file, choose \\"Yes, and allow Claude to edit files in this project'"'"'s .claude folder for this session\\" and the rest of the run'"'"'s .claude/ edits go through without a prompt for each file."}\n' "$path"
exit 0
