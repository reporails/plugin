#!/bin/sh
# PreToolUse / PostToolUse / UserPromptSubmit hook: prints one line per finished
# reporails:remedy agent and one line when a round of them is done. A foreground
# agent's report arrives in its PostToolUse; a background agent's arrives as a
# <task-notification> prompt. Never blocks; prints nothing on any other input,
# on a background launch, or on any failure.
exec 2>/dev/null
input=$(cat) || exit 0
common="$(dirname "$0")/heal-common.sh"
# A missing helper must not abort the hook: exit 2 from a PreToolUse hook blocks the dispatch.
[ -r "$common" ] || exit 0
. "$common"

event=$(heal_event "$input")
[ -n "$event" ] || exit 0

case "$event" in
  Prompt)
    # A finished background agent reaches the main session as a <task-notification> prompt.
    printf '%s' "$input" | grep -q '<task-notification>' || exit 0
    ;;
  *)
    heal_is_remedy "$input" || exit 0
    # A background launch answers at once with no report: the dispatch stays pending until its notification.
    if [ "$event" = Post ] && heal_is_async_launch "$input"; then exit 0; fi
    ;;
esac

id=$(heal_tool_use_id "$input")
[ -n "$id" ] || id="none-$$"

order=$(heal_prompt_field "$input" order)
kind=$(heal_prompt_field "$input" kind)
[ -n "$order" ] || order="?"
[ -n "$kind" ] || kind="unknown"

dir="${TMPDIR:-/tmp}/reporails-heal-$(heal_session "$input")"
batch="$dir/batch"
# A notification can only belong to a recorded batch: nothing to decode without one.
if [ "$event" = Prompt ]; then [ -f "$batch" ] || exit 0; fi
mkdir -p "$dir" || exit 0
lock="$dir/lock.d"

# Atomic lock: mkdir succeeds for exactly one hook, which records its pid. A lock whose holder is
# gone is taken over by renaming it away (one waiter wins the rename); a live holder is waited on,
# and after a minute the hook gives up without doing anything.
tries=0
until mkdir "$lock"; do
  tries=$((tries + 1))
  [ "$tries" -le 600 ] || exit 0
  holder=$(cat "$lock/pid")
  if [ -n "$holder" ] && ! kill -0 "$holder" || { [ -z "$holder" ] && [ "$tries" -gt 300 ]; }; then
    mv "$lock" "$lock.stale.$$" && rm -rf "$lock.stale.$$"
    continue
  fi
  sleep 0.1 || sleep 1
done
trap 'rm -rf "$lock"' EXIT
trap 'exit 0' HUP INT TERM
printf '%s' "$$" > "$lock/pid"

now=$(date +%s)

if [ "$event" = Pre ]; then
  # Entries from well before this dispatch burst belong to an earlier round that will not close.
  if [ -f "$batch" ]; then
    awk -F '\t' -v cutoff="$((now - 60))" '$4 >= cutoff' "$batch" > "$batch.new" && mv "$batch.new" "$batch"
  fi
  printf '%s\t%s\t%s\t%s\tpending\n' "$id" "$order" "$kind" "$now" >> "$batch"
  exit 0
fi

# heal_record <id> <order> <kind> <report>: reads one agent's report, records its result in the batch,
# appends its location line to $out, and, when no dispatch of the batch is still pending, the round-close line.
heal_record() {
  _id=$1 _order=$2 _kind=$3
  parsed=$(printf '%s\n' "$4" | awk '
  function clean(l) {
    gsub(/`/, "", l)
    sub(/^[ \t]*([-*•|][ \t]*)?/, "", l)
    sub(/[ \t|]+$/, "", l)
    return l
  }
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
      st = "restored"; d = tail[first_restored]
      if (length(d) > 200) d = substr(d, 1, 200)
      if (d == "") d = "score " score[first_restored]
    } else {
      st = "accepted"; d = ""
      for (r = 1; r <= rows; r++) d = (d == "" ? score[r] : d ", " score[r])
      d = "score " d
    }
    print element; print st; print d
  }')
  [ -n "$parsed" ] || return 0
  element=$(printf '%s\n' "$parsed" | sed -n 1p)
  status=$(printf '%s\n' "$parsed" | sed -n 2p)
  detail=$(printf '%s\n' "$parsed" | sed -n 3p)
  [ -n "$element" ] || element="$_kind"

  # Record the result; a hand-back with no recorded dispatch counts as its own one-location batch.
  grep -q "^$_id	" "$batch" 2>/dev/null || printf '%s\t%s\t%s\t%s\tpending\n' "$_id" "$_order" "$_kind" "$now" >> "$batch"
  awk -F '\t' -v OFS='\t' -v id="$_id" -v st="$status" '$1 == id { $5 = st } { print }' "$batch" > "$batch.new" && mv "$batch.new" "$batch"

  message="$_order $element — $status ($detail)"
  if ! grep -q "	pending$" "$batch"; then
    round=$(LC_ALL=C awk -F '\t' -v now="$now" '
      NR == 1 { start = $4 }
      { n[$5]++; if (!($3 in seen)) { seen[$3] = 1; kinds = (kinds == "" ? $3 : kinds ", " $3) } }
      END { printf "Round %s done — %d accepted, %d restored, %d refused, %.1f min", kinds, n["accepted"], n["restored"], n["refused"], (now - start) / 60 }' "$batch")
    message="$message
$round"
    rm -f "$batch"
  fi
  out="${out:+$out
}$message"
}

out=""
if [ "$event" = Prompt ]; then
  heal_split_notifications "$(heal_prompt_text "$input")" "$dir"
  for note in "$dir"/note.*; do
    [ -f "$note" ] || continue
    nid=$(heal_tool_use_id "\"tool_use_id\":\"$(sed -n 1p "$note")\"")
    # Only a recorded dispatch still pending is read; its order and kind come from the batch.
    row=$(grep "^$nid	.*	pending$" "$batch" 2>/dev/null | head -n 1)
    if [ -n "$row" ]; then
      heal_record "$nid" "$(printf '%s' "$row" | cut -f2)" "$(printf '%s' "$row" | cut -f3)" "$(sed 1d "$note")"
    fi
    rm -f "$note"
  done
else
  heal_record "$id" "$order" "$kind" "$(heal_report_text "$input")"
fi
[ -n "$out" ] || exit 0
message=$out

printf '%s' "$message" | tr -d '\000-\010\013-\037' | awk '
  BEGIN { printf "{\"systemMessage\": \"" }
  { gsub(/\\/, "\\\\"); gsub(/"/, "\\\""); printf "%s%s", (NR > 1 ? "\\n" : ""), $0 }
  END { printf "\"}\n" }'
exit 0
