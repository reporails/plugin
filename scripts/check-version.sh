#!/usr/bin/env bash
# Checks the plugin's version fields (and with --publish its cli pins) against the release branch name.
set -euo pipefail

CEILING="<0.7"
PUBLISH=0

case "${1:-}" in
  "") ;;
  --publish) PUBLISH=1 ;;
  *) echo "Usage: scripts/check-version.sh [--publish]" >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then
  echo "Usage: scripts/check-version.sh [--publish]" >&2
  exit 2
fi

cd "$(git rev-parse --show-toplevel)"
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if ! [[ "$BRANCH" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Version check applies only on a release branch (X.Y.Z); on '$BRANCH', skipped."
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required to read the plugin manifests and was not found." >&2
  exit 1
fi

PROBLEMS=()

for f in plugins/reporails/.claude-plugin/plugin.json \
         plugins/reporails/.codex-plugin/plugin.json \
         plugins/reporails/plugin.json; do
  found=$(jq -r .version "$f" 2>/dev/null || echo "<unreadable>")
  if [ "$found" != "$BRANCH" ]; then
    PROBLEMS+=("$f: version is $found, expected $BRANCH")
  fi
done

SKILL=plugins/reporails/skills/ails/SKILL.md
found=$(sed -n 's/^  version: "\(.*\)"[[:space:]]*$/\1/p' "$SKILL" | head -n 1)
if [ "$found" != "$BRANCH" ]; then
  PROBLEMS+=("$SKILL: metadata.version is ${found:-<missing>}, expected $BRANCH")
fi

if [ "$PUBLISH" -eq 1 ]; then
  EXPECTED="reporails-cli>=$BRANCH,$CEILING"
  for f in plugins/reporails/.mcp.json \
           plugins/reporails/mcp.json \
           plugins/reporails/mcp_config.json \
           README.md \
           plugins/reporails/skills/ails/workflows/setup.md; do
    hits=$(grep -noE "reporails-cli>=[^'\"\` )]*" "$f" 2>/dev/null || true)
    if [ -z "$hits" ]; then
      PROBLEMS+=("$f: no reporails-cli pin found, expected $EXPECTED")
      continue
    fi
    while IFS= read -r hit; do
      line=${hit%%:*}
      pin=${hit#*:}
      if [ "$pin" != "$EXPECTED" ]; then
        PROBLEMS+=("$f:$line: pin is $pin, expected $EXPECTED")
      fi
    done <<< "$hits"
  done
fi

if [ "${#PROBLEMS[@]}" -gt 0 ]; then
  printf '%s\n' "${PROBLEMS[@]}" >&2
  echo "Version check failed: ${#PROBLEMS[@]} problem(s) against release $BRANCH." >&2
  exit 1
fi

if [ "$PUBLISH" -eq 1 ]; then
  echo "Version check passed: fields and cli pins match $BRANCH."
else
  echo "Version check passed: fields match $BRANCH."
fi
