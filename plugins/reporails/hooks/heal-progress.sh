#!/bin/sh
# PreToolUse / PostToolUse hook: prints one line per finished reporails:remedy
# agent and one line when a round of them is done. Never blocks; prints nothing
# on any other input, on a background launch, or on any failure.
exec 2>/dev/null
input=$(cat) || exit 0
. "$(dirname "$0")/heal-common.sh" || exit 0

heal_is_remedy "$input" || exit 0

event=$(printf '%s' "$input" | grep -Eo '"hook_event_name"[[:space:]]*:[[:space:]]*"(Pre|Post)ToolUse"' | head -n 1 | sed 's/.*"\(Pre\|Post\)ToolUse"/\1/')
[ -n "$event" ] || exit 0

id=$(printf '%s' "$input" | grep -Eo '"tool_use_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 | sed 's/.*:[[:space:]]*"//; s/"$//' | tr -c 'A-Za-z0-9_-' '_')
[ -n "$id" ] || id="none-$$"

# The leading "key: value" lines of the dispatch prompt, as they appear escaped in the JSON.
prompt_field() {
  printf '%s' "$input" | grep -Eo "\\\\n$1:[[:space:]]*[A-Za-z0-9_.-]+" | head -n 1 | sed "s/^.*$1:[[:space:]]*//"
}
order=$(prompt_field order)
kind=$(prompt_field kind)
[ -n "$order" ] || order="?"
[ -n "$kind" ] || kind="unknown"

dir="${TMPDIR:-/tmp}/reporails-heal-$(heal_session "$input")"
mkdir -p "$dir" || exit 0
batch="$dir/batch"
lock="$dir/lock.d"

# Atomic lock: mkdir succeeds for exactly one hook; a lock left by a crashed hook is taken over.
tries=0
until mkdir "$lock"; do
  tries=$((tries + 1))
  if [ "$tries" -gt 100 ]; then
    rmdir "$lock"
    mkdir "$lock" || exit 0
    break
  fi
  sleep 0.1 || sleep 1
done
trap 'rmdir "$lock"' EXIT

now=$(date +%s)

if [ "$event" = Pre ]; then
  printf '%s\t%s\t%s\t%s\tpending\n' "$id" "$order" "$kind" "$now" >> "$batch"
  exit 0
fi

# Decode the report text of the tool_response, then read its rows.
report=$(printf '%s' "$input" | awk '
  BEGIN { RS = "\001" }
  {
    s = $0
    if (!match(s, /"tool_response"/)) exit
    s = substr(s, RSTART + RLENGTH)
    if (!match(s, /"text"[ \t]*:[ \t]*"/)) exit
    s = substr(s, RSTART + RLENGTH)
    out = ""
    n = length(s)
    for (i = 1; i <= n; i++) {
      c = substr(s, i, 1)
      if (c == "\"") break
      if (c == "\\") {
        i++
        e = substr(s, i, 1)
        if (e == "n") c = "\n"
        else if (e == "t") c = " "
        else if (e == "r") c = ""
        else c = e
      }
      out = out c
    }
    print out
  }')

parsed=$(printf '%s\n' "$report" | awk '
  function clean(l) {
    gsub(/`/, "", l)
    sub(/^[ \t]*([-*•][ \t]+)?/, "", l)
    sub(/[ \t]+$/, "", l)
    return l
  }
  BEGIN { checks = "lost_instructions|polarity_flips|lost_named|detached_constraints|dangling_fragments|lost_context|removed_structure|moved_list_items|invented_named|repeated_named|added_instructions|relabelled_negative_headings|added_conditions|dropped_conditions|narrowed_instructions|hedge_made_absolute|padded_lines" }
  {
    l = clean($0)
    if (match(l, /^location[ \t]+[0-9]+[ \t]+/)) { element = substr(l, RSTART + RLENGTH); next }
    if (l ~ /^[^|]+\|[ \t]*(accepted|restored|refused)[ \t]*\|/) {
      rows++
      split(l, f, /[ \t]*\|[ \t]*/)
      status[rows] = f[2]; score[rows] = f[3]; tail[rows] = ""
      next
    }
    if (rows > 0 && l != "") {
      if (tail[rows] == "") tail[rows] = l
      rest[rows] = rest[rows] " " l
    }
  }
  END {
    if (rows == 0) exit
    first_refused = first_restored = 0
    for (r = 1; r <= rows; r++) {
      if (status[r] == "refused" && !first_refused) first_refused = r
      if (status[r] == "restored" && !first_restored) first_restored = r
    }
    if (first_refused) {
      st = "refused"; d = tail[first_refused]
      sub(/^[Rr]eason:[ \t]*/, "", d)
      if (length(d) > 200) d = substr(d, 1, 200)
      if (d == "") d = "no reason given"
    } else if (first_restored) {
      st = "restored"; d = ""
      for (r = 1; r <= rows; r++) {
        if (status[r] != "restored") continue
        t = rest[r]
        while (match(t, checks)) {
          name = substr(t, RSTART, RLENGTH)
          if (index(", " d ", ", ", " name ", ") == 0) d = (d == "" ? name : d ", " name)
          t = substr(t, RSTART + RLENGTH)
        }
      }
      if (d == "") d = (tail[first_restored] != "" ? tail[first_restored] : "score " score[first_restored])
      if (length(d) > 200) d = substr(d, 1, 200)
    } else {
      st = "accepted"; d = ""
      for (r = 1; r <= rows; r++) d = (d == "" ? score[r] : d ", " score[r])
      d = "score " d
    }
    print element; print st; print d
  }')
[ -n "$parsed" ] || exit 0
element=$(printf '%s\n' "$parsed" | sed -n 1p)
status=$(printf '%s\n' "$parsed" | sed -n 2p)
detail=$(printf '%s\n' "$parsed" | sed -n 3p)
[ -n "$element" ] || element="$kind"

# Record the result; a hand-back with no recorded dispatch counts as its own one-location batch.
grep -q "^$id	" "$batch" 2>/dev/null || printf '%s\t%s\t%s\t%s\tpending\n' "$id" "$order" "$kind" "$now" >> "$batch"
awk -F '\t' -v OFS='\t' -v id="$id" -v st="$status" '$1 == id { $5 = st } { print }' "$batch" > "$batch.new" && mv "$batch.new" "$batch"

message="$order $element — $status ($detail)"
if ! grep -q "	pending$" "$batch"; then
  round=$(LC_ALL=C awk -F '\t' -v now="$now" '
    NR == 1 { start = $4 }
    { n[$5]++; if (!($3 in seen)) { seen[$3] = 1; kinds = (kinds == "" ? $3 : kinds ", " $3) } }
    END { printf "Round %s done — %d accepted, %d restored, %d refused, %.1f min", kinds, n["accepted"], n["restored"], n["refused"], (now - start) / 60 }' "$batch")
  message="$message
$round"
  rm -f "$batch"
fi

printf '%s' "$message" | tr -d '\000-\010\013-\037' | awk '
  BEGIN { printf "{\"systemMessage\": \"" }
  { gsub(/\\/, "\\\\"); gsub(/"/, "\\\""); printf "%s%s", (NR > 1 ? "\\n" : ""), $0 }
  END { printf "\"}\n" }'
exit 0
