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

# heal_event <input>: Pre or Post (tool events), Prompt (UserPromptSubmit), empty for any other hook event.
heal_event() {
  _event=$(printf '%s' "$1" | grep -Eo '"hook_event_name"[[:space:]]*:[[:space:]]*"(Pre|Post)ToolUse"' | head -n 1 | sed -E 's/.*"(Pre|Post)ToolUse"$/\1/')
  if [ -z "$_event" ] && printf '%s' "$1" | grep -Eq '"hook_event_name"[[:space:]]*:[[:space:]]*"UserPromptSubmit"'; then
    _event=Prompt
  fi
  printf '%s' "$_event"
}

# heal_is_async_launch <input>: succeeds when a PostToolUse input only reports a background launch (no report yet).
heal_is_async_launch() {
  printf '%s' "$1" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"async_launched"'
}

# heal_json_string <input> <anchor> <key>: the decoded JSON string that follows <key> (an ERE ending at the
# opening quote), searched after <anchor> (an ERE, may be empty).
heal_json_string() {
  printf '%s' "$1" | awk -v anchor="$2" -v key="$3" '
    BEGIN { RS = "\001" }
    {
      s = $0
      if (anchor != "") {
        if (!match(s, anchor)) exit
        s = substr(s, RSTART + RLENGTH)
      }
      if (!match(s, key)) exit
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
    }'
}

# heal_report_text <input>: the decoded report text of a PostToolUse tool_response.
heal_report_text() {
  heal_json_string "$1" '"tool_response"' '"text"[ \t]*:[ \t]*"'
}

# heal_prompt_text <input>: the decoded prompt of a UserPromptSubmit input.
heal_prompt_text() {
  heal_json_string "$1" '' '"prompt"[ \t]*:[ \t]*"'
}

# heal_split_notifications <text> <dir>: writes each <task-notification> block of the text to <dir>/note.NNN
# (first line the block's tool-use-id, then its <result> text), in order.
heal_split_notifications() {
  rm -f "$2"/note.*
  printf '%s\n' "$1" | awk -v dir="$2" '
    /<task-notification>/ { inblock = 1; inres = 0; id = ""; res = ""; next }
    !inblock { next }
    {
      line = $0
      if (!inres && (p = index(line, "<tool-use-id>")) > 0) {
        id = substr(line, p + 13)
        if ((q = index(id, "</tool-use-id>")) > 0) id = substr(id, 1, q - 1)
      }
      if (!inres && (p = index(line, "<result>")) > 0) { inres = 1; line = substr(line, p + 8); res = "" }
      if (inres) {
        if ((q = index(line, "</result>")) > 0) { res = res substr(line, 1, q - 1); inres = 0; resdone = 1 }
        else res = res line "\n"
      }
      if (index($0, "</task-notification>") > 0) {
        if (id != "" && resdone) { f = sprintf("%s/note.%03d", dir, ++n); printf "%s\n%s\n", id, res > f; close(f) }
        inblock = 0; resdone = 0
      }
    }'
}

# heal_tool_use_id <input>: the call's id, safe to use in a file name.
heal_tool_use_id() {
  printf '%s' "$1" | grep -Eo '"tool_use_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 | sed -E 's/.*:[[:space:]]*"//; s/"$//' | tr -c 'A-Za-z0-9_-' '_'
}

# heal_prompt_field <input> <key>: the value of a "key: value" line of the dispatch prompt (escaped in the JSON).
heal_prompt_field() {
  printf '%s' "$1" | grep -Eo "\\\\n$2:[[:space:]]*[A-Za-z0-9_.-]+" | head -n 1 | sed "s/^.*$2:[[:space:]]*//"
}
