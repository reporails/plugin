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
  # Rows of another kind, far older than any round, or for this same order belong to an earlier round
  # that will not close (an order is dispatched once per round). The incoming kind's other pending rows
  # stay: a client may hold back a dispatch for minutes.
  if [ -f "$batch" ]; then
    awk -F '\t' -v cutoff="$((now - 900))" -v kind="$kind" -v order="$order" '$3 == kind && $4 >= cutoff && $2 != order' "$batch" > "$batch.new" && mv "$batch.new" "$batch"
  fi
  printf '%s\t%s\t%s\t%s\tpending\n' "$id" "$order" "$kind" "$now" >> "$batch"
  exit 0
fi

# heal_record <id> <order> <kind> <report>: reads one agent's report, records its result in the batch,
# appends its location line to $out, and, when no dispatch of the batch is still pending, the round-close line.
heal_record() {
  _id=$1 _order=$2 _kind=$3
  # The only line read is the report's `outcome: <order> | <element> | <accepted, restored or refused> | <detail>`.
  # A hand-back without a valid one is recorded as refused, so the round always closes.
  # The detail is printed as the agent gave it; only the line's own framing is removed.
  parsed=$(printf '%s\n' "$4" | awk '
  function strip_end(ch, n) {
    while (n > 0 && substr(l, length(l), 1) == ch) { l = substr(l, 1, length(l) - 1); n-- }
  }
  {
    l = $0
    sub(/\r$/, "", l)
    if (!match(l, /^[ \t>*•_`|-]*[Oo][Uu][Tt][Cc][Oo][Mm][Ee]:/)) next
    prefix = substr(l, 1, RLENGTH - 8)
    l = substr(l, RLENGTH + 1)
    sub(/^[ \t*_`]+/, "", l)
    sub(/[ \t]+$/, "", l)
    # Emphasis or code that wraps the whole line is removed symmetrically: as many closers as openers.
    stars = prefix; ticks = prefix; unders = prefix
    gsub(/[^*]/, "", stars); gsub(/[^`]/, "", ticks); gsub(/[^_]/, "", unders)
    strip_end("*", length(stars)); strip_end("`", length(ticks)); strip_end("_", length(unders))
    # A table row has its closing pipe.
    if (index(prefix, "|") > 0) { sub(/[ \t]*\|[ \t]*$/, "", l) }
    sub(/[ \t]+$/, "", l)
    # Fields one to three end at a pipe; the detail is the rest, pipes and all, as given.
    rest = l
    for (k = 1; k <= 3; k++) {
      if (match(rest, /[ \t]*\|[ \t]*/)) { f[k] = substr(rest, 1, RSTART - 1); rest = substr(rest, RSTART + RLENGTH) }
      else { f[k] = rest; rest = "" }
    }
    if (f[3] !~ /^(accepted|restored|refused)$/) next
    d = rest
    el = f[2]; st = f[3]; det = d; found = 1
  }
  END { if (found) { print el; print st; print det } }')
  if [ -n "$parsed" ]; then
    element=$(printf '%s\n' "$parsed" | sed -n 1p)
    status=$(printf '%s\n' "$parsed" | sed -n 2p)
    detail=$(printf '%s\n' "$parsed" | sed -n 3p)
    [ -n "$detail" ] || detail="no detail given"
  else
    element="" status=refused detail="no outcome line"
  fi
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

# Bytes that are not valid UTF-8 are dropped so the JSON is always valid.
sanitize() { if command -v iconv >/dev/null; then iconv -c -f UTF-8 -t UTF-8; else cat; fi; }
printf '%s' "$message" | tr -d '\000-\010\013-\037' | sanitize | awk '
  BEGIN { printf "{\"systemMessage\": \"" }
  { gsub(/\\/, "\\\\"); gsub(/"/, "\\\""); printf "%s%s", (NR > 1 ? "\\n" : ""), $0 }
  END { printf "\"}\n" }'
exit 0
