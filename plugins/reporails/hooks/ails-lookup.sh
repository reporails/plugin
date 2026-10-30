#!/bin/sh
# Sourced by bin/ails and the recording hook. One owner for finding an installed ails
# (no jq, plain POSIX sh: it must run under Git Bash on Windows too).

# ails_installed <self>: print the path of an installed ails on PATH other than <self>
# (the plugin's own bin/ails wrapper), or print nothing.
ails_installed() {
  _old=$IFS
  IFS=:
  for _dir in $PATH; do
    [ -n "$_dir" ] || _dir=.
    _cand=$(cd "$_dir" 2>/dev/null && pwd -P)/ails
    if [ -x "$_cand" ] && [ -f "$_cand" ] && [ "$_cand" != "$1" ]; then
      IFS=$_old
      printf '%s' "$_cand"
      return 0
    fi
  done
  IFS=$_old
  return 0
}
